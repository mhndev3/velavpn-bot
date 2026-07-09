"""
admin_payment_review.py — تایید/رد پرداخت + X-UI خودکار
FIX: database locked — همه DB writes بعد از X-UI و در یک تراکنش
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from config.settings import ADMIN_IDS
from states.user_states import AdminPaymentStates
from services.xui_service import provision_account

router = Router()


def _get_order(order_id):
    from database.db import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def _finalize_approved(order_id, payment_id, order, result=None, config_link=""):
    """همه DB writes در یک connection — جلوگیری از database locked"""
    from database.db import get_connection, save_xui_account, _retry_on_locked
    from datetime import datetime, timedelta

    actual_link = (result.get("config_link") if result else None) or config_link or ""

    def _do():
        conn = get_connection()
        cursor = conn.cursor()
        try:
            if payment_id:
                cursor.execute("UPDATE payments SET status='approved' WHERE id=?", (payment_id,))
            cursor.execute("UPDATE orders SET status='approved' WHERE id=?", (order_id,))
            days = int(order.get("duration_days") or 30)
            expires_at = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO subscriptions
                (telegram_id, order_id, service_name, plan_title, duration_days,
                 status, expires_at, delivery_text)
                VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
            """, (
                order["telegram_id"], order["id"],
                order["service_name"], order["plan_title"],
                days, expires_at, actual_link,
            ))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    _retry_on_locked(_do)

    # ذخیره xui_account بعد از بسته شدن connection بالا
    if result:
        try:
            save_xui_account(
                telegram_id=order["telegram_id"],
                order_id=order_id,
                server_id=result.get("server_id", 0),
                xui_client_id=result.get("client_id", ""),
                xui_inbound_id=result.get("inbound_id", 0),
                email=result.get("email", ""),
                config_link=actual_link,
                config_type=result.get("config_type", "vless"),
                traffic_gb=result.get("traffic_gb", 0),
                expires_at=result.get("expires_at", ""),
                sub_id=result.get("sub_id", ""),
            )
        except Exception:
            pass


def _finalize_rejected(order_id, payment_id):
    from database.db import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if payment_id:
            cursor.execute("UPDATE payments SET status='rejected' WHERE id=?", (payment_id,))
        cursor.execute("UPDATE orders SET status='rejected' WHERE id=?", (order_id,))
        conn.commit()
    finally:
        conn.close()


def _set_waiting_delivery(order_id, payment_id):
    from database.db import get_connection, _retry_on_locked
    def _do():
        conn = get_connection()
        cursor = conn.cursor()
        try:
            if payment_id:
                cursor.execute("UPDATE payments SET status='approved' WHERE id=?", (payment_id,))
            cursor.execute("UPDATE orders SET status='waiting_delivery' WHERE id=?", (order_id,))
            conn.commit()
        finally:
            conn.close()
    _retry_on_locked(_do)


