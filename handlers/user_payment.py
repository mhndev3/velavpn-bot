from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from config.settings import (
    ADMIN_REPORT_CHANNEL_ID,
    STARLINK_ADMIN_REPORT_CHANNEL_ID,
    CRYPTO_PAYMENT_TEXT,
    ADMIN_IDS,
    ADMIN_PAYMENT_USERNAME,
)

from database.db import get_connection, get_setting

from keyboards.user_keyboards import (
    toman_payment_keyboard,
)

from keyboards.admin_keyboards import payment_review_keyboard

from states.user_states import (
    PaymentStates,
    AdminPaymentStates,
)

from services.referral_service import (
    process_referral_reward,
)
from services.ui_service import send_screen
from services.price_service import payment_price_block
from services.ui_texts import T, TF
from services.xui_service import provision_account
from database.db import get_plan as db_get_plan


router = Router()


def _months_label(days) -> str:
    """مدت را بر حسب ماه نشان می‌دهد (مثلاً 120 روز → «۴ ماهه»)."""
    d = int(days or 0)
    if d <= 0:
        return T("u_no_expiry", "بی‌انقضا")
    months = round(d / 30) or 1
    return str(months) + T("u_month_suffix", " ماهه")


def rows_to_dicts(cursor, rows):
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def is_starlink_order(order: dict) -> bool:
    if not order:
        return False
    service_name = str(order.get("service_name") or "")
    plan_title = str(order.get("plan_title") or "")
    return "استارلینک" in service_name or "starlink" in service_name.lower() or "استارلینک" in plan_title


def get_report_channel_id(order: dict):
    if is_starlink_order(order):
        return STARLINK_ADMIN_REPORT_CHANNEL_ID or ADMIN_REPORT_CHANNEL_ID
    return ADMIN_REPORT_CHANNEL_ID


def get_report_targets(order: dict) -> list:
    channel_id = get_report_channel_id(order)
    if channel_id:
        return [channel_id]
    return list(ADMIN_IDS)


def admin_card_contact_text(order: dict, order_id: int) -> str:
    final_price = order["final_price_toman"] or order["price_toman"]
    card_info = get_setting("card_info", "شماره کارت تنظیم نشده")
    return TF(
        "pay_card_text",
        "💳 <b>پرداخت کارت‌به‌کارت</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "🧾 شماره سفارش: <code>{order_id}</code>\n"
        "💰 مبلغ: <b>{price} تومان</b>\n\n"
        "💳 اطلاعات کارت:\n<code>{card}</code>\n\n"
        "لطفاً مبلغ را واریز کرده و <b>رسید</b> (عکس یا شماره پیگیری) را اینجا ارسال کنید.",
        order_id=order_id, price="{:,}".format(final_price), card=card_info,
    )


