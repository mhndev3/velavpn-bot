"""
user_extra.py — اشتراک‌های من (از جدول subscriptions) + درخواست همکاری + دعوت دوستان
"""
import io
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from config.settings import ADMIN_IDS
from database.db import (
    get_connection, get_sub_admin, add_sub_admin,
    get_user_subscriptions, get_subscription_by_order,
)
from handlers.btn_filter import Btn
from services.ui_texts import T

router = Router()

_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _fa(value) -> str:
    # اعداد لاتین می‌مانند
    return str(value)


def _btn(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


def _make_qr(text: str):
    try:
        import qrcode
        img = qrcode.make(text)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except ImportError:
        return None


_LINK_PREFIXES = ("vless://", "vmess://", "ss://", "trojan://", "tuic://", "hysteria://", "hysteria2://")


def _extract_config_link(sub: dict) -> str:
    txt = (sub.get("delivery_text") or "").strip()
    if not txt:
        return ""
    for token in txt.replace("\n", " ").split(" "):
        token = token.strip()
        if token.startswith(_LINK_PREFIXES):
            return token
    return txt


def _remaining_text(sub: dict) -> str:
    exp = sub.get("expires_at")
    if not exp:
        return "♾ بدون انقضا"
    try:
        dt = datetime.strptime(str(exp)[:19], "%Y-%m-%d %H:%M:%S")
        delta = dt - datetime.now()
        if delta.total_seconds() <= 0:
            return "⛔️ منقضی شده"
        days = delta.days
        hours = int(delta.seconds // 3600)
        if days > 0:
            return "⏳ باقیمانده: " + _fa(days) + " روز و " + _fa(hours) + " ساعت"
        return "⏳ باقیمانده: " + _fa(hours) + " ساعت"
    except Exception:
        return "📅 انقضا: " + str(exp)


async def _send_subs_list(target, uid: int):
    """لیست اشتراک‌ها را می‌فرستد (هم از دکمهٔ منو، هم بعد از بازگشت)."""
    subs = get_user_subscriptions(uid)
    _back = [_btn(T("subs_btn_back", "⬅️ بازگشت"), "u:menu")]
    if not subs:
        return await target.answer(
            T("subs_empty", "📦 شما هنوز اشتراک فعالی ندارید.\n\nبرای خرید گزینه «⚡ خرید کانفیگ» را بزنید."),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[_back])
        )
    item_emoji = T("subs_emoji_item", "📦")
    kb_rows = []
    for s in subs:
        _m = _sub_meta(uid, s["order_id"])
        title = (_m.get("config_name") or s.get("plan_title")
                 or s.get("service_name") or "اشتراک").strip()
        if len(title) > 40:
            title = title[:40] + "…"
        kb_rows.append([_btn(item_emoji + " " + title, "mysub:" + str(s["order_id"]))])
    kb_rows.append(_back)
    text = (T("subs_title", "📦 اشتراک‌های فعال شما") +
            " (" + _fa(len(subs)) + " مورد):\n\n" +
            T("subs_hint", "برای مشاهده جزئیات، حجم و کانفیگ، انتخاب کنید:"))
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    sent = False
    try:
        from services.banner_service import send_banner
        sent = await send_banner(target, "subs", caption=text, reply_markup=kb)
    except Exception:
        sent = False
    if not sent:
        await target.answer(text, reply_markup=kb)


# ─── اشتراک‌های من ───────────────────────────────────────────
@router.message(Btn("btn_subs", "📦 اشتراک‌های من"))
async def my_subscriptions(msg: Message):
    await _send_subs_list(msg, msg.from_user.id)


def _sub_meta(telegram_id: int, order_id: int) -> dict:
    """نام کانفیگِ انتخابیِ مشتری، حجم پلن، مدت و لوکیشن (سرور) را برمی‌گرداند."""
    meta = {"config_name": "", "gb": 0, "days": 0, "location": ""}
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT o.config_name, o.duration_days AS o_days, o.plan_id,
                      p.traffic_gb, p.duration_days AS p_days,
                      xs.label AS server_label
               FROM orders o
               LEFT JOIN plans p ON p.id = o.plan_id
               LEFT JOIN xui_servers xs ON xs.id = p.server_id
               WHERE o.id = ? AND o.telegram_id = ?""",
            (order_id, telegram_id),
        )
        r = cur.fetchone()
        # اگر نام کانفیگ در سفارش نبود، از ایمیلِ اکانت پنل بخوان
        cur.execute(
            "SELECT xa.email, xa.server_id, xs.label AS acc_label "
            "FROM xui_accounts xa LEFT JOIN xui_servers xs ON xs.id = xa.server_id "
            "WHERE xa.order_id = ? AND xa.telegram_id = ?",
            (order_id, telegram_id),
        )
        xa = cur.fetchone()
        # مدت از روی اشتراک (برای کانفیگ‌های واردشده که پلن ندارند)
        cur.execute(
            "SELECT created_at, expires_at FROM subscriptions "
            "WHERE order_id = ? AND telegram_id = ? ORDER BY id DESC LIMIT 1",
            (order_id, telegram_id),
        )
        sb = cur.fetchone()
        conn.close()
        if r:
            d = dict(r)
            meta["config_name"] = (d.get("config_name") or "").strip()
            meta["gb"] = int(d.get("traffic_gb") or 0)
            meta["days"] = int(d.get("p_days") or d.get("o_days") or 0)
            meta["location"] = (d.get("server_label") or "").strip()
        if not meta["config_name"] and xa and xa["email"]:
            meta["config_name"] = str(xa["email"]).strip()
        # fallback لوکیشن: از سرورِ اکانتِ ساخته‌شده در پنل
        if not meta["location"] and xa and xa["acc_label"]:
            meta["location"] = str(xa["acc_label"]).strip()
        # fallback مدت: فاصلهٔ ساخت تا انقضای اشتراک
        if not meta["days"] and sb and sb["created_at"] and sb["expires_at"]:
            try:
                c = datetime.strptime(str(sb["created_at"])[:19], "%Y-%m-%d %H:%M:%S")
                e = datetime.strptime(str(sb["expires_at"])[:19], "%Y-%m-%d %H:%M:%S")
                meta["days"] = max(0, (e - c).days)
            except Exception:
                pass
    except Exception:
        pass
    return meta


def _months_label(days: int) -> str:
    d = int(days or 0)
    if d <= 0:
        return "بدون انقضا"
    months = round(d / 30)
    if months >= 1:
        return "\u200f" + str(months) + " ماهه"
    return "\u200f" + str(d) + " روزه"


def _remaining_only(sub: dict) -> str:
    """فقط مقدار زمان باقیمانده (بدون برچسب) — با ایموجی تقویم در برچسب نمایش داده می‌شود."""
    exp = sub.get("expires_at")
    if not exp:
        return "♾ بدون انقضا"
    try:
        dt = datetime.strptime(str(exp)[:19], "%Y-%m-%d %H:%M:%S")
        delta = dt - datetime.now()
        if delta.total_seconds() <= 0:
            return "⛔️ منقضی شده"
        days = delta.days
        hours = int(delta.seconds // 3600)
        if days > 0:
            return "\u200f" + _fa(days) + " روز و " + _fa(hours) + " ساعت"
        return "\u200f" + _fa(hours) + " ساعت"
    except Exception:
        return str(exp)


async def _build_sub_detail(telegram_id: int, order_id: int):
    sub = get_subscription_by_order(telegram_id, order_id)
    if not sub:
        return None, None
    config_link = _extract_config_link(sub)
    meta = _sub_meta(telegram_id, order_id)

    remain_line = ""
    pct_line = ""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT email, server_id FROM xui_accounts WHERE order_id = ? AND telegram_id = ?",
            (order_id, telegram_id),
        )
        xa = cursor.fetchone()
        conn.close()
        if xa and xa["email"]:
            from services.xui_service import get_account_stats
            stats = await get_account_stats(xa["email"], xa["server_id"])
            if stats:
                used = stats.get("up", 0) + stats.get("down", 0)
                total = stats.get("total", 0)
                if total > 0:
                    # اگر پلن حجم نداشت (مثلاً کانفیگ واردشده)، حجم را از پنل بگیر
                    if not meta.get("gb"):
                        meta["gb"] = int(round(total / (1024 ** 3)))
                    remain_gb = round((total - used) / (1024 ** 3), 2)
                    pct = min(100, int(used / total * 100))
                    bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                    remain_line = "\u200f" + _fa(remain_gb) + " گیگ"
                    pct_line = "[" + bar + "] " + _fa(pct) + "%"
                else:
                    remain_line = "♾ نامحدود"
    except Exception:
        pass

    gb_txt = ("\u200f" + _fa(meta["gb"]) + " گیگ") if meta["gb"] else "نامحدود"

    text = (
        T("subs_lbl_name", "🏷 نام سرویس:") + " " + (meta["config_name"] or "—") + "\n\n"
        + T("subs_lbl_service", "📦 سرویس:") + " " + gb_txt + "\n\n"
        + T("subs_lbl_plan", "💠 پلن:") + " " + _months_label(meta["days"]) + "\n\n"
        + T("subs_lbl_location", "🌍 لوکیشن:") + " " + (meta["location"] or "—") + "\n\n"
        + T("subs_lbl_remain", "📅 زمان باقی مونده:") + " " + _remaining_only(sub) + "\n\n"
    )
    if remain_line:
        text += T("subs_lbl_gb", "📥 باقی مانده حجم:") + " " + remain_line + "\n\n"
    if pct_line:
        text += T("subs_lbl_percent", "📊 درصد مصرف شده:") + "\n" + pct_line + "\n\n"
    if config_link:
        text += T("subs_lbl_link", "🔗 لینک کانفیگ:") + "\n<code>" + config_link + "</code>"
    elif sub.get("delivery_file_id"):
        text += "📎 کانفیگ به‌صورت فایل ارسال شده — دکمه زیر را بزنید."

    rows = []
    if config_link.startswith(_LINK_PREFIXES):
        rows.append([_btn(T("subs_btn_qr", "📱 دریافت QR Code"), "mysub_qr:" + str(order_id))])
    if sub.get("delivery_file_id"):
        rows.append([_btn(T("subs_btn_file", "📎 دریافت مجدد فایل کانفیگ"), "mysub_file:" + str(order_id))])
    rows.append([_btn(T("subs_btn_refresh", "🔄 بروزرسانی وضعیت"), "mysub:" + str(order_id))])
    rows.append([_btn(T("subs_btn_back", "⬅️ بازگشت"), "mysub_back")])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("mysub:"))
async def my_sub_detail(cb: CallbackQuery):
    order_id = int(cb.data.split(":")[1])
    await cb.answer("⏳ در حال دریافت اطلاعات...", show_alert=False)
    text, kb = await _build_sub_detail(cb.from_user.id, order_id)
    if not text:
        return await cb.answer("اشتراک پیدا نشد", show_alert=True)
    try:
        # اگر پیام قبلی متنی است ویرایشش کن؛ اگر عکس/بنر است پاکش کن تا چت شلوغ نشود
        if cb.message.photo or cb.message.caption is not None:
            raise ValueError("photo message")
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("mysub_qr:"))
async def my_sub_qr(cb: CallbackQuery):
    order_id = int(cb.data.split(":")[1])
    sub = get_subscription_by_order(cb.from_user.id, order_id)
    link = _extract_config_link(sub) if sub else ""
    if not link:
        return await cb.answer("لینک کانفیگ موجود نیست", show_alert=True)
    await cb.answer("⏳ در حال ساخت QR...", show_alert=False)
    qr_bytes = _make_qr(link)
    if qr_bytes:
        await cb.bot.send_photo(
            chat_id=cb.from_user.id,
            photo=BufferedInputFile(qr_bytes, filename="qr.png"),
            caption="📱 اشتراک #" + _fa(order_id),
        )
    else:
        await cb.message.reply("📱 لینک کانفیگ:\n\n<code>" + link + "</code>")


@router.callback_query(F.data.startswith("mysub_file:"))
async def my_sub_file(cb: CallbackQuery):
    order_id = int(cb.data.split(":")[1])
    sub = get_subscription_by_order(cb.from_user.id, order_id)
    if not sub or not sub.get("delivery_file_id"):
        return await cb.answer("فایلی برای این اشتراک موجود نیست", show_alert=True)
    await cb.answer()
    fid = sub["delivery_file_id"]
    ft = sub.get("delivery_file_type")
    cap = sub.get("delivery_text") or "📎 کانفیگ شما"
    try:
        if ft == "photo":
            await cb.bot.send_photo(cb.from_user.id, fid, caption=cap)
        elif ft == "document":
            await cb.bot.send_document(cb.from_user.id, fid, caption=cap)
        elif ft == "video":
            await cb.bot.send_video(cb.from_user.id, fid, caption=cap)
        else:
            await cb.message.answer(cap)
    except Exception:
        await cb.message.answer("❌ ارسال فایل ناموفق بود.")


@router.callback_query(F.data == "u:subs")
async def subs_from_profile(cb: CallbackQuery):
    """ورود به «کانفیگ‌های من» از پنل کاربری."""
    try:
        await cb.message.delete()
    except Exception:
        pass
    await _send_subs_list(cb.message, cb.from_user.id)
    await cb.answer()


@router.callback_query(F.data == "mysub_back")
async def my_sub_back(cb: CallbackQuery):
    # پیام جزئیات پاک می‌شود تا چت شلوغ نشود
    try:
        await cb.message.delete()
    except Exception:
        pass
    await _send_subs_list(cb.message, cb.from_user.id)
    await cb.answer()


# ─── دعوت دوستان (رفرال) ────────────────────────────────────
@router.message(Btn("btn_referral", "🎁 دعوت دوستان"))
async def referral_menu(msg: Message):
    from services.referral_service import get_or_create_referral_code, get_referral_stats
    code = get_or_create_referral_code(msg.from_user.id)
    stats = get_referral_stats(msg.from_user.id)

    text = (
        "🎁 دعوت دوستان\n\n"
        "کد دعوت شما: <code>" + code + "</code>\n\n"
        "📊 آمار:\n"
        "👥 تعداد معرفی‌ها: " + str(stats.get("referred_count", 0)) + "\n"
        "💰 کل کمیسیون: " + str(stats.get("total_commission", 0)) + " تومان\n\n"
        "دوستان رو دعوت کن و کمیسیون بگیر!\n\n"
        "لینک دعوت:\nhttps://t.me/?start=ref_" + code
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [_btn("📋 کپی کد دعوت", "referral:info")],
        [_btn("⬅️ بازگشت", "u:menu")],
    ])
    await msg.answer(text, reply_markup=kb)


@router.callback_query(F.data == "referral:info")
async def referral_info(cb: CallbackQuery):
    from services.referral_service import get_or_create_referral_code
    code = get_or_create_referral_code(cb.from_user.id)
    await cb.answer(
        "کد دعوت شما: " + code + "\n\n"
        "این کد رو به دوستانت بده تا وقتی ثبت‌نام می‌کنن به عنوان معرف ثبت بشی",
        show_alert=True
    )


# ─── درخواست همکاری (تیکت) ───────────────────────────────────
class PartnerStates(StatesGroup):
    waiting_message = State()


@router.message(Btn("btn_coop", "🤝 درخواست همکاری"))
async def partnership_start(msg: Message, state: FSMContext):
    if get_sub_admin(msg.from_user.id):
        return await msg.answer(
            "✅ شما در حال حاضر همکار (ساب‌ادمین) هستید.\n"
            "برای مشاهده پنل خود دکمه آمار فروش را بزنید."
        )
    await state.clear()
    await msg.answer(
        "🤝 درخواست همکاری\n\n"
        "یک پیام کوتاه درباره خودت و روش کارت بنویس.\n"
        "مثلاً: من در کانال X فعالم و می‌تونم ماهی Y تا بفروشم.\n\n"
        "درخواستت به صورت تیکت برای مدیر ارسال می‌شه.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [_btn("⬅️ بازگشت", "u:menu")]
        ]),
    )
    await state.set_state(PartnerStates.waiting_message)


@router.message(PartnerStates.waiting_message)
async def partnership_submit(msg: Message, state: FSMContext):
    await state.clear()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO tickets (telegram_id, subject, status)
        VALUES (?, ?, 'open')
        """,
        (msg.from_user.id, "درخواست همکاری")
    )
    ticket_id = cursor.lastrowid
    cursor.execute(
        """
        INSERT INTO ticket_messages (ticket_id, sender_id, sender_type, message_text)
        VALUES (?, ?, 'user', ?)
        """,
        (ticket_id, msg.from_user.id, msg.text)
    )
    conn.commit()
    conn.close()

    admin_text = (
        "🤝 درخواست همکاری جدید (تیکت #" + str(ticket_id) + ")\n\n"
        "نام: " + str(msg.from_user.full_name) + "\n"
        "آیدی: " + str(msg.from_user.id) + "\n"
        "یوزرنیم: @" + (msg.from_user.username or "ندارد") + "\n\n"
        "پیام:\n" + str(msg.text)
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [_btn("✅ تأیید همکاری", "partner_ok:" + str(msg.from_user.id) + ":" + str(ticket_id)),
         _btn("❌ رد", "partner_no:" + str(msg.from_user.id) + ":" + str(ticket_id))],
    ])

    for admin_id in ADMIN_IDS:
        try:
            await msg.bot.send_message(chat_id=admin_id, text=admin_text, reply_markup=kb)
        except Exception:
            pass

    await msg.answer(
        "✅ درخواست شما (تیکت #" + str(ticket_id) + ") ارسال شد.\n"
        "منتظر پاسخ مدیر باشید."
    )


