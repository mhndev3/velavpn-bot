"""
handler تنظیمات UI — هد ادمین تنظیم کنه
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from config.settings import ADMIN_IDS
from database.ui_settings import get_all_ui_settings_by_category, set_ui_setting, get_all_ui_settings

router = Router()


def _btn(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


class UISettingStates(StatesGroup):
    waiting_value = State()


def ui_settings_kb():
    """کیبورد تنظیمات UI"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("😊 ایموجی‌ها", "ui:emoji")],
        [_btn("📝 متن‌ها", "ui:texts")],
        [_btn("🎨 بنرها", "ui:banners")],
        [_btn("⬅️ بازگشت", "ha:home")],
    ])


def settings_list_kb(category: str, settings: list):
    """کیبورد لیست تنظیمات"""
    rows = []
    for setting in settings:
        rows.append([_btn(f"{setting['label']}", f"ui:edit:{category}:{setting['key']}")])
    rows.append([_btn("⬅️ بازگشت", "ui:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "ui:home")
async def ui_settings_home(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("دسترسی ندارید", show_alert=True)
    
    await cb.message.edit_text(
        "⚙️ تنظیمات UI/UX\n\nبخش رو انتخاب کن:",
        reply_markup=ui_settings_kb()
    )
    await cb.answer()


@router.callback_query(F.data == "ui:emoji")
async def ui_emoji_settings(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    
    emojis = get_all_ui_settings_by_category("emoji")
    await cb.message.edit_text(
        "😊 تنظیمات ایموجی‌ها\n\nایموجی رو انتخاب کن:",
        reply_markup=settings_list_kb("emoji", emojis)
    )
    await cb.answer()


@router.callback_query(F.data == "ui:texts")
async def ui_text_settings(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    
    texts = get_all_ui_settings_by_category("text")
    await cb.message.edit_text(
        "📝 تنظیمات متن‌ها\n\nمتن رو انتخاب کن:",
        reply_markup=settings_list_kb("text", texts)
    )
    await cb.answer()


@router.callback_query(F.data == "ui:banners")
async def ui_banner_settings(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    
    banners = get_all_ui_settings_by_category("banner")
    await cb.message.edit_text(
        "🎨 تنظیمات بنرها\n\nبنر رو انتخاب کن:",
        reply_markup=settings_list_kb("banner", banners)
    )
    await cb.answer()


@router.callback_query(F.data.startswith("ui:edit:"))
async def ui_edit_setting(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    
    parts = cb.data.split(":")
    category = parts[2]
    key = parts[3]
    
    from database.ui_settings import get_ui_setting
    current_value = get_ui_setting(key, "")
    
    settings = get_all_ui_settings_by_category(category)
    setting = next((s for s in settings if s["key"] == key), None)
    
    if not setting:
        return await cb.answer("تنظیم پیدا نشد", show_alert=True)
    
    await state.update_data(setting_key=key)
    await cb.message.edit_text(
        f"✏️ {setting['label']}\n\n"
        f"مقدار فعلی:\n<code>{current_value}</code>\n\n"
        f"مقدار جدید رو بفرست:"
    )
    await state.set_state(UISettingStates.waiting_value)
    await cb.answer()


@router.message(UISettingStates.waiting_value)
async def ui_save_setting(msg, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        return
    
    data = await state.get_data()
    key = data.get("setting_key")
    
    set_ui_setting(key, msg.text.strip())
    await state.clear()
    
    await msg.answer(
        f"✅ تنظیم ذخیره شد\n\n"
        f"مقدار: <code>{msg.text.strip()}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [_btn("⬅️ بازگشت", "ui:home")]
        ])
    )