def get_plan(plan_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT plans.id, plans.service_id, plans.title, plans.price_toman,
           plans.duration_days, plans.traffic_gb,
           services.name AS service_name, services.category AS category,
           services.service_type AS service_type, services.server_id AS server_id
    FROM plans
    JOIN services ON services.id = plans.service_id
    WHERE plans.id = ? AND plans.is_active = 1
    """, (plan_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    plan = rows_to_dicts(cursor, [row])[0]
    conn.close()
    return plan


def create_order(telegram_id: int, plan: dict, payment_method: str = None):
    from database.sub_admin_pricing import get_price_for_user
    from database.db import get_sub_admin
    final_price = get_price_for_user(telegram_id, plan["id"])
    sub_admin = get_sub_admin(telegram_id)
    sub_admin_id = sub_admin["id"] if sub_admin else None
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO orders (telegram_id, plan_id, service_name, plan_title, price_toman,
                        duration_days, payment_method, status, discount_code,
                        discount_amount, final_price_toman, sub_admin_id, referral_processed)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        telegram_id, plan["id"], plan["service_name"], plan["title"],
        plan["price_toman"], plan["duration_days"], payment_method,
        "pending", None, plan["price_toman"] - final_price, final_price,
        sub_admin_id, 0
    ))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return order_id


def update_order_payment_method(order_id: int, payment_method: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET payment_method = ? WHERE id = ?", (payment_method, order_id))
    conn.commit()
    conn.close()


def get_order(order_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    order = rows_to_dicts(cursor, [row])[0]
    conn.close()
    return order


def save_payment(order_id, telegram_id, payment_method, receipt_type, receipt_text=None, file_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO payments (order_id, telegram_id, payment_method, receipt_type, receipt_text, file_id, status)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (order_id, telegram_id, payment_method, receipt_type, receipt_text, file_id, "waiting_admin_review"))
    payment_id = cursor.lastrowid
    cursor.execute("UPDATE orders SET status = ? WHERE id = ?", ("waiting_admin_review", order_id))
    conn.commit()
    conn.close()
    return payment_id


def update_payment_status(payment_id: int, status: str):
    if not payment_id:
        return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE payments SET status = ? WHERE id = ?", (status, payment_id))
    conn.commit()
    conn.close()


def update_order_status(order_id: int, status: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()
    conn.close()


def create_subscription(order, delivery_text=None, delivery_file_id=None, delivery_file_type=None):
    expires_at = datetime.now() + timedelta(days=int(order["duration_days"]))
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO subscriptions (telegram_id, order_id, service_name, plan_title, duration_days,
                               status, expires_at, delivery_text, delivery_file_id, delivery_file_type)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        order["telegram_id"], order["id"], order["service_name"], order["plan_title"],
        order["duration_days"], "active", expires_at.strftime("%Y-%m-%d %H:%M:%S"),
        delivery_text, delivery_file_id, delivery_file_type
    ))
    conn.commit()
    conn.close()
    return expires_at


async def _notify_admin_wallet_purchase(bot, order, telegram_id, paid_amount, result):
    """
    اعلان خرید از کیف‌پول به هد‌ادمین‌ها:
    مشخصات کاربر + مشخصات کانفیگ + تعداد + موجودی باقی‌ماندهٔ کیف‌پول.
    """
    from database.wallet import get_wallet
    name = username = phone = ""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT full_name, username, custom_username, phone FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        r = cur.fetchone()
        conn.close()
        if r:
            d = dict(r)
            name = (d.get("full_name") or "").strip()
            username = (d.get("custom_username") or d.get("username") or "").strip()
            phone = (d.get("phone") or "").strip()
    except Exception:
        pass

    try:
        w = get_wallet(telegram_id)
        remaining = w["balance_toman"] if w else 0
    except Exception:
        remaining = 0

    qty = int(order.get("quantity") or 1)

    cfg_block = ""
    if result:
        server = result.get("server_label", "—")
        traffic = result.get("traffic_gb", 0)
        expires = result.get("expires_at", "—")
        link = result.get("config_link", "")
        cfg_block = (
            "\n🌍 سرور: " + str(server) +
            (("\n📥 حجم: " + str(traffic) + " گیگ") if traffic else "") +
            "\n📅 انقضا: " + str(expires)
        )
        if link:
            cfg_block += "\n🔗 لینک:\n<code>" + link + "</code>"

    uname = ("@" + username) if (username and not username.startswith("@")) else (username or "—")
    _is_rnw = bool((order.get("renew_email") or "").strip())
    text = (
        ("♻️ <b>تمدید از کیف‌پول</b>\n" if _is_rnw else "🛒 <b>خرید جدید از کیف‌پول</b>\n")
        + "━━━━━━━━━━━━━━\n"
        "👤 نام: " + (name or "—") + "\n"
        "🆔 آیدی: <code>" + str(telegram_id) + "</code>\n"
        "📛 یوزرنیم: " + uname + "\n"
        + (("📱 تلفن: " + phone + "\n") if phone else "") +
        "━━━━━━━━━━━━━━\n"
        "📦 سرویس: " + str(order.get("service_name") or "—") + "\n"
        + (("♻️ کانفیگ در حال تمدید: " + str(order.get("renew_email") or "—") + "\n") if _is_rnw else "") +
        "🏷 نام کانفیگ: " + str(order.get("config_name") or "—") + "\n"
        "🔢 تعداد: " + str(qty) + "\n"
        "💵 مبلغ پرداختی: " + "{:,}".format(paid_amount) + " تومان\n"
        "💳 موجودی باقی‌مانده: " + "{:,}".format(remaining) + " تومان"
        + cfg_block
    )

    sent_to = set()
    for admin_id in ADMIN_IDS:
        if admin_id in sent_to:
            continue
        sent_to.add(admin_id)
        try:
            await bot.send_message(chat_id=admin_id, text=text, disable_web_page_preview=True)
        except Exception:
            pass


async def _finalize_auto_delivery(message_obj, order, payment_id, result):
    from services.referral_service import process_referral_reward, notify_referral_reward
    order_id = order["id"]
    target_user_id = order["telegram_id"]
    config_link = result.get("config_link", "")
    config_type = result.get("config_type", "vless").upper()
    expires_at = result.get("expires_at", "—")
    traffic = result.get("traffic_gb", 0)
    server = result.get("server_label", "—")

    delivery_text = "لینک " + config_type + ": " + config_link
    # همه DB writes در یک تراکنش
    from database.db import get_connection, save_xui_account
    from datetime import datetime, timedelta
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE payments SET status='approved' WHERE id=?", (payment_id,))
        cursor.execute("UPDATE orders SET status='approved' WHERE id=?", (order_id,))
        days = int(order.get("duration_days") or 30)
        exp = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO subscriptions
            (telegram_id, order_id, service_name, plan_title, duration_days, status, expires_at, delivery_text)
            VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
        """, (order["telegram_id"], order_id, order["service_name"], order["plan_title"], days, exp, delivery_text))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()
    if result:
        try:
            save_xui_account(
                telegram_id=order["telegram_id"], order_id=order_id,
                server_id=result.get("server_id", 0),
                xui_client_id=result.get("client_id", ""),
                xui_inbound_id=result.get("inbound_id", 0),
                email=result.get("email", ""),
                config_link=config_link,
                config_type=result.get("config_type", "vless"),
                traffic_gb=result.get("traffic_gb", 0),
                expires_at=result.get("expires_at", ""),
                sub_id=result.get("sub_id", ""),
            )
        except Exception:
            pass
    try:
        reward_data = process_referral_reward(order)
    except Exception:
        reward_data = {}

    msg_text = TF(
        "pay_delivered",
        "✅ پرداخت تایید شد و کانفیگ آماده است!\n\n"
        "سرویس: {service}\n"
        "پلن: {plan}\n"
        "سرور: {server}\n"
        "انقضا: {expires}\n",
        service=order["service_name"], plan=order["plan_title"],
        server=server, expires=expires_at,
    )
    if traffic:
        msg_text += TF("pay_delivered_traffic", "حجم: {gb} GB\n", gb=traffic)
    msg_text += TF("pay_delivered_link", "\n🔗 لینک {type}:\n<code>{link}</code>",
                   type=config_type, link=config_link)

    await message_obj.bot.send_message(chat_id=target_user_id, text=msg_text)

    try:
        import io, qrcode
        from aiogram.types import BufferedInputFile
        img = qrcode.make(config_link)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        await message_obj.bot.send_photo(
            chat_id=target_user_id,
            photo=BufferedInputFile(buf.read(), filename="qr.png"),
        )
    except Exception:
        pass

    await notify_referral_reward(message_obj.bot, reward_data)


