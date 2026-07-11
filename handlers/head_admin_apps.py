"""
head_admin_apps.py — مدیریت برنامه‌های V2Ray از پنل هد‌ادمین.

هد‌ادمین می‌تواند برای هر پلتفرم (اندروید/ویندوز/مک/iOS) برنامه اضافه/حذف/ویرایش
کند. داده در setting «apps_data» به‌صورت JSON ذخیره می‌شود؛ همان چیزی که
handlers/user_apps.py برای نمایش به کاربر می‌خواند.
"""
import json

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from config.settings import ADMIN_IDS
from database.db import get_setting, set_setting
from handlers.user_apps import PLATFORMS, get_apps_data

router = Router()


class AppStates(StatesGroup):
    add_name = State()
    add_url = State()
    edit_url = State()


def _btn(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


def _save_apps(data: dict):
    set_setting("apps_data", json.dumps(data, ensure_ascii=False))


def _plat_label(pkey: str) -> str:
    return dict(PLATFORMS).get(pkey, pkey)


# ── صفحهٔ اصلی: انتخاب پلتفرم ────────────────────────────────
def _apps_home_kb():
    data = get_apps_data()
    rows = []
    for pkey, plabel in PLATFORMS:
        n = len(data.get(pkey, []))
        rows.append([_btn(f"{plabel} ({n} برنامه)", f"ha:apps:plat:{pkey}")])
    rows.append([_btn("⬅️ بازگشت", "ha:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "ha:apps")
async def apps_home(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("دسترسی ندارید", show_alert=True)
    await state.clear()
    txt = ("📲 <b>مدیریت برنامه‌ها</b>\n\n"
           "برای هر سیستم‌عامل می‌توانید برنامه اضافه/حذف/ویرایش کنید.\n"
           "این‌ها همان‌هایی هستند که کاربر در «دریافت برنامه‌ها» می‌بیند.")
    try:
        await cb.message.edit_text(txt, reply_markup=_apps_home_kb())
    except Exception:
        await cb.message.answer(txt, reply_markup=_apps_home_kb())
    await cb.answer()


# ── لیست برنامه‌های یک پلتفرم ────────────────────────────────
def _plat_kb(pkey: str):
    data = get_apps_data()
    apps = data.get(pkey, [])
    rows = []
    for i, app in enumerate(apps):
        name = app.get("name", "?")
        rows.append([
            _btn(f"🔗 {name}", f"ha:apps:edit:{pkey}:{i}"),
            _btn("🗑", f"ha:apps:del:{pkey}:{i}"),
        ])
    rows.append([_btn("➕ افزودن برنامه", f"ha:apps:add:{pkey}")])
    rows.append([_btn("⬅️ بازگشت", "ha:apps")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("ha:apps:plat:"))
async def apps_platform(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("دسترسی ندارید", show_alert=True)
    await state.clear()
    pkey = cb.data.split(":")[3]
    apps = get_apps_data().get(pkey, [])
    lines = [f"📲 <b>{_plat_label(pkey)}</b>\n"]
    if apps:
        for app in apps:
            lines.append(f"• {app.get('name','?')}\n  <code>{app.get('url','')}</code>")
    else:
        lines.append("هنوز برنامه‌ای ثبت نشده.")
    txt = "\n".join(lines)
    try:
        await cb.message.edit_text(txt, reply_markup=_plat_kb(pkey), disable_web_page_preview=True)
    except Exception:
        await cb.message.answer(txt, reply_markup=_plat_kb(pkey), disable_web_page_preview=True)
    await cb.answer()


# ── افزودن برنامه ────────────────────────────────────────────
@router.callback_query(F.data.startswith("ha:apps:add:"))
async def apps_add_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("دسترسی ندارید", show_alert=True)
    pkey = cb.data.split(":")[3]
    await state.update_data(pkey=pkey)
    await state.set_state(AppStates.add_name)
    await cb.message.answer(f"📲 افزودن برنامه به «{_plat_label(pkey)}»\n\nنام برنامه را بفرست:")
    await cb.answer()


@router.message(AppStates.add_name)
async def apps_add_name(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    name = (msg.text or "").strip()
    if not name:
        return await msg.answer("نام معتبر بفرست.")
    await state.update_data(new_name=name)
    await state.set_state(AppStates.add_url)
    await msg.answer(f"نام: {name}\n\nحالا لینک دانلود را بفرست (با https):")


@router.message(AppStates.add_url)
async def apps_add_url(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    url = (msg.text or "").strip()
    if not url.lower().startswith("http"):
        return await msg.answer("لینک باید با http یا https شروع شود. دوباره بفرست:")
    data = await state.get_data()
    pkey = data.get("pkey")
    name = data.get("new_name")
    apps_data = get_apps_data()
    apps_data.setdefault(pkey, []).append({"name": name, "url": url})
    _save_apps(apps_data)
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[_btn("⬅️ بازگشت به لیست", f"ha:apps:plat:{pkey}")]])
    await msg.answer(f"✅ «{name}» به {_plat_label(pkey)} اضافه شد.", reply_markup=kb)


# ── حذف برنامه ───────────────────────────────────────────────
@router.callback_query(F.data.startswith("ha:apps:del:"))
async def apps_delete(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("دسترسی ندارید", show_alert=True)
    parts = cb.data.split(":")
    pkey, idx = parts[3], int(parts[4])
    apps_data = get_apps_data()
    apps = apps_data.get(pkey, [])
    if 0 <= idx < len(apps):
        removed = apps.pop(idx)
        _save_apps(apps_data)
        await cb.answer(f"🗑 «{removed.get('name','?')}» حذف شد")
    else:
        await cb.answer("یافت نشد", show_alert=True)
    # رفرش لیست
    try:
        await cb.message.edit_reply_markup(reply_markup=_plat_kb(pkey))
    except Exception:
        pass


# ── ویرایش لینک برنامه ───────────────────────────────────────
@router.callback_query(F.data.startswith("ha:apps:edit:"))
async def apps_edit_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("دسترسی ندارید", show_alert=True)
    parts = cb.data.split(":")
    pkey, idx = parts[3], int(parts[4])
    apps = get_apps_data().get(pkey, [])
    if not (0 <= idx < len(apps)):
        return await cb.answer("یافت نشد", show_alert=True)
    app = apps[idx]
    await state.update_data(pkey=pkey, idx=idx)
    await state.set_state(AppStates.edit_url)
    await cb.message.answer(
        f"✏️ ویرایش لینک «{app.get('name','?')}»\n"
        f"لینک فعلی:\n<code>{app.get('url','')}</code>\n\n"
        "لینک جدید را بفرست:"
    )
    await cb.answer()


@router.message(AppStates.edit_url)
async def apps_edit_url(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    url = (msg.text or "").strip()
    if not url.lower().startswith("http"):
        return await msg.answer("لینک باید با http شروع شود. دوباره بفرست:")
    data = await state.get_data()
    pkey, idx = data.get("pkey"), data.get("idx")
    apps_data = get_apps_data()
    apps = apps_data.get(pkey, [])
    if 0 <= idx < len(apps):
        apps[idx]["url"] = url
        _save_apps(apps_data)
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[_btn("⬅️ بازگشت به لیست", f"ha:apps:plat:{pkey}")]])
    await msg.answer("✅ لینک بروزرسانی شد.", reply_markup=kb)
