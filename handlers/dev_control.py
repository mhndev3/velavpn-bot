"""
dev_control.py — کنترل دولوپر (Death Note)
فقط DEVELOPER_ID دسترسی دارد. چهار عملیات:
  - Stop Bot   : بات برای کاربران عادی متوقف می‌شود (ادمین‌ها و دولوپر کار می‌کنند)
  - Start Bot  : توقف برداشته می‌شود
  - L          : قفل کامل — حتی هد‌ادمین‌ها هم دسترسی ندارند، فقط دولوپر
  - K          : قفل کامل برداشته می‌شود
وضعیت در تنظیمات ذخیره می‌شود (sys_stopped / sys_lockdown) و آنی اعمال می‌شود.
"""
from aiogram import Router, BaseMiddleware
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from config.settings import DEVELOPER_ID, ADMIN_IDS
from database.db import get_setting, set_setting

router = Router()


def _is_dev(uid) -> bool:
    return DEVELOPER_ID and int(uid) == int(DEVELOPER_ID)


class DevControlMiddleware(BaseMiddleware):
    """قبل از هر هندلر اجرا می‌شود و بر اساس وضعیت قفل/توقف اجازه می‌دهد یا مسدود می‌کند."""
    async def __call__(self, handler, event, data):
        msg = getattr(event, "message", None)
        cbq = getattr(event, "callback_query", None)
        carrier = msg or cbq
        uid = None
        if carrier and getattr(carrier, "from_user", None):
            uid = carrier.from_user.id
        if uid is None:
            return await handler(event, data)

        # دولوپر همیشه عبور می‌کند
        if _is_dev(uid):
            return await handler(event, data)

        lock = get_setting("sys_lockdown", "") == "1"
        stop = get_setting("sys_stopped", "") == "1"

        # قفل کامل (L): همه مسدود، حتی هد‌ادمین
        if lock:
            try:
                if cbq:
                    await cbq.answer("🛠 بات موقتاً در دسترس نیست.", show_alert=True)
                elif msg:
                    await msg.answer("🛠 بات در حال به‌روزرسانی است. لطفاً بعداً تلاش کنید.")
            except Exception:
                pass
            return  # مسدود

        # توقف (Stop): کاربران عادی مسدود، ادمین‌ها عبور می‌کنند
        if stop and uid not in ADMIN_IDS:
            try:
                if cbq:
                    await cbq.answer("🛠 بات موقتاً غیرفعال است.", show_alert=True)
                elif msg:
                    await msg.answer("🛠 بات موقتاً غیرفعال است. لطفاً بعداً تلاش کنید.")
            except Exception:
                pass
            return  # مسدود

        return await handler(event, data)


def _death_note_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛑 Stop Bot", callback_data="dev:stop"),
         InlineKeyboardButton(text="▶️ Start Bot", callback_data="dev:start")],
        [InlineKeyboardButton(text="🖤 L", callback_data="dev:lock"),
         InlineKeyboardButton(text="🤍 K", callback_data="dev:unlock")],
    ])


def _status_text():
    stopped = get_setting("sys_stopped", "") == "1"
    lock = get_setting("sys_lockdown", "") == "1"
    return (
        "📓 <b>Death Note</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "وضعیت فعلی:\n"
        "• توقف (Stop): " + ("🛑 روشن" if stopped else "▶️ خاموش") + "\n"
        "• قفل کامل (L): " + ("🖤 روشن" if lock else "🤍 خاموش") + "\n\n"
        "🛑 Stop Bot: توقف برای کاربران عادی (ادمین‌ها کار می‌کنند)\n"
        "▶️ Start Bot: رفع توقف\n"
        "🖤 L: قفل کامل — حتی هد‌ادمین‌ها هم دسترسی ندارند\n"
        "🤍 K: رفع قفل کامل"
    )


@router.message(Command("deathnote"))
async def death_note_cmd(msg: Message):
    if not _is_dev(msg.from_user.id):
        return  # برای غیر دولوپر کاملاً بی‌پاسخ
    await msg.answer(_status_text(), reply_markup=_death_note_kb())


@router.callback_query(lambda c: c.data and c.data.startswith("dev:"))
async def dev_actions(cb: CallbackQuery):
    if not _is_dev(cb.from_user.id):
        return await cb.answer("⛔", show_alert=True)
    action = cb.data.split(":", 1)[1]
    if action == "stop":
        set_setting("sys_stopped", "1")
        await cb.answer("🛑 بات برای کاربران عادی متوقف شد")
    elif action == "start":
        set_setting("sys_stopped", "")
        await cb.answer("▶️ بات دوباره فعال شد")
    elif action == "lock":
        set_setting("sys_lockdown", "1")
        await cb.answer("🖤 قفل کامل فعال شد (فقط دولوپر)")
    elif action == "unlock":
        set_setting("sys_lockdown", "")
        await cb.answer("🤍 قفل کامل برداشته شد")
    try:
        await cb.message.edit_text(_status_text(), reply_markup=_death_note_kb())
    except Exception:
        pass
