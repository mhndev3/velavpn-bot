"""
user_config_update.py — دریافت کانفیگ آپدیت‌شده
از اشتراک‌های فعال (جدول subscriptions) می‌خونه.
اگه برای سفارش، اکانت X-UI با sub_id وجود داشته باشه، لینک جدید از پنل گرفته می‌شه؛
در غیر این صورت همون کانفیگ تحویل‌شده نمایش داده می‌شه.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database.db import get_connection, get_user_subscriptions, get_subscription_by_order
from handlers.btn_filter import Btn

router = Router()

_LINK_PREFIXES = ("vless://", "vmess://", "ss://", "trojan://", "tuic://", "hysteria://", "hysteria2://")


def _btn(t, d):
    return InlineKeyboardButton(text=t, callback_data=d)


def _extract_link(sub: dict) -> str:
    txt = (sub.get("delivery_text") or "").strip()
    if not txt:
        return ""
    for token in txt.replace("\n", " ").split(" "):
        token = token.strip()
        if token.startswith(_LINK_PREFIXES):
            return token
    return txt


def _get_xui_account_by_order(order_id: int, telegram_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT xa.*, s.label as server_label, s.url as server_url,
               s.username as server_user, s.password as server_pass
        FROM xui_accounts xa
        LEFT JOIN xui_servers s ON s.id = xa.server_id
        WHERE xa.order_id = ? AND xa.telegram_id = ?
    """, (order_id, telegram_id))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


async def _fetch_updated_config(acc: dict) -> str | None:
    """دریافت کانفیگ آپدیت‌شده از پنل با همون client_id"""
    server = {
        "id": acc["server_id"],
        "label": acc.get("server_label", ""),
        "url": acc.get("server_url", ""),
        "username": acc.get("server_user", ""),
        "password": acc.get("server_pass", ""),
    }
    try:
        from services.xui_service import XUIClient
        c = XUIClient(server)
        ok, _ = await c.login()
        if not ok:
            await c.close()
            return None
        inbounds = await c.get_inbounds()
        await c.close()
        if not inbounds:
            return None
        target = None
        for ib in inbounds:
            if ib.get("id") == acc.get("xui_inbound_id"):
                target = ib
                break
        if not target:
            target = inbounds[0]
        client_id = acc.get("xui_client_id", "")
        email = acc.get("email", "")
        if not client_id:
            return None
        return c.build_vless_link(target, client_id, email)
    except Exception:
        return None


def _update_config_link(order_id: int, new_link: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE xui_accounts SET config_link = ? WHERE order_id = ?", (new_link, order_id))
    cursor.execute("UPDATE subscriptions SET delivery_text = ? WHERE order_id = ?", (new_link, order_id))
    conn.commit()
    conn.close()


# ─── دکمه دریافت کانفیگ آپدیت‌شده ──────────────────────────
@router.message(Btn("btn_cfg_update", "🔄 دریافت کانفیگ آپدیت‌شده"))
async def config_update_entry(msg: Message):
    subs = get_user_subscriptions(msg.from_user.id)
    _back = [_btn("⬅️ بازگشت", "u:menu")]
    if not subs:
        return await msg.answer(
            "📦 شما هنوز اشتراک فعالی ندارید.\n\nبرای خرید «⚡ خرید کانفیگ» را بزنید.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[_back])
        )
    rows = []
    for s in subs:
        label = (s.get("plan_title") or s.get("service_name") or "اشتراک").strip()
        if len(label) > 40:
            label = label[:40] + "…"
        rows.append([_btn("🔄 " + label, "cfg_update:" + str(s["order_id"]))])
    rows.append(_back)
    await msg.answer(
        "🔄 دریافت کانفیگ آپدیت‌شده\n\n"
        "اگه پنل فیلتر شده یا IP عوض شده، با این دکمه آخرین کانفیگ رو دریافت کن.\n\n"
        "اشتراک خود را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )


@router.callback_query(F.data.startswith("cfg_update:"))
async def config_update_fetch(cb: CallbackQuery):
    order_id = int(cb.data.split(":")[1])
    sub = get_subscription_by_order(cb.from_user.id, order_id)
    if not sub:
        return await cb.answer("اشتراک پیدا نشد", show_alert=True)

    await cb.answer("⏳ در حال دریافت کانفیگ...", show_alert=False)

    config_link = _extract_link(sub)
    status_text = "✅ کانفیگ فعلی شما"

    # اگه اکانت X-UI زنده داریم، تلاش برای گرفتن لینک جدید
    acc = _get_xui_account_by_order(order_id, cb.from_user.id)
    if acc and acc.get("xui_client_id"):
        new_link = await _fetch_updated_config(acc)
        if new_link and new_link != config_link:
            _update_config_link(order_id, new_link)
            config_link = new_link
            status_text = "✅ کانفیگ آپدیت شد (لینک جدید دریافت شد)"
        elif new_link:
            config_link = new_link
            status_text = "✅ کانفیگ تغییری نکرده (همان لینک قبلی)"

    if not config_link:
        return await cb.message.answer("❌ کانفیگی برای این اشتراک ذخیره نشده. با پشتیبانی تماس بگیرید.")

    text = (
        "🔄 " + status_text + "\n\n"
        "💠 پلن: " + str(sub.get("plan_title") or "—") + "\n"
        "📅 انقضا: " + str(sub.get("expires_at") or "نامحدود") + "\n\n"
    )
    if config_link.startswith(_LINK_PREFIXES):
        text += "🔗 لینک کانفیگ:\n<code>" + config_link + "</code>"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [_btn("📱 دریافت QR Code", "cfg_qr:" + str(order_id))],
            [_btn("🔄 آپدیت مجدد", "cfg_update:" + str(order_id))],
        ])
    else:
        text += "🔗 کانفیگ:\n<code>" + config_link + "</code>"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [_btn("🔄 آپدیت مجدد", "cfg_update:" + str(order_id))],
        ])
    await cb.message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("cfg_qr:"))
async def config_qr(cb: CallbackQuery):
    order_id = int(cb.data.split(":")[1])
    sub = get_subscription_by_order(cb.from_user.id, order_id)
    link = _extract_link(sub) if sub else ""
    if not link:
        return await cb.answer("کانفیگ پیدا نشد", show_alert=True)
    await cb.answer("⏳ ساخت QR...", show_alert=False)
    try:
        import io, qrcode
        from aiogram.types import BufferedInputFile
        img = qrcode.make(link)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        await cb.bot.send_photo(
            chat_id=cb.from_user.id,
            photo=BufferedInputFile(buf.read(), filename="qr.png"),
        )
    except Exception:
        await cb.message.answer("📱 لینک کانفیگ:\n<code>" + link + "</code>")
