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
from services.ui_texts import T, TF

router = Router()

_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _fa(value) -> str:
    # اعداد لاتین می‌مانند
    return str(value)


def _btn(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


def _parse_dt(value):
    """پارس تاریخ با پشتیبانی از فرمت‌های مختلف (با/بدون ساعت). None اگر ناموفق."""
    if not value:
        return None
    s = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    # تلاش نهایی: فقط بخش تاریخ (۱۰ کاراکتر اول)
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d")
    except Exception:
        return None


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
        return T("u_no_expiry_long", "♾ بدون انقضا")
    dt = _parse_dt(exp)
    if not dt:
        return TF("u_expiry_at", "📅 انقضا: {date}", date=exp)
    delta = dt - datetime.now()
    if delta.total_seconds() <= 0:
        return T("u_expired", "⛔️ منقضی شده")
    days = delta.days
    hours = int(delta.seconds // 3600)
    if days > 0:
        return TF("u_remaining_dh", "⏳ باقیمانده: {days} روز و {hours} ساعت",
                  days=_fa(days), hours=_fa(hours))
    return TF("u_remaining_h", "⏳ باقیمانده: {hours} ساعت", hours=_fa(hours))


def _order_accounts(telegram_id: int, order_id: int) -> list:
    """
    همهٔ اکانت‌های پنل مربوط به یک سفارش را برمی‌گرداند.

    سفارش‌های چندتایی (quantity > 1) چند اکانت واقعی می‌سازند ولی فقط یک ردیف
    در جدول subscriptions دارند؛ پس لیست «اشتراک‌های من» باید روی اکانت‌ها باز
    شود، نه روی اشتراک‌ها، وگرنه فقط اولی دیده می‌شود.
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT xa.id, xa.email, xa.server_id, xa.config_link, xa.traffic_gb, "
            "       xa.expires_at, xs.label AS server_label "
            "FROM xui_accounts xa LEFT JOIN xui_servers xs ON xs.id = xa.server_id "
            "WHERE xa.order_id = ? AND xa.telegram_id = ? "
            "  AND COALESCE(xa.status, '') != 'deleted' "
            "ORDER BY xa.id",
            (order_id, telegram_id),
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception:
        return []


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
    count = 0
    for s in subs:
        oid = s["order_id"]
        accounts = _order_accounts(uid, oid)
        base = (s.get("plan_title") or s.get("service_name")
                or T("subs_item_fallback", "اشتراک")).strip()

        if len(accounts) <= 1:
            # حالت معمول: یک کانفیگ برای این سفارش
            _m = _sub_meta(uid, oid)
            title = (_m.get("config_name") or base).strip()
            if len(title) > 40:
                title = title[:40] + "…"
            kb_rows.append([_btn(item_emoji + " " + title, "mysub:" + str(oid))])
            count += 1
        else:
            # سفارش چندتایی: برای هر کانفیگ یک دکمهٔ جدا
            for idx, acc in enumerate(accounts, 1):
                _m = _sub_meta(uid, oid, acc["id"])
                title = (_m.get("config_name") or acc.get("email") or base).strip()
                if len(title) > 34:
                    title = title[:34] + "…"
                title += " (" + _fa(idx) + ")"
                kb_rows.append([_btn(item_emoji + " " + title,
                                     "mysub:" + str(oid) + ":" + str(acc["id"]))])
                count += 1

    kb_rows.append(_back)
    text = TF("subs_list_title", "{title} ({count} مورد):\n\n{hint}",
              title=T("subs_title", "📦 اشتراک‌های فعال شما"),
              count=_fa(count),
              hint=T("subs_hint", "برای مشاهده جزئیات، حجم و کانفیگ، انتخاب کنید:"))
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


def _sub_meta(telegram_id: int, order_id: int, account_id: int = None) -> dict:
    """
    نام کانفیگِ انتخابیِ مشتری، حجم پلن، مدت و لوکیشن (سرور) را برمی‌گرداند.

    account_id اختیاری است: در سفارش‌های چندتایی مشخص می‌کند کدام اکانت مد نظر
    است؛ اگر داده نشود اولین اکانت سفارش استفاده می‌شود.
    """
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
        # برای سفارش‌های چندتایی، اکانت مشخص (account_id) خوانده می‌شود
        if account_id:
            cur.execute(
                "SELECT xa.email, xa.server_id, xa.traffic_gb AS acc_gb, xa.expires_at AS acc_exp, "
                "xs.label AS acc_label "
                "FROM xui_accounts xa LEFT JOIN xui_servers xs ON xs.id = xa.server_id "
                "WHERE xa.id = ? AND xa.telegram_id = ?",
                (account_id, telegram_id),
            )
        else:
            cur.execute(
                "SELECT xa.email, xa.server_id, xa.traffic_gb AS acc_gb, xa.expires_at AS acc_exp, "
                "xs.label AS acc_label "
                "FROM xui_accounts xa LEFT JOIN xui_servers xs ON xs.id = xa.server_id "
                "WHERE xa.order_id = ? AND xa.telegram_id = ? ORDER BY xa.id",
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
        # حجم واقعی: اگر اکانت پنل مقدار به‌روز دارد (مثلاً پس از تمدید)، آن را ترجیح بده
        if xa and xa["acc_gb"] is not None:
            try:
                _accgb = int(xa["acc_gb"])
                if _accgb > 0:
                    meta["gb"] = _accgb
            except Exception:
                pass
        # fallback لوکیشن: از سرورِ اکانتِ ساخته‌شده در پنل
        if not meta["location"] and xa and xa["acc_label"]:
            meta["location"] = str(xa["acc_label"]).strip()
        # مدت واقعی «پلن»: انقضای به‌روز را از اکانت پنل (که پس از تمدید آپدیت
        # می‌شود) و در نبود آن از اشتراک می‌گیریم. مدت = فاصلهٔ ساخت تا انقضا،
        # که با هر تمدید بزرگ‌تر می‌شود (مثلاً ۱ماهه + تمدید ۱ماهه = ۲ماهه).
        _acc_exp = (xa["acc_exp"] if xa else None) or (sb["expires_at"] if sb else None)
        _created = sb["created_at"] if sb else None
        e = _parse_dt(_acc_exp)
        c = _parse_dt(_created)
        if e and c:
            _d = (e - c).days
            if _d > 0:
                meta["days"] = _d
    except Exception:
        pass
    return meta


def _months_label(days: int) -> str:
    d = int(days or 0)
    if d <= 0:
        return T("u_no_expiry_plain", "بدون انقضا")
    months = round(d / 30)
    if months >= 1:
        return "\u200f" + str(months) + T("u_month_suffix", " ماهه")
    return "\u200f" + str(d) + T("u_day_suffix", " روزه")


def _remaining_only(sub: dict) -> str:
    """فقط مقدار زمان باقیمانده (بدون برچسب) — با ایموجی تقویم در برچسب نمایش داده می‌شود."""
    exp = sub.get("expires_at")
    if not exp:
        return T("u_no_expiry_long", "♾ بدون انقضا")
    dt = _parse_dt(exp)
    if not dt:
        return str(exp)
    delta = dt - datetime.now()
    if delta.total_seconds() <= 0:
        return T("u_expired", "⛔️ منقضی شده")
    days = delta.days
    hours = int(delta.seconds // 3600)
    if days > 0:
        return "\u200f" + TF("u_dh", "{days} روز و {hours} ساعت",
                             days=_fa(days), hours=_fa(hours))
    return "\u200f" + TF("u_h", "{hours} ساعت", hours=_fa(hours))


async def _build_sub_detail(telegram_id: int, order_id: int, account_id: int = None):
    sub = get_subscription_by_order(telegram_id, order_id)
    if not sub:
        return None, None
    meta = _sub_meta(telegram_id, order_id, account_id)

    # اکانت هدف: در سفارش چندتایی همان اکانت انتخاب‌شده، وگرنه اولین اکانت سفارش
    accounts = _order_accounts(telegram_id, order_id)
    acc = None
    if account_id:
        acc = next((a for a in accounts if int(a["id"]) == int(account_id)), None)
    if not acc and accounts:
        acc = accounts[0]

    # لینک: برای هر اکانت لینک خودش (سفارش چندتایی)، وگرنه از متن تحویل
    config_link = ""
    if acc and (acc.get("config_link") or "").strip():
        config_link = acc["config_link"].strip()
    if not config_link:
        config_link = _extract_config_link(sub)

    # پسوند شماره در عنوان برای سفارش‌های چندتایی
    idx_suffix = ""
    if acc and len(accounts) > 1:
        try:
            idx_suffix = " (" + _fa(accounts.index(acc) + 1) + "/" + _fa(len(accounts)) + ")"
        except Exception:
            idx_suffix = ""

    remain_line = ""
    pct_line = ""
    try:
        if acc and acc.get("email"):
            from services.xui_service import get_account_stats
            stats = await get_account_stats(acc["email"], acc["server_id"])
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
                    remain_line = "\u200f" + _fa(remain_gb) + T("u_gig", " گیگ")
                    pct_line = "[" + bar + "] " + _fa(pct) + "%"
                else:
                    remain_line = T("u_unlimited_long", "♾ نامحدود")
    except Exception:
        pass

    gb_txt = ("\u200f" + _fa(meta["gb"]) + T("u_gig", " گیگ")) if meta["gb"] else T("u_unlimited", "نامحدود")

    # شناسهٔ مسیرِ کالبک‌ها: با اکانت مشخص یا بدون آن
    ref = str(order_id) + ((":" + str(acc["id"])) if (acc and len(accounts) > 1) else "")

    text = (
        T("subs_lbl_name", "🏷 نام سرویس:") + " " + (meta["config_name"] or "—") + idx_suffix + "\n\n"
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
        text += T("subs_file_note", "📎 کانفیگ به‌صورت فایل ارسال شده — دکمه زیر را بزنید.")

    rows = []
    if config_link.startswith(_LINK_PREFIXES):
        rows.append([_btn(T("subs_btn_qr", "📱 دریافت QR Code"), "mysub_qr:" + ref)])
    if sub.get("delivery_file_id"):
        rows.append([_btn(T("subs_btn_file", "📎 دریافت مجدد فایل کانفیگ"), "mysub_file:" + ref)])
    rows.append([_btn(T("subs_btn_refresh", "🔄 بروزرسانی وضعیت"), "mysub:" + ref)])
    rows.append([_btn(T("subs_btn_delete", "🗑 حذف این کانفیگ"), "mysub_del:" + ref)])
    rows.append([_btn(T("subs_btn_back", "⬅️ بازگشت"), "mysub_back")])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def _parse_ref(data: str):
    """
    'prefix:order_id' یا 'prefix:order_id:account_id' را می‌شکند.
    خروجی: (order_id, account_id|None)
    """
    parts = data.split(":")
    try:
        oid = int(parts[1])
    except (IndexError, ValueError):
        return None, None
    aid = None
    if len(parts) > 2 and parts[2].strip():
        try:
            aid = int(parts[2])
        except ValueError:
            aid = None
    return oid, aid


@router.callback_query(F.data.startswith("mysub:"))
async def my_sub_detail(cb: CallbackQuery):
    order_id, account_id = _parse_ref(cb.data)
    if order_id is None:
        return await cb.answer()
    await cb.answer(T("subs_loading", "⏳ در حال دریافت اطلاعات..."), show_alert=False)
    text, kb = await _build_sub_detail(cb.from_user.id, order_id, account_id)
    if not text:
        return await cb.answer(T("subs_not_found", "اشتراک پیدا نشد"), show_alert=True)
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


@router.callback_query(F.data.startswith("mysub_del:"))
async def my_sub_delete_confirm(cb: CallbackQuery):
    order_id, account_id = _parse_ref(cb.data)
    if order_id is None:
        return await cb.answer()
    ref = str(order_id) + ((":" + str(account_id)) if account_id else "")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [_btn(T("subs_del_yes", "✅ بله، حذف کن"), "mysub_delok:" + ref)],
        [_btn(T("subs_del_no", "❌ انصراف"), "mysub:" + ref)],
    ])
    txt = T("subs_del_confirm",
            "⚠️ آیا مطمئنید می‌خواهید این کانفیگ را حذف کنید؟\n"
            "این عمل قابل بازگشت نیست و کانفیگ از سرور هم پاک می‌شود.")
    try:
        if cb.message.photo or cb.message.caption is not None:
            raise ValueError("photo")
        await cb.message.edit_text(txt, reply_markup=kb)
    except Exception:
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(txt, reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data.startswith("mysub_delok:"))
async def my_sub_delete_do(cb: CallbackQuery):
    order_id, account_id = _parse_ref(cb.data)
    if order_id is None:
        return await cb.answer()
    await cb.answer(T("subs_deleting", "⏳ در حال حذف..."), show_alert=False)
    from database.db import get_xui_account_by_order, get_connection

    # اکانت هدف: در سفارش چندتایی فقط همان اکانت حذف می‌شود
    accounts = _order_accounts(cb.from_user.id, order_id)
    acc = None
    if account_id:
        acc = next((a for a in accounts if int(a["id"]) == int(account_id)), None)
    if not acc:
        acc = accounts[0] if accounts else get_xui_account_by_order(order_id)

    # حذف از پنل
    if acc and acc.get("email") and acc.get("server_id"):
        try:
            from services.xui_service import delete_account
            await delete_account(acc["email"], acc["server_id"])
        except Exception:
            pass

    # حذف از دیتابیس
    try:
        conn = get_connection(); cur = conn.cursor()
        if acc and acc.get("id"):
            cur.execute("UPDATE xui_accounts SET status='deleted' WHERE id=? AND telegram_id=?",
                        (acc["id"], cb.from_user.id))
        else:
            cur.execute("UPDATE xui_accounts SET status='deleted' WHERE order_id=? AND telegram_id=?",
                        (order_id, cb.from_user.id))
        # اشتراک فقط وقتی بسته می‌شود که کانفیگ فعال دیگری از این سفارش نمانده باشد
        cur.execute(
            "SELECT COUNT(*) AS c FROM xui_accounts "
            "WHERE order_id=? AND telegram_id=? AND COALESCE(status,'') != 'deleted'",
            (order_id, cb.from_user.id),
        )
        remaining = cur.fetchone()["c"]
        if remaining == 0:
            cur.execute("UPDATE subscriptions SET status='deleted' WHERE order_id=? AND telegram_id=?",
                        (order_id, cb.from_user.id))
        conn.commit(); conn.close()
    except Exception:
        pass
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.message.answer(T("subs_del_done", "🗑 کانفیگ با موفقیت حذف شد."))
    await _send_subs_list(cb.message, cb.from_user.id)


async def my_sub_qr(cb: CallbackQuery):
    order_id, account_id = _parse_ref(cb.data)
    if order_id is None:
        return await cb.answer()
    sub = get_subscription_by_order(cb.from_user.id, order_id)
    # لینک اکانت مشخص (سفارش چندتایی)، وگرنه از متن تحویل
    link = ""
    accounts = _order_accounts(cb.from_user.id, order_id)
    acc = None
    if account_id:
        acc = next((a for a in accounts if int(a["id"]) == int(account_id)), None)
    if not acc and accounts:
        acc = accounts[0]
    if acc and (acc.get("config_link") or "").strip():
        link = acc["config_link"].strip()
    if not link:
        link = _extract_config_link(sub) if sub else ""
    if not link:
        return await cb.answer(T("subs_no_link", "لینک کانفیگ موجود نیست"), show_alert=True)
    await cb.answer(T("subs_qr_making", "⏳ در حال ساخت QR..."), show_alert=False)
    qr_bytes = _make_qr(link)
    if qr_bytes:
        await cb.bot.send_photo(
            chat_id=cb.from_user.id,
            photo=BufferedInputFile(qr_bytes, filename="qr.png"),
            caption=TF("subs_qr_caption", "📱 اشتراک #{order_id}", order_id=_fa(order_id)),
        )
    else:
        await cb.message.reply(TF("subs_link_only", "📱 لینک کانفیگ:\n\n<code>{link}</code>", link=link))


@router.callback_query(F.data.startswith("mysub_file:"))
async def my_sub_file(cb: CallbackQuery):
    order_id, _acc = _parse_ref(cb.data)
    if order_id is None:
        return await cb.answer()
    sub = get_subscription_by_order(cb.from_user.id, order_id)
    if not sub or not sub.get("delivery_file_id"):
        return await cb.answer(T("subs_no_file", "فایلی برای این اشتراک موجود نیست"), show_alert=True)
    await cb.answer()
    fid = sub["delivery_file_id"]
    ft = sub.get("delivery_file_type")
    cap = sub.get("delivery_text") or T("subs_file_caption", "📎 کانفیگ شما")
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
        await cb.message.answer(T("subs_file_failed", "❌ ارسال فایل ناموفق بود."))


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

    text = TF(
        "ref_title",
        "🎁 دعوت دوستان\n\n"
        "کد دعوت شما: <code>{code}</code>\n\n"
        "📊 آمار:\n"
        "👥 تعداد معرفی‌ها: {count}\n"
        "💰 کل کمیسیون: {commission} تومان\n\n"
        "دوستان رو دعوت کن و کمیسیون بگیر!\n\n"
        "لینک دعوت:\nhttps://t.me/?start=ref_{code}",
        code=code,
        count=stats.get("referred_count", 0),
        commission=stats.get("total_commission", 0),
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [_btn(T("ref_btn_copy", "📋 کپی کد دعوت"), "referral:info")],
        [_btn(T("ref_btn_back", "⬅️ بازگشت"), "u:menu")],
    ])
    await msg.answer(text, reply_markup=kb)


@router.callback_query(F.data == "referral:info")
async def referral_info(cb: CallbackQuery):
    from services.referral_service import get_or_create_referral_code
    code = get_or_create_referral_code(cb.from_user.id)
    await cb.answer(
        TF("ref_info_alert",
           "کد دعوت شما: {code}\n\n"
           "این کد رو به دوستانت بده تا وقتی ثبت‌نام می‌کنن به عنوان معرف ثبت بشی",
           code=code),
        show_alert=True
    )


# ─── درخواست همکاری (تیکت) ───────────────────────────────────
class PartnerStates(StatesGroup):
    waiting_message = State()


@router.message(Btn("btn_coop", "🤝 درخواست همکاری"))
async def partnership_start(msg: Message, state: FSMContext):
    if get_sub_admin(msg.from_user.id):
        return await msg.answer(
            T("coop_already",
              "✅ شما در حال حاضر همکار (ساب‌ادمین) هستید.\n"
              "برای مشاهده پنل خود دکمه آمار فروش را بزنید.")
        )
    await state.clear()
    await msg.answer(
        T("coop_ask",
          "🤝 درخواست همکاری\n\n"
          "یک پیام کوتاه درباره خودت و روش کارت بنویس.\n"
          "مثلاً: من در کانال X فعالم و می‌تونم ماهی Y تا بفروشم.\n\n"
          "درخواستت به صورت تیکت برای مدیر ارسال می‌شه."),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [_btn(T("coop_btn_back", "⬅️ بازگشت"), "u:menu")]
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
        TF("coop_sent",
           "✅ درخواست شما (تیکت #{ticket_id}) ارسال شد.\n"
           "منتظر پاسخ مدیر باشید.",
           ticket_id=ticket_id)
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
            text=T("coop_approved_user", "🎉 درخواست همکاری شما تأیید شد!\nاکنون به عنوان همکار ثبت شدید.")
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
            text=T("coop_rejected_user", "متأسفانه درخواست همکاری شما در حال حاضر تأیید نشد.")
        )
    except Exception:
        pass
