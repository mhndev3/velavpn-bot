"""
user_renew.py — تمدید اشتراک.

جریان (طبق خواستهٔ کارفرما):
  دکمهٔ «♻️ تمدید اشتراک» → انتخاب کانفیگی که می‌خواهد شارژ شود →
  انتخاب مدت → انتخاب حجم (پلن) → پرداخت.
  (بدون انتخاب لوکیشن؛ روی همان سرورِ اکانت فعلی انجام می‌شود.)

پس از تأیید پرداخت، به‌جای ساخت اکانت جدید، همان اکانت با حجم و مدتِ
«جمع‌شده» به‌روزرسانی می‌شود (services.xui_service.renew_account).
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message

from database.db import get_connection, get_setting
from handlers.btn_filter import Btn
from services.ui_texts import T, TF

router = Router()


def _btn(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


def _fa(s):
    return str(s)


def _dur_label(days):
    d = int(days or 0)
    if d <= 0:
        return T("u_no_expiry", "بی‌انقضا")
    months = round(d / 30) or 1
    return "\u200f" + str(months) + T("u_month_suffix", " ماهه")


# ─── اکانت‌های قابل تمدیدِ کاربر ─────────────────────────────
def _renewable_accounts(telegram_id: int):
    """اکانت‌هایی که email و server دارند (روی پنل قابل تمدیدند)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT xa.order_id, xa.email, xa.server_id, xa.config_type,
               o.config_name, xs.label AS server_label
        FROM xui_accounts xa
        LEFT JOIN orders o ON o.id = xa.order_id
        LEFT JOIN xui_servers xs ON xs.id = xa.server_id
        WHERE xa.telegram_id = ? AND xa.email != ''
        ORDER BY xa.id DESC
    """, (telegram_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def _display_name(acc: dict) -> str:
    return (acc.get("config_name") or acc.get("email") or T("rnw_config_fallback", "کانفیگ")).strip()


def _accounts_kb(telegram_id: int):
    rows = []
    for acc in _renewable_accounts(telegram_id):
        name = _display_name(acc)
        loc = acc.get("server_label") or ""
        label = "♻️ " + name + (("  •  " + loc) if loc else "")
        rows.append([_btn(label, "rnw:acc:" + str(acc["order_id"]))])
    rows.append([_btn(T("rnw_btn_back", "⬅️ بازگشت"), "u:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── پلن‌های همان سرورِ اکانت (برای مدت/حجم) ─────────────────
def _plans_for_server(server_id: int):
    """پلن‌های فعالِ استارلینک روی همان سرور."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.title, p.price_toman, p.duration_days, p.traffic_gb, p.server_id
        FROM plans p
        JOIN services s ON s.id = p.service_id
        WHERE p.is_active = 1 AND s.is_active = 1 AND p.server_id = ?
        ORDER BY p.duration_days ASC, p.price_toman ASC
    """, (server_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def _durations_kb(order_id: int, server_id: int):
    days_seen = []
    for p in _plans_for_server(server_id):
        d = int(p.get("duration_days") or 0)
        if d not in days_seen:
            days_seen.append(d)
    days_seen.sort()
    rows = [[_btn("⏳ " + _dur_label(d), "rnw:dur:" + str(order_id) + ":" + str(d))]
            for d in days_seen]
    rows.append([_btn(T("rnw_btn_back", "⬅️ بازگشت"), "rnw:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _plans_kb(order_id: int, server_id: int, days: int):
    box = get_setting("emoji_box", "📦")
    rows = []
    for p in _plans_for_server(server_id):
        if int(p.get("duration_days") or 0) != int(days):
            continue
        gb = (_fa(p["traffic_gb"]) + T("u_gig", " گیگ")) if p.get("traffic_gb") else T("u_unlimited", "نامحدود")
        price = _fa("{:,}".format(p["price_toman"]))
        rows.append([_btn("\u200f" + box + " " + gb + " | " + price + T("u_toman", " تومان"),
                          "rnw:plan:" + str(order_id) + ":" + str(p["id"]))])
    rows.append([_btn(T("rnw_btn_back", "⬅️ بازگشت"),
                     "rnw:acc:" + str(order_id))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── ورود: انتخاب اکانت ──────────────────────────────────────
async def renew_entry(msg: Message):
    accounts = _renewable_accounts(msg.from_user.id)
    text = T("rnw_title", "♻️ تمدید اشتراک") + "\n" + "━━━━━━━━━━━━━━\n\n"
    if not accounts:
        text += T("rnw_empty", "شما اکانتی برای تمدید ندارید.\nابتدا یک کانفیگ خریداری کنید.")
        kb = InlineKeyboardMarkup(inline_keyboard=[[_btn(T("rnw_btn_back", "⬅️ بازگشت"), "u:menu")]])
        return await msg.answer(text, reply_markup=kb)
    text += T("rnw_pick_account", "کدام کانفیگ را می‌خواهید شارژ/تمدید کنید؟")
    kb = _accounts_kb(msg.from_user.id)
    sent = False
    try:
        from services.banner_service import send_banner
        sent = await send_banner(msg, "renew", caption=text, reply_markup=kb)
    except Exception:
        sent = False
    if not sent:
        await msg.answer(text, reply_markup=kb)


@router.message(Btn("btn_renew", "♻️ تمدید اشتراک"))
async def renew_entry_msg(msg: Message):
    await renew_entry(msg)


@router.callback_query(F.data == "rnw:home")
async def renew_home_cb(cb: CallbackQuery):
    accounts = _renewable_accounts(cb.from_user.id)
    text = T("rnw_title", "♻️ تمدید اشتراک") + "\n━━━━━━━━━━━━━━\n\n"
    text += T("rnw_pick_account", "کدام کانفیگ را می‌خواهید شارژ/تمدید کنید؟")
    try:
        await cb.message.edit_text(text, reply_markup=_accounts_kb(cb.from_user.id))
    except Exception:
        await cb.message.answer(text, reply_markup=_accounts_kb(cb.from_user.id))
    await cb.answer()


# ─── انتخاب اکانت → نمایش مدت‌ها ─────────────────────────────
def _get_account(telegram_id: int, order_id: int):
    for acc in _renewable_accounts(telegram_id):
        if int(acc["order_id"]) == int(order_id):
            return acc
    return None


@router.callback_query(F.data.startswith("rnw:acc:"))
async def renew_pick_account(cb: CallbackQuery):
    order_id = int(cb.data.split(":")[2])
    acc = _get_account(cb.from_user.id, order_id)
    if not acc:
        return await cb.answer(T("rn_acc_notfound", "اکانت پیدا نشد"), show_alert=True)
    server_id = acc.get("server_id") or 0
    plans = _plans_for_server(server_id)
    if not plans:
        return await cb.answer(
            T("rnw_no_plans", "برای سرور این اکانت پلنی فعال نیست."), show_alert=True)
    name = _display_name(acc)
    text = (T("rnw_title", "♻️ تمدید اشتراک") + "\n"
            "🏷 " + name + "\n━━━━━━━━━━━━━━\n\n"
            + T("rnw_pick_duration", "مدت تمدید را انتخاب کنید:"))
    try:
        await cb.message.edit_text(text, reply_markup=_durations_kb(order_id, server_id))
    except Exception:
        await cb.message.answer(text, reply_markup=_durations_kb(order_id, server_id))
    await cb.answer()


# ─── انتخاب مدت → نمایش حجم‌ها ───────────────────────────────
@router.callback_query(F.data.startswith("rnw:dur:"))
async def renew_pick_duration(cb: CallbackQuery):
    parts = cb.data.split(":")
    order_id, days = int(parts[2]), int(parts[3])
    acc = _get_account(cb.from_user.id, order_id)
    if not acc:
        return await cb.answer(T("rn_acc_notfound", "اکانت پیدا نشد"), show_alert=True)
    server_id = acc.get("server_id") or 0
    name = _display_name(acc)
    text = (T("rnw_title", "♻️ تمدید اشتراک") + "\n"
            "🏷 " + name + "\n"
            "⏳ " + _dur_label(days) + "\n━━━━━━━━━━━━━━\n\n"
            + T("rnw_pick_volume", "حجم موردنظر برای تمدید را انتخاب کنید:"))
    try:
        await cb.message.edit_text(text, reply_markup=_plans_kb(order_id, server_id, days))
    except Exception:
        await cb.message.answer(text, reply_markup=_plans_kb(order_id, server_id, days))
    await cb.answer()


# ─── انتخاب پلن → ثبت سفارش تمدید و پرداخت ───────────────────
def _create_renew_order(telegram_id, plan, acc):
    """سفارش تمدید ثبت می‌کند و order_id را برمی‌گرداند."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO orders
            (telegram_id, plan_id, service_name, plan_title, price_toman,
             duration_days, status, discount_amount, final_price_toman,
             referral_processed, config_name, quantity, renew_email, renew_server_id)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', 0, ?, 0, ?, 1, ?, ?)
        """, (
            telegram_id, plan["id"],
            (acc.get("server_label") or "تمدید"), "تمدید: " + plan["title"],
            plan["price_toman"], plan.get("duration_days", 30), plan["price_toman"],
            _display_name(acc), acc.get("email"), acc.get("server_id") or 0,
        ))
        oid = cur.lastrowid
        conn.commit()
        return oid
    finally:
        conn.close()


@router.callback_query(F.data.startswith("rnw:plan:"))
async def renew_pick_plan(cb: CallbackQuery):
    from services.price_service import payment_price_block
    from keyboards.user_keyboards import payment_methods_for_order_keyboard
    parts = cb.data.split(":")
    order_id, plan_id = int(parts[2]), int(parts[3])
    acc = _get_account(cb.from_user.id, order_id)
    if not acc:
        return await cb.answer(T("rn_acc_notfound", "اکانت پیدا نشد"), show_alert=True)

    # پلن
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, title, price_toman, duration_days, traffic_gb FROM plans WHERE id = ? AND is_active = 1", (plan_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return await cb.answer(T("shop_plan_gone", "این پلن دیگر موجود نیست."), show_alert=True)
    plan = dict(row)

    new_order_id = _create_renew_order(cb.from_user.id, plan, acc)

    name = _display_name(acc)
    gb = (str(plan["traffic_gb"]) + T("u_gig", " گیگ")) if plan.get("traffic_gb") else T("u_unlimited", "نامحدود")
    text = (
        T("rnw_invoice_title", "🧾 فاکتور تمدید") + "\n"
        "━━━━━━━━━━━━━━\n\n"
        + TF("rnw_invoice_body",
             "🏷 کانفیگ: {name}\n"
             "📥 حجم: {gb}\n"
             "⏳ مدت: {dur}\n"
             "♻️ ترافیک ریست می‌شود\n",
             name=name, gb=gb, dur=_dur_label(plan["duration_days"]))
        + payment_price_block(plan["price_toman"]) + "\n\n"
        + T("rnw_invoice_hint", "پس از پرداخت، سرویس شما به این حجم و مدت بازنشانی می‌شود و ترافیک مصرف‌شده صفر می‌گردد.\nروش پرداخت را انتخاب کنید:")
    )
    try:
        await cb.message.edit_text(text, reply_markup=payment_methods_for_order_keyboard(new_order_id))
    except Exception:
        await cb.message.answer(text, reply_markup=payment_methods_for_order_keyboard(new_order_id))
    await cb.answer()


# ─── تکمیل تمدید پس از پرداخت (فراخوانی از مسیرهای پرداخت) ───
def order_is_renewal(order: dict) -> bool:
    """آیا این سفارش یک تمدید است؟"""
    return bool(order and (order.get("renew_email") or "").strip())


async def fulfill_renewal(bot, order: dict) -> dict | None:
    """
    اکانت مبدأ را با منطق «ریست و جایگزینی» تمدید می‌کند و به کاربر اطلاع می‌دهد.

    - ترافیک مصرف‌شده ریست می‌شود (مصرف → صفر).
    - حجم روی مقدار پلنِ انتخابی تنظیم می‌شود (اگر همان پلن قبلی باشد، همان حجم؛
      اگر پلن متفاوت باشد، حجم جدید).
    - مدت از حالا به‌اندازهٔ مدت پلن تنظیم می‌شود (مثلاً ۱۵ روز مانده + تمدید ۱ ماهه
      = ۳۰ روز کامل از حالا، نه ۴۵ روز).

    خروجی: dict نتیجه یا None اگر ناموفق بود.
    فقط زمانی صدا زده می‌شود که order_is_renewal(order) True باشد.
    """
    from services.xui_service import renew_account
    email = (order.get("renew_email") or "").strip()
    server_id = int(order.get("renew_server_id") or 0)
    plan_days = int(order.get("duration_days") or 0)

    # حجم هدف از روی پلن سفارش (مقدار جایگزین، نه افزوده)
    plan_gb = 0
    plan_found = False
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT traffic_gb FROM plans WHERE id = ?", (order.get("plan_id"),))
        r = cur.fetchone()
        conn.close()
        if r:
            plan_found = True
            if r["traffic_gb"]:
                plan_gb = int(r["traffic_gb"])
    except Exception:
        pass

    # محافظ ایمنی: اگر پلن بین ثبت سفارش و تأیید حذف شده باشد، plan_gb صفر می‌ماند
    # که در منطق «تنظیم» یعنی نامحدود. در این حالت حجم فعلی خودِ اکانت را نگه می‌داریم
    # تا سهواً سرویس نامحدود داده نشود.
    if not plan_found:
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT traffic_gb FROM xui_accounts WHERE email = ? AND server_id = ?",
                (email, server_id),
            )
            a = cur.fetchone()
            conn.close()
            if a and a["traffic_gb"]:
                plan_gb = int(a["traffic_gb"])
        except Exception:
            pass

    result = await renew_account(email, server_id, plan_gb, plan_days)
    if not result:
        return None

    # به‌روزرسانی رکورد اکانت در دیتابیس تا «اشتراک‌های من» مقادیر جدید را نشان دهد
    # (لینک کانفیگ تغییر نمی‌کند؛ فقط حجم/تاریخ به‌روز می‌شود)
    try:
        conn = get_connection()
        cur = conn.cursor()
        new_total = result.get("new_total_gb")
        # انقضای کامل (با ساعت) را ترجیح بده تا محاسبهٔ مدت دقیق باشد
        new_exp = result.get("new_expiry_full") or result.get("new_expiry")
        was_expired = bool(result.get("was_expired"))
        # traffic_gb فقط اگر عددی بود (نامحدود را دست نزن)
        if isinstance(new_total, (int, float)) and new_total:
            cur.execute(
                "UPDATE xui_accounts SET traffic_gb = ?, expires_at = ? WHERE email = ? AND server_id = ?",
                (int(new_total), str(new_exp), email, server_id),
            )
        else:
            cur.execute(
                "UPDATE xui_accounts SET expires_at = ? WHERE email = ? AND server_id = ?",
                (str(new_exp), email, server_id),
            )
        # اشتراک مرتبط را هم به‌روز کن (بر اساس همان اکانت)
        # با منطق جدیدِ «ریست و جایگزینی»، مدت همیشه از حالا شروع می‌شود؛
        # پس created_at را همیشه به حالا ریست می‌کنیم تا مدتِ نمایش‌داده‌شده
        # در «اشتراک‌های من» دقیقاً برابر مدتِ پلنِ تمدیدشده باشد.
        from datetime import datetime as _dt
        now_str = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("""
            UPDATE subscriptions SET expires_at = ?, created_at = ?
            WHERE order_id IN (SELECT order_id FROM xui_accounts WHERE email = ? AND server_id = ?)
        """, (str(new_exp), now_str, email, server_id))
        conn.commit()
        conn.close()
    except Exception:
        pass

    # اطلاع به کاربر
    try:
        gb_txt = (str(result.get("new_total_gb")) + T("u_gig", " گیگ")) if result.get("new_total_gb") else T("u_unlimited", "نامحدود")
        msg = (
            T("rnw_done_title", "✅ تمدید انجام شد") + "\n"
            "━━━━━━━━━━━━━━\n\n"
            + TF("rnw_done_body",
                 "🏷 کانفیگ: {name}\n"
                 "📥 حجم کل جدید: {gb}\n"
                 "♻️ ترافیک مصرف‌شده ریست شد\n"
                 "📅 انقضای جدید: {expiry}\n\n",
                 name=(order.get("config_name") or email),
                 gb=gb_txt, expiry=str(result.get("new_expiry", "—")))
            + T("rnw_done_hint", "لینک کانفیگ شما تغییری نکرده و همان قبلی است. ✅")
        )
        await bot.send_message(chat_id=order["telegram_id"], text=msg)
    except Exception:
        pass
    return result