async def process_wallet_payment(message_obj, telegram_id: int, order_id: int, state: FSMContext):
    from database.wallet import get_wallet, deduct_from_wallet
    order = get_order(order_id)
    if not order:
        await message_obj.answer("❌ " + T("pay_order_gone", "سفارش پیدا نشد."))
        await state.clear()
        return

    final_price = order["final_price_toman"] or order["price_toman"]
    wallet = get_wallet(telegram_id)
    balance = wallet["balance_toman"] if wallet else 0

    if balance < final_price:
        shortage = final_price - balance
        await message_obj.answer(
            TF("pay_wallet_insufficient",
               "❌ موجودی کیف‌پول کافی نیست\n\n"
               "نیاز: {need} تومان\n"
               "موجودی: {balance} تومان\n"
               "کمبود: {shortage} تومان\n\n"
               "از بخش «💳 کیف پول» شارژ کنید.",
               need="{:,}".format(final_price), balance="{:,}".format(balance),
               shortage="{:,}".format(shortage))
        )
        await state.clear()
        return

    # ── تمدید؟ اگر سفارش تمدید یک اکانت موجود است، شارژ کن (نه ساخت جدید) ──
    from handlers.user_renew import order_is_renewal, fulfill_renewal
    if order_is_renewal(order):
        renew_res = await fulfill_renewal(message_obj.bot, order)
        conn = get_connection()
        cursor = conn.cursor()
        try:
            if renew_res:
                cursor.execute("UPDATE orders SET payment_method='wallet', status='approved' WHERE id=?", (order_id,))
            cursor.execute("""
                INSERT INTO payments (order_id, telegram_id, payment_method, receipt_type, receipt_text, status)
                VALUES (?, ?, 'wallet', 'text', 'پرداخت خودکار از کیف‌پول (تمدید)', ?)
            """, (order_id, telegram_id, "approved" if renew_res else "waiting_admin_review"))
            conn.commit()
        finally:
            conn.close()
        if renew_res:
            deduct_from_wallet(telegram_id, final_price, order_id)
            await state.clear()
            return
        else:
            await message_obj.answer(T("pay_renew_failed", "❌ تمدید ناموفق بود. لطفاً با پشتیبانی تماس بگیرید."))
            await state.clear()
            return

    # ── اول X-UI (بدون هیچ DB write) ──────────────────────────
    plan = db_get_plan(order.get("plan_id")) if order.get("plan_id") else None
    server_id = plan.get("server_id") if plan else None
    if not server_id:
        from database.db import get_best_server
        best = get_best_server()
        server_id = best["id"] if best else None

    result = None
    extra_results = []
    if server_id:
        plan_data = plan or {
            "duration_days": int(order.get("duration_days") or 30),
            "traffic_gb": int(order.get("traffic_gb") or 0),
        }
        result = await provision_account(
            order_id=order_id, telegram_id=telegram_id,
            plan=plan_data, server_id=server_id,
        )

        # سفارش چند-تایی: بقیهٔ اکانت‌ها با نام یکتا ساخته می‌شوند
        # (بدون این حلقه، خرید با تعداد بیشتر از یک فقط یک کانفیگ می‌ساخت)
        _qty_prov = int(order.get("quantity") or 1)
        if result and result.get("config_link") and _qty_prov > 1:
            for _i in range(2, _qty_prov + 1):
                try:
                    _ex = await provision_account(
                        order_id=order_id, telegram_id=telegram_id,
                        plan=plan_data, server_id=server_id,
                        name_suffix="-" + str(_i),
                    )
                    if _ex and _ex.get("config_link"):
                        extra_results.append(_ex)
                except Exception:
                    pass

    # ── بعد همه DB writes در یک تراکنش ──────────────────────
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE orders SET payment_method='wallet', status=? WHERE id=?",
            ("approved" if (result and result.get("config_link")) else "waiting_delivery", order_id)
        )
        cursor.execute("""
            INSERT INTO payments (order_id, telegram_id, payment_method, receipt_type, receipt_text, status)
            VALUES (?, ?, 'wallet', 'text', 'پرداخت خودکار از کیف‌پول', 'approved')
        """, (order_id, telegram_id))
        payment_id = cursor.lastrowid
        conn.commit()
    except Exception:
        conn.rollback()
        payment_id = 0
    finally:
        conn.close()

    # کسر از کیف‌پول
    deduct_from_wallet(telegram_id, final_price, order_id)

    # اعلان خرید کیف‌پول به هد‌ادمین (با مشخصات کاربر، کانفیگ، تعداد و موجودی باقی‌مانده)
    try:
        await _notify_admin_wallet_purchase(message_obj.bot, order, telegram_id, final_price, result)
    except Exception:
        pass

    if result and result.get("config_link"):
        await _finalize_auto_delivery(message_obj, order, payment_id, result)
        # اکانت‌های اضافیِ سفارش چند-تایی: ذخیره و ارسال هرکدام
        for _ex in extra_results:
            try:
                from database.db import save_xui_account
                save_xui_account(
                    telegram_id=telegram_id, order_id=order_id,
                    server_id=_ex.get("server_id", 0),
                    xui_client_id=_ex.get("client_id", ""),
                    xui_inbound_id=_ex.get("inbound_id", 0),
                    email=_ex.get("email", ""),
                    config_link=_ex.get("config_link", ""),
                    config_type=_ex.get("config_type", "vless"),
                    traffic_gb=_ex.get("traffic_gb", 0),
                    expires_at=_ex.get("expires_at", ""),
                    sub_id=_ex.get("sub_id", ""),
                )
            except Exception:
                pass
            try:
                await message_obj.bot.send_message(
                    chat_id=telegram_id,
                    text=TF("pay_delivered_link", "\n🔗 لینک {type}:\n<code>{link}</code>",
                            type=_ex.get("config_type", "vless"),
                            link=_ex.get("config_link", "")),
                )
            except Exception:
                pass
        await state.clear()
        return

    update_order_status(order_id, "waiting_delivery")
    await message_obj.answer(
        TF("pay_wallet_waiting",
           "✅ پرداخت از کیف‌پول انجام شد\n\n"
           "سرویس: {service}\n"
           "مبلغ: {price} تومان\n\n"
           "⏳ کانفیگ به‌زودی توسط پشتیبانی ارسال می‌شود.",
           service=order["service_name"], price="{:,}".format(final_price))
    )

    _qty = int(order.get("quantity") or 1)
    _is_renewal = bool((order.get("renew_email") or "").strip())
    _wallet_txt = (
        "💰 پرداخت کیف‌پول (نیاز به تحویل دستی)\n\n"
        "نوع: " + ("♻️ تمدید اشتراک" if _is_renewal else "🆕 خرید جدید") + "\n"
        "سفارش: #" + str(order_id) + "\n"
        "کاربر: " + str(telegram_id) + "\n"
        "سرویس: " + str(order["service_name"]) + "\n"
        "پلن: " + str(order.get("plan_title") or "—") + "\n"
    )
    if _is_renewal:
        _wallet_txt += "کانفیگ در حال تمدید: " + str(order.get("renew_email") or "—") + "\n"
    if _qty > 1:
        _wallet_txt += ("تعداد: " + str(_qty) + " عدد\n"
                        "قیمت واحد: " + "{:,}".format(order["price_toman"] or 0) + " تومان\n")
    _wallet_txt += "مبلغ: " + "{:,}".format(final_price) + " تومان"

    for admin_id in ADMIN_IDS:
        try:
            await message_obj.bot.send_message(
                chat_id=admin_id,
                text=_wallet_txt,
                reply_markup=payment_review_keyboard(order_id, payment_id)
            )
        except Exception:
            pass
    await state.clear()


