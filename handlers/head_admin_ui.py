"""
پنل مدیریت UI — بنرها، متن‌ها، تم
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from config.settings import ADMIN_IDS
from database.ui_config import (
    get_all_banners, get_banner, update_banner, get_all_ui_texts, 
    set_ui_text, get_all_themes, set_active_theme
)

router = Router()


def _btn(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


class UIEditStates(StatesGroup):
    waiting_banner_text = State()
    waiting_ui_text_value = State()


@router.callback_query(F.data == "ha:ui_config")
async def ha_ui_config(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [_btn("📌 بنرها", "ha:ui_banners")],
        [_btn("📝 متن‌های UI", "ha:ui_texts")],
        [_btn("🎨 تم‌ها", "ha:ui_themes")],
        [_btn("⬅️ بازگشت", "ha:home")],
    ])
    await cb.message.edit_text("🎨 تنظیمات UI/UX:\n\nگزینه رو انتخاب کن:", reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data == "ha:ui_banners")
async def ha_ui_banners(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    banners = get_all_banners()
    if not banners:
        return await cb.message.edit_text("بنری تعریف نشده", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[_btn("⬅️ بازگشت", "ha:ui_config")]]))
    
    rows = []
    for b in banners:
        rows.append([_btn(f"{b['emoji']} {b['name']}", f"ha:ui_banner:{b['id']}")])
    rows.append([_btn("⬅️ بازگشت", "ha:ui_config")])
    
    await cb.message.edit_text("📌 بنرها:\n\nبنر رو انتخاب کن:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


@router.callback_query(F.data.startswith("ha:ui_banner:"))
async def ha_ui_banner_detail(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    banner_id = int(cb.data.split(":")[3])
    banners = get_all_banners()
    banner = next((b for b in banners if b["id"] == banner_id), None)
    if not banner:
        return await cb.answer("بنر پیدا نشد", show_alert=True)
    
    text = (
        f"📌 بنر: {banner['emoji']} {banner['name']}\n\n"
        f"عنوان: {banner['title']}\n"
        f"توضیح: {banner['description'] or '—'}\n"
        f"وضعیت: {'🟢 فعال' if banner['is_active'] else '🔴 غیرفعال'}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [_btn("✏️ ویرایش عنوان", f"ha:ui_banner_edit:{banner_id}")],
        [_btn("⬅️ بازگشت", "ha:ui_banners")],
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data.startswith("ha:ui_banner_edit:"))
async def ha_ui_banner_edit(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    banner_id = int(cb.data.split(":")[4])
    await state.update_data(banner_id=banner_id)
    await cb.message.edit_text("📝 عنوان جدید بنر رو بفرست:")
    await state.set_state(UIEditStates.waiting_banner_text)
    await cb.answer()


@router.message(UIEditStates.waiting_banner_text)
async def ha_ui_banner_text_input(msg, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    banner_id = data.get("banner_id")
    banners = get_all_banners()
    banner = next((b for b in banners if b["id"] == banner_id), None)
    if banner:
        update_banner(banner["name"], title=msg.text.strip())
        await msg.answer(f"✅ بنر آپدیت شد")
    await state.clear()


@router.callback_query(F.data == "ha:ui_texts")
async def ha_ui_texts(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    texts = get_all_ui_texts()
    if not texts:
        return await cb.message.edit_text("متنی تعریف نشده", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[_btn("⬅️ بازگشت", "ha:ui_config")]]))
    
    rows = []
    for t in texts:
        rows.append([_btn(f"{t['emoji']} {t['label']}", f"ha:ui_text:{t['id']}")])
    rows.append([_btn("⬅️ بازگشت", "ha:ui_config")])
    
    await cb.message.edit_text("📝 متن‌های UI:\n\nمتن رو انتخاب کن:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


@router.callback_query(F.data.startswith("ha:ui_text:"))
async def ha_ui_text_detail(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    text_id = int(cb.data.split(":")[3])
    texts = get_all_ui_texts()
    text_obj = next((t for t in texts if t["id"] == text_id), None)
    if not text_obj:
        return await cb.answer("متن پیدا نشد", show_alert=True)
    
    text = (
        f"📝 {text_obj['emoji']} {text_obj['label']}\n\n"
        f"مقدار فعلی:\n{text_obj['value']}"
    )
    await state.update_data(text_key=text_obj['key'])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [_btn("✏️ ویرایش", f"ha:ui_text_edit:{text_id}")],
        [_btn("⬅️ بازگشت", "ha:ui_texts")],
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data.startswith("ha:ui_text_edit:"))
async def ha_ui_text_edit(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    text_id = int(cb.data.split(":")[4])
    texts = get_all_ui_texts()
    text_obj = next((t for t in texts if t["id"] == text_id), None)
    if text_obj:
        await state.update_data(text_key=text_obj['key'], text_label=text_obj['label'])
    await cb.message.edit_text("📝 مقدار جدید رو بفرست:")
    await state.set_state(UIEditStates.waiting_ui_text_value)
    await cb.answer()


@router.message(UIEditStates.waiting_ui_text_value)
async def ha_ui_text_value_input(msg, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    key = data.get("text_key")
    label = data.get("text_label")
    if key:
        set_ui_text(key, label, msg.text.strip())
        await msg.answer(f"✅ متن آپدیت شد")
    await state.clear()


@router.callback_query(F.data == "ha:ui_themes")
async def ha_ui_themes(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    themes = get_all_themes()
    rows = []
    for t in themes:
        active = "⭐" if t["is_active"] else ""
        rows.append([_btn(f"{t['name']} {active}", f"ha:ui_theme:{t['id']}")])
    rows.append([_btn("⬅️ بازگشت", "ha:ui_config")])
    
    await cb.message.edit_text("🎨 تم‌های موجود:\n\nتم رو انتخاب کن:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


@router.callback_query(F.data.startswith("ha:ui_theme:"))
async def ha_ui_theme_detail(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    theme_id = int(cb.data.split(":")[3])
    set_active_theme(theme_id)
    await cb.answer("✅ تم فعال شد", show_alert=True)
    await cb.message.edit_reply_markup(reply_markup=None)