def _create_subscription_manual(order, delivery_text=None, file_id=None, file_type=None):
    from database.db import get_connection
    from datetime import datetime, timedelta
    days = int(order.get("duration_days") or 30)
    expires_at = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO subscriptions
            (telegram_id, order_id, service_name, plan_title, duration_days,
             status, expires_at, delivery_text, delivery_file_id, delivery_file_type)
            VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)
        """, (
            order["telegram_id"], order["id"],
            order["service_name"], order["plan_title"],
            days, expires_at, delivery_text, file_id, file_type,
        ))
        cursor.execute("UPDATE orders SET status='approved' WHERE id=?", (order["id"],))
        conn.commit()
    finally:
        conn.close()


async def _send_config_to_user(bot, target_user_id, order, result):
    config_link = result.get("config_link", "")
    expires = result.get("expires_at", "—")
    traffic = result.get("traffic_gb", 0)
    server = result.get("server_label", "—")
    email = result.get("email", "")

    links = result.get("config_links") or []
    if not links and config_link:
        links = [{"protocol": result.get("config_type", "vless"), "link": config_link}]
    links = [l for l in links if (l.get("link") or "").strip()]

    _PROTO_LABEL = {
        "vless": "🟢 VLESS", "vmess": "🔵 VMess", "trojan": "🟣 Trojan",
        "shadowsocks": "🟠 Shadowsocks", "ss": "🟠 Shadowsocks",
    }

    # همه‌چیز در یک پیام: عکس QR + کپشنِ کامل (اطلاعات + لینک)
    caption = (
        "✅ پرداخت تأیید شد — کانفیگ آماده است!\n\n"
        "سرویس: " + str(order["service_name"]) + "\n"
        "پلن: " + str(order["plan_title"]) + "\n"
        "سرور: " + str(server) + "\n"
    )
    if email:
        caption += "نام کانفیگ: " + str(email) + "\n"
    caption += "انقضا: " + str(expires) + "\n"
    if traffic:
        caption += "حجم: " + str(traffic) + " GB\n"
    caption += "\n"
    for item in links:
        label = _PROTO_LABEL.get((item.get("protocol") or "").lower(), "🔗 کانفیگ")
        caption += label + ":\n<code>" + item["link"].strip() + "</code>\n\n"
    caption = caption.rstrip()

    primary = (links[0]["link"].strip() if links else config_link)
    sent = False
    if primary:
        try:
            import io, qrcode
            from aiogram.types import BufferedInputFile
            img = qrcode.make(primary)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            photo_caption = caption if len(caption) <= 1024 else (caption[:1015] + "…")
            await bot.send_photo(
                chat_id=target_user_id,
                photo=BufferedInputFile(buf.read(), filename="config.png"),
                caption=photo_caption,
            )
            sent = True
        except Exception:
            sent = False
    if not sent:
        await bot.send_message(chat_id=target_user_id, text=caption)


# ─── Approve ─────────────────────────────────────────────────
@router.callback_query(F.data.startswith("admin_payment:approve:"))
async def admin_approve_payment_handler(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("دسترسی ندارید", show_alert=True)

    parts = callback.data.split(":")
    order_id = int(parts[2])
    payment_id = int(parts[3])

    order = _get_order(order_id)
    if not order:
        return await callback.answer("سفارش پیدا نشد", show_alert=True)

    target_user_id = order["telegram_id"]
    await callback.answer("⏳ در حال ساخت اکانت...", show_alert=False)

    # پیدا کردن سرور
    from database.db import get_best_server
    try:
        from database.db import get_plan as db_get_plan
        plan = db_get_plan(order.get("plan_id")) if order.get("plan_id") else None
    except Exception:
        plan = None
    server_id = plan.get("server_id") if plan else None
    if not server_id:
        best = get_best_server()
        server_id = best["id"] if best else None

    # ── اول X-UI (بدون هیچ DB write) ──
    result = await provision_account(
        order_id=order_id,
        telegram_id=target_user_id,
        plan=plan or {"duration_days": int(order.get("duration_days") or 30), "traffic_gb": 0},
        server_id=server_id,
    )

    # ── بعد همه DB writes در یک تراکنش ──
    if result and result.get("config_link"):
        _finalize_approved(order_id, payment_id, order, result=result)
        await _send_config_to_user(callback.bot, target_user_id, order, result)
        # حذف پیام رسید قبلی (عکس یا متن) و جایگزینی با فاکتور تمیز
        try:
            await callback.message.delete()
        except Exception:
            pass
        try:
            from database.db import get_user
            u = get_user(target_user_id) or {}
            uname = u.get("full_name") or u.get("username") or str(target_user_id)
        except Exception:
            uname = str(target_user_id)
        price = order.get("final_price_toman") or order.get("price_toman") or 0
        try:
            price_txt = "{:,}".format(int(price))
        except Exception:
            price_txt = str(price)
        cfg_name = result.get("email") or order.get("config_name") or ""
        invoice = (
            "🧾 فاکتور سفارش #" + str(order_id) + "\n"
            "━━━━━━━━━━━━━━\n"
            "کاربر: " + str(uname) + "\n"
            "آیدی: " + str(target_user_id) + "\n"
            "سرویس: " + str(order.get("service_name") or "—") + "\n"
            "پلن: " + str(order.get("plan_title") or "—") + "\n"
        )
        if cfg_name:
            invoice += "نام کانفیگ: " + str(cfg_name) + "\n"
        invoice += "مبلغ: " + price_txt + " تومان\n\n"
        invoice += "✅ سفارش تایید و کانفیگ ارسال شد"
        try:
            await callback.message.answer(invoice)
        except Exception:
            pass
        try:
            from services.referral_service import process_referral_reward, notify_referral_reward
            reward_data = process_referral_reward(order)
            await notify_referral_reward(callback.bot, reward_data)
        except Exception:
            pass
    else:
        _set_waiting_delivery(order_id, payment_id)
        await state.update_data(order_id=order_id, payment_id=payment_id, target_user_id=target_user_id)
        await callback.message.reply(
            "⚠️ ساخت خودکار از X-UI ناموفق بود.\n\n"
            "کانفیگ رو دستی بفرست (متن، عکس یا لینک vless):"
        )
        await state.set_state(AdminPaymentStates.waiting_for_delivery)


# ─── Reject ──────────────────────────────────────────────────
@router.callback_query(F.data.startswith("admin_payment:reject:"))
async def admin_reject_payment_handler(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("دسترسی ندارید", show_alert=True)

    parts = callback.data.split(":")
    order_id = int(parts[2])
    payment_id = int(parts[3])

    order = _get_order(order_id)
    if not order:
        return await callback.answer("سفارش پیدا نشد", show_alert=True)

    await state.update_data(order_id=order_id, payment_id=payment_id, target_user_id=order["telegram_id"])
    await callback.message.reply("❌ دلیل رد پرداخت رو بنویس:")
    await state.set_state(AdminPaymentStates.waiting_for_reject_reason)
    await callback.answer()


# ─── Delivery (دستی) ─────────────────────────────────────────
@router.message(AdminPaymentStates.waiting_for_delivery)
async def admin_delivery_handler(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    target_user_id = data.get("target_user_id")
    order = _get_order(order_id)
    if not order:
        await state.clear()
        return await message.answer("سفارش پیدا نشد.")

    delivery_text = message.caption or message.text or ""
    file_id, file_type = None, None
    if message.photo:
        file_id, file_type = message.photo[-1].file_id, "photo"
    elif message.document:
        file_id, file_type = message.document.file_id, "document"
    elif message.video:
        file_id, file_type = message.video.file_id, "video"

    _create_subscription_manual(order, delivery_text, file_id, file_type)

    await message.bot.send_message(
        chat_id=target_user_id,
        text="✅ پرداخت تایید شد\n\nسرویس: " + str(order["service_name"]) + "\n\n🔐 اطلاعات دسترسی:"
    )
    if file_type == "photo" and file_id:
        await message.bot.send_photo(chat_id=target_user_id, photo=file_id, caption=delivery_text)
    elif file_type == "document" and file_id:
        await message.bot.send_document(chat_id=target_user_id, document=file_id, caption=delivery_text)
    elif file_type == "video" and file_id:
        await message.bot.send_video(chat_id=target_user_id, video=file_id, caption=delivery_text)
    elif delivery_text:
        await message.bot.send_message(chat_id=target_user_id, text=delivery_text)

    try:
        from services.referral_service import process_referral_reward, notify_referral_reward
        await notify_referral_reward(message.bot, process_referral_reward(order))
    except Exception:
        pass

    await message.answer("✅ کانفیگ برای کاربر ارسال شد.")
    await state.clear()


# ─── Reject Reason ───────────────────────────────────────────
@router.message(AdminPaymentStates.waiting_for_reject_reason)
async def admin_reject_reason_handler(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    payment_id = data.get("payment_id")
    target_user_id = data.get("target_user_id")

    _finalize_rejected(order_id, payment_id)

    reason = message.text or "پرداخت تأیید نشد."
    await message.bot.send_message(
        chat_id=target_user_id,
        text="❌ پرداخت شما تأیید نشد\n\nسفارش: #" + str(order_id) + "\n\nدلیل:\n" + reason
    )
    await message.answer("❌ پرداخت رد شد.")
    await state.clear()