@router.callback_query(F.data.startswith("payment_order:"))
async def payment_order_handler(callback: CallbackQuery, state: FSMContext):
    _, order_id_raw, currency = callback.data.split(":")
    order_id = int(order_id_raw)
    order = get_order(order_id)
    if not order:
        return await callback.answer(T("pay_order_gone", "سفارش پیدا نشد."), show_alert=True)

    final_price = order["final_price_toman"] or order["price_toman"]
    text = TF(
        "pay_order_pick",
        "💳 انتخاب روش پرداخت\n"
        "━━━━━━━━━━━━━━\n\n"
        "شماره سفارش: <code>{order_id}</code>\n"
        "سرویس: {service}\n"
        "پلن: {plan}\n"
        "{price_block}",
        order_id=order_id, service=order["service_name"], plan=order["plan_title"],
        price_block=payment_price_block(final_price),
    )

    if currency == "toman":
        await send_screen(callback, state, text, reply_markup=toman_payment_keyboard(order_id), banner_key="payment", back_to="u:menu")
    else:
        await callback.answer(T("pay_method_invalid", "روش پرداخت نامعتبر است."), show_alert=True)


@router.callback_query(F.data.startswith("payment_currency:"))
async def payment_currency_handler(callback: CallbackQuery, state: FSMContext):
    _, plan_id_raw, currency = callback.data.split(":")
    plan_id = int(plan_id_raw)
    plan = get_plan(plan_id)
    if not plan:
        return await callback.answer(T("shop_plan_notfound", "پلن پیدا نشد."), show_alert=True)

    order_id = create_order(telegram_id=callback.from_user.id, plan=plan)

    from database.sub_admin_pricing import get_price_for_user
    final_price = get_price_for_user(callback.from_user.id, plan_id)

    if currency == "wallet":
        await process_wallet_payment(callback.message, callback.from_user.id, order_id, state)
        await callback.answer()
        return

    text = TF(
        "pay_order_created",
        "🧾 سفارش ثبت شد\n"
        "━━━━━━━━━━━━━━\n\n"
        "شماره سفارش: <code>{order_id}</code>\n"
        "سرویس: {service}\n"
        "پلن: {plan}\n"
        "مدت: {dur}\n"
        "{price_block}",
        order_id=order_id, service=plan["service_name"], plan=plan["title"],
        dur=_months_label(plan.get("duration_days")),
        price_block=payment_price_block(final_price),
    )

    if currency == "toman":
        await send_screen(callback, state, text, reply_markup=toman_payment_keyboard(order_id), banner_key="payment", back_to="u:menu")
    else:
        await callback.answer(T("pay_method_invalid", "روش پرداخت نامعتبر است."), show_alert=True)


