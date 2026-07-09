"""
glass_menu.py — حالت دکمه‌های شیشه‌ای (inline) برای یوزر و ساب‌ادمین.
با توگل ui_glass_mode (تنظیمات هد‌ادمین) روشن/خاموش می‌شود.
هد‌ادمین شامل نمی‌شود؛ پنل مدیریت همیشه معمولی می‌ماند.
"""
import importlib
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from database.db import get_setting, is_head_admin
from keyboards.user_keyboards import (
    main_menu_keyboard_for, main_menu_inline_for, glass_launcher_kb, is_glass_mode,
)

router = Router()


class _Shim:
    """پیام جعلی از روی CallbackQuery: from_user = کاربر واقعی، بقیه = پیامِ کالبک."""
    def __init__(self, cb: CallbackQuery):
        self.__dict__["from_user"] = cb.from_user
        self.__dict__["_msg"] = cb.message

    def __getattr__(self, name):
        return getattr(self.__dict__["_msg"], name)


# menu:<key> → (module, function, needs_state)
_DISPATCH = {
    "buy":        ("handlers.user_shop", "buy_subscription_handler", True),
    "profile":    ("handlers.wallet", "profile_entry", False),
    "wallet":     ("handlers.wallet", "wallet_entry", False),
    "subs":       ("handlers.user_extra", "my_subscriptions", False),
    "support":    ("handlers.user_ticket", "support_handler", True),
    "faq":        ("handlers.user_menu", "faq_handler", False),
    "coop":       ("handlers.user_extra", "partnership_start", True),
    "guide":      ("handlers.user_menu", "channels_list_handler", False),
    "cfg_update": ("handlers.user_config_update", "config_update_entry", False),
    "addcfg":     ("handlers.user_add_config", "add_config_start", True),
    "referral":   ("handlers.user_extra", "referral_menu", False),
    "sa_stats":   ("handlers.menu_dynamic", "sa_stats_btn", False),
}


async def send_user_menu(target, uid: int):
    """منوی اصلی را بسته به حالت شیشه‌ای می‌فرستد. target باید متد async answer داشته باشد."""
    txt = get_setting("txt_menu", "منوی اصلی:")
    if is_glass_mode() and not is_head_admin(uid):
        # فقط خود منوی شیشه‌ای؛ بدون هیچ متن/پیام اضافه. دکمهٔ «📋 منو» هم روی همین پیام.
        await target.answer(txt, reply_markup=main_menu_inline_for(uid))
    else:
        await target.answer(txt, reply_markup=main_menu_keyboard_for(uid))


@router.message(F.text == "📋 منو")
async def open_glass_menu(msg: Message, state: FSMContext):
    await state.clear()
    txt = get_setting("txt_menu", "منوی اصلی:")
    if is_glass_mode() and not is_head_admin(msg.from_user.id):
        await msg.answer(txt, reply_markup=main_menu_inline_for(msg.from_user.id))
    else:
        await msg.answer(txt, reply_markup=main_menu_keyboard_for(msg.from_user.id))


@router.callback_query(F.data.startswith("menu:"))
async def glass_dispatch(cb: CallbackQuery, state: FSMContext):
    key = cb.data.split(":", 1)[1]
    entry = _DISPATCH.get(key)
    if not entry:
        return await cb.answer()
    module, func, needs_state = entry
    try:
        fn = getattr(importlib.import_module(module), func)
    except Exception:
        return await cb.answer("این بخش در دسترس نیست.", show_alert=True)
    await cb.answer()
    shim = _Shim(cb)
    try:
        if needs_state:
            await fn(shim, state)
        else:
            await fn(shim)
    except Exception:
        try:
            await cb.message.answer("⚠️ خطا در باز کردن این بخش. لطفاً /start را بزنید.")
        except Exception:
            pass


@router.callback_query(F.data == "u:menu")
async def back_to_menu(cb: CallbackQuery, state: FSMContext):
    """دکمهٔ عمومی بازگشت به منوی اصلی (برای همهٔ بخش‌های کاربر)."""
    await state.clear()
    # پیام فعلی (که دکمهٔ بازگشت رویش بود) پاک می‌شود
    try:
        await cb.message.delete()
    except Exception:
        pass
    # اگر بخش دو پیام فرستاده بود (محتوا + دکمهٔ بازگشت)، پیام محتوا را هم پاک کن.
    # اگر پیام قبلی مالِ کاربر باشد تلگرام اجازه نمی‌دهد و بی‌صدا رد می‌شود.
    try:
        await cb.bot.delete_message(chat_id=cb.message.chat.id,
                                    message_id=cb.message.message_id - 1)
    except Exception:
        pass
    await send_user_menu(cb.message, cb.from_user.id)
    await cb.answer()
