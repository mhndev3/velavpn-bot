"""
user_test_account.py — دریافت اکانت تست (سمت کاربر).

اگر ادمین اکانت تست را فعال کرده باشد، کاربر بین تست‌های موجود انتخاب می‌کند
و اکانت تست به‌صورت خودکار روی پنل ساخته و لینک/مشخصاتش تحویل داده می‌شود.
اگر غیرفعال باشد، پیام «غیرفعال است» نمایش داده می‌شود.

تنظیمات در setting «test_accounts» به‌صورت JSON:
{ "enabled": bool, "tests": [ {name, server_id, inbound_id, traffic_gb, duration_hours} ] }
همه‌چیز از پنل هد‌ادمین قابل‌ویرایش است.
"""
import json

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database.db import get_setting, save_user
from handlers.btn_filter import Btn
from services.ui_texts import T

router = Router()


def _btn(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


def get_test_config() -> dict:
    raw = get_setting("test_accounts", "")
    if raw:
        try:
            d = json.loads(raw)
            if isinstance(d, dict):
                d.setdefault("enabled", False)
                d.setdefault("tests", [])
                return d
        except Exception:
            pass
    return {"enabled": False, "tests": []}


def _tests_kb() -> InlineKeyboardMarkup:
    cfg = get_test_config()
    rows = []
    for i, t in enumerate(cfg.get("tests", [])):
        name = (t.get("name") or ("تست " + str(i + 1))).strip()
        gb = t.get("traffic_mb", 0)
        hrs = t.get("duration_hours", 0)
        label = "🎁 " + name + "  (" + str(gb) + "MB / " + str(hrs) + "h)"
        rows.append([_btn(label, "test:get:" + str(i))])
    rows.append([_btn(T("test_btn_back", "⬅️ بازگشت"), "u:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def test_entry(msg: Message):
    save_user(msg.from_user.id, msg.from_user.full_name, msg.from_user.username)
    cfg = get_test_config()
    if not cfg.get("enabled"):
        text = T("test_disabled", "⛔️ دریافت اکانت تست در حال حاضر غیرفعال است.\nلطفاً بعداً مراجعه کنید.")
        kb = InlineKeyboardMarkup(inline_keyboard=[[_btn(T("test_btn_back", "⬅️ بازگشت"), "u:menu")]])
        sent = await _send_with_banner(msg, text, kb)
        if not sent:
            await msg.answer(text, reply_markup=kb)
        return
    tests = cfg.get("tests", [])
    if not tests:
        text = T("test_none", "فعلاً اکانت تستی تعریف نشده است.")
        kb = InlineKeyboardMarkup(inline_keyboard=[[_btn(T("test_btn_back", "⬅️ بازگشت"), "u:menu")]])
        return await msg.answer(text, reply_markup=kb)
    text = T("test_title", "🎁 دریافت اکانت تست") + "\n\n" + \
        T("test_pick", "یکی از اکانت‌های تست زیر را انتخاب کنید:")
    kb = _tests_kb()
    sent = await _send_with_banner(msg, text, kb)
    if not sent:
        await msg.answer(text, reply_markup=kb)


async def _send_with_banner(msg, text, kb):
    try:
        from services.banner_service import send_banner
        return await send_banner(msg, "test", caption=text, reply_markup=kb)
    except Exception:
        return False


@router.message(Btn("btn_test", "🎁 دریافت اکانت تست"))
async def test_entry_msg(msg: Message):
    await test_entry(msg)


@router.callback_query(F.data == "test:home")
async def test_home_cb(cb: CallbackQuery):
    cfg = get_test_config()
    if not cfg.get("enabled"):
        return await cb.answer(T("test_disabled_short", "غیرفعال است"), show_alert=True)
    text = T("test_title", "🎁 دریافت اکانت تست") + "\n\n" + \
        T("test_pick", "یکی از اکانت‌های تست زیر را انتخاب کنید:")
    try:
        await cb.message.edit_text(text, reply_markup=_tests_kb())
    except Exception:
        await cb.message.answer(text, reply_markup=_tests_kb())
    await cb.answer()


@router.callback_query(F.data.startswith("test:get:"))
async def test_get_cb(cb: CallbackQuery):
    from services.xui_service import provision_test_account
    from database.db import has_received_test_account, log_test_account
    idx = int(cb.data.split(":")[2])
    cfg = get_test_config()
    if not cfg.get("enabled"):
        return await cb.answer(T("test_disabled_short", "غیرفعال است"), show_alert=True)
    tests = cfg.get("tests", [])
    if not (0 <= idx < len(tests)):
        return await cb.answer("یافت نشد", show_alert=True)

    # ضدسوءاستفاده: هر کاربر فقط یک بار اکانت تست می‌گیرد
    if has_received_test_account(cb.from_user.id):
        return await cb.answer(
            T("test_already", "شما قبلاً اکانت تست دریافت کرده‌اید. هر کاربر فقط یک‌بار می‌تواند اکانت تست بگیرد."),
            show_alert=True)

    t = tests[idx]

    await cb.answer(T("test_building", "⏳ در حال ساخت اکانت تست..."), show_alert=False)
    result = await provision_test_account(
        telegram_id=cb.from_user.id,
        server_id=int(t.get("server_id") or 0),
        inbound_id=int(t.get("inbound_id") or 0),
        traffic_mb=int(t.get("traffic_mb") or 0),
        duration_hours=int(t.get("duration_hours") or 1),
    )
    if not result:
        return await cb.answer(
            T("test_failed", "❌ ساخت اکانت تست ناموفق بود. لطفاً بعداً تلاش کنید."),
            show_alert=True)

    # ثبت در لاگ برای اعمال محدودیت یک‌بار
    log_test_account(
        cb.from_user.id, result.get("email", ""),
        int(t.get("server_id") or 0), int(t.get("inbound_id") or 0),
        int(t.get("traffic_mb") or 0), int(t.get("duration_hours") or 1),
    )

    link = result.get("config_link", "")
    caption = (
        T("test_ready_title", "✅ اکانت تست شما آماده است") + "\n"
        "━━━━━━━━━━━━━━\n\n"
        "📥 حجم: " + str(result.get("traffic_mb", 0)) + " مگابایت\n"
        "⏳ اعتبار: " + str(result.get("duration_hours", 0)) + " ساعت\n"
        "📅 انقضا: " + str(result.get("expires_at", "—")) + "\n"
        "🌍 لوکیشن: " + str(result.get("server_label", "—")) + "\n\n"
        "🔗 لینک کانفیگ:\n<code>" + link + "</code>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[_btn(T("test_btn_back", "⬅️ بازگشت"), "u:menu")]])
    try:
        await cb.message.delete()
    except Exception:
        pass
    # ارسال با QR کد (مثل تحویل کانفیگ خرید)
    sent = False
    if link:
        try:
            import io, qrcode
            from aiogram.types import BufferedInputFile
            img = qrcode.make(link)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            cap = caption if len(caption) <= 1024 else (caption[:1015] + "…")
            await cb.message.answer_photo(
                photo=BufferedInputFile(buf.read(), filename="test_config.png"),
                caption=cap, reply_markup=kb,
            )
            sent = True
        except Exception:
            sent = False
    if not sent:
        await cb.message.answer(caption, reply_markup=kb, disable_web_page_preview=True)