@router.callback_query(F.data.startswith("payment_method:"))
async def payment_method_handler(callback: CallbackQuery, state: FSMContext):
    _, order_id_raw, method = callback.data.split(":")
    order_id = int(order_id_raw)
    order = get_order(order_id)
    if not order:
        return await callback.answer(T("pay_order_gone", "سفارش پیدا نشد."), show_alert=True)

    update_order_payment_method(order_id, method)

    if method == "card":
        update_order_payment_method(order_id, "card")
        await state.update_data(order_id=order_id, payment_method="card")
        await send_screen(
            callback, state,
            admin_card_contact_text(order, order_id),
            banner_key="payment",
            back_to="u:menu",
        )
        await state.set_state(PaymentStates.waiting_for_card_receipt)
        await callback.answer()
        return

    elif method == "wallet":
        await process_wallet_payment(callback.message, callback.from_user.id, order_id, state)
        await callback.answer()
        return

    else:
        await callback.answer(T("pay_method_invalid", "روش پرداخت نامعتبر است."), show_alert=True)


@router.message(PaymentStates.waiting_for_card_receipt)
async def card_receipt_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")
    payment_method = data.get("payment_method", "card")

    receipt_text = message.caption or message.text or T("pay_receipt_no_text", "رسید بدون متن")
    file_id = None
    receipt_type = "text"

    if message.photo:
        file_id = message.photo[-1].file_id
        receipt_type = "photo"
    elif message.document:
        file_id = message.document.file_id
        receipt_type = "document"

    payment_id = save_payment(
        order_id=order_id,
        telegram_id=message.from_user.id,
        payment_method=payment_method,
        receipt_type=receipt_type,
        receipt_text=receipt_text,
        file_id=file_id
    )

    await message.answer(
        T("pay_receipt_saved",
          "✅ رسید شما ثبت شد.\n\n"
          "پرداخت برای بررسی به ادمین ارسال شد.\n"
          "بعد از تایید، کانفیگ برای شما ارسال می‌شه.")
    )

    order = get_order(order_id)
    await send_payment_report_to_admin(
        message=message,
        order_id=order_id,
        payment_id=payment_id,
        payment_method="کارت‌به‌کارت",
        receipt_text=receipt_text,
        file_id=file_id,
        receipt_type=receipt_type
    )
    await state.clear()