@router.callback_query(F.data.startswith("partner_ok:"))
async def partner_approve(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("دسترسی ندارید", show_alert=True)
    parts = cb.data.split(":")
    target_id = int(parts[1])
    ticket_id = int(parts[2]) if len(parts) > 2 else 0

    add_sub_admin(
        telegram_id=target_id, full_name="همکار", username="",
        added_by=cb.from_user.id, commission_percent=0, note="از طریق درخواست همکاری"
    )
    await cb.answer("✅ تأیید شد", show_alert=True)
    try:
        new_text = (cb.message.text or "") + "\n\n✅ تأیید شد توسط ادمین"
        await cb.message.edit_text(new_text)
    except Exception:
        pass
    try:
        await cb.bot.send_message(
            chat_id=target_id,
            text="🎉 درخواست همکاری شما تأیید شد!\nاکنون به عنوان همکار ثبت شدید."
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("partner_no:"))
async def partner_reject(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("دسترسی ندارید", show_alert=True)
    parts = cb.data.split(":")
    target_id = int(parts[1])
    await cb.answer("❌ رد شد", show_alert=True)
    try:
        new_text = (cb.message.text or "") + "\n\n❌ رد شد توسط ادمین"
        await cb.message.edit_text(new_text)
    except Exception:
        pass
    try:
        await cb.bot.send_message(
            chat_id=target_id,
            text="متأسفانه درخواست همکاری شما در حال حاضر تأیید نشد."
        )
    except Exception:
        pass