async def send_payment_report_to_admin(
    message, order_id, payment_id, payment_method,
    receipt_text=None, file_id=None, receipt_type="text"
):
    order = get_order(order_id)
    if not order:
        return

    final_price = order["final_price_toman"] or order["price_toman"]
    user = message.from_user

    qty = int(order.get("quantity") or 1)
    is_renewal = bool((order.get("renew_email") or "").strip())
    unit_price = order["price_toman"] or 0

    head = ("♻️ تمدید اشتراک" if is_renewal else "🆕 خرید جدید")

    caption = (
        "💳 رسید پرداخت جدید\n\n"
        "نوع: " + head + "\n"
        "شماره سفارش: #" + str(order_id) + "\n"
        "کاربر: " + str(user.full_name) + "\n"
        "آیدی: " + str(user.id) + "\n"
        "سرویس: " + str(order["service_name"]) + "\n"
        "پلن: " + str(order["plan_title"]) + "\n"
    )

    if is_renewal:
        caption += "کانفیگ در حال تمدید: " + str(order.get("renew_email") or "—") + "\n"

    if qty > 1:
        caption += ("تعداد: " + str(qty) + " عدد\n"
                    "قیمت واحد: " + "{:,}".format(unit_price) + " تومان\n")

    caption += (
        "مبلغ: " + "{:,}".format(final_price) + " تومان\n"
        "روش: " + payment_method + "\n\n"
        "رسید:\n" + str(receipt_text or "—")
    )

    kb = payment_review_keyboard(order_id, payment_id)
    targets = get_report_targets(order)

    for target_id in targets:
        try:
            if receipt_type == "photo" and file_id:
                await message.bot.send_photo(chat_id=target_id, photo=file_id, caption=caption, reply_markup=kb)
            elif receipt_type == "document" and file_id:
                await message.bot.send_document(chat_id=target_id, document=file_id, caption=caption, reply_markup=kb)
            else:
                await message.bot.send_message(chat_id=target_id, text=caption, reply_markup=kb)
        except Exception:
            pass


@router.callback_query(F.data.startswith("payment_currency_discount:"))
async def payment_currency_discount_handler(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    plan_id = int(parts[1])
    currency = parts[2]
    discount_code = parts[3] if len(parts) > 3 else None

    plan = get_plan(plan_id)
    if not plan:
        return await callback.answer(T("shop_plan_notfound", "پلن پیدا نشد."), show_alert=True)

    from database.sub_admin_pricing import get_price_for_user
    base_price = get_price_for_user(callback.from_user.id, plan_id)

    discount_amount = 0
    if discount_code:
        from database.db import get_connection as _c
        conn = _c()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM discount_codes WHERE code = ? AND is_active = 1", (discount_code,))
        row = cursor.fetchone()
        conn.close()
        if row:
            dc = dict(row)
            if dc["discount_type"] == "percent":
                discount_amount = int(base_price * dc["amount"] / 100)
            else:
                discount_amount = dc["amount"]

    final_price = max(0, base_price - discount_amount)

    conn = get_connection()
    cursor = conn.cursor()
    from database.db import get_sub_admin
    sub_admin = get_sub_admin(callback.from_user.id)
    sub_admin_id = sub_admin["id"] if sub_admin else None
    cursor.execute("""
        INSERT INTO orders (telegram_id, plan_id, service_name, plan_title, price_toman,
                            duration_days, payment_method, status, discount_code,
                            discount_amount, final_price_toman, sub_admin_id, referral_processed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        callback.from_user.id, plan["id"], plan["service_name"], plan["title"],
        plan["price_toman"], plan["duration_days"], currency, "pending",
        discount_code, discount_amount, final_price, sub_admin_id, 0
    ))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()

    if currency == "wallet":
        await process_wallet_payment(callback.message, callback.from_user.id, order_id, state)
        await callback.answer()
        return

    text = TF(
        "pay_order_created_disc",
        "🧾 سفارش ثبت شد\n"
        "━━━━━━━━━━━━━━\n\n"
        "شماره سفارش: <code>{order_id}</code>\n"
        "سرویس: {service}\n"
        "پلن: {plan}\n"
        "{price_block}",
        order_id=order_id, service=plan["service_name"], plan=plan["title"],
        price_block=payment_price_block(final_price),
    )
    if currency == "toman":
        await send_screen(callback, state, text, reply_markup=toman_payment_keyboard(order_id), banner_key="payment", back_to="u:menu")
    else:
        await callback.answer(T("pay_method_invalid", "روش پرداخت نامعتبر است."), show_alert=True)
