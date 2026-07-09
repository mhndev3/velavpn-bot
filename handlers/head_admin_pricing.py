"""
بخش تعرفه ساب‌ادمین در پنل هد ادمین
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config.settings import ADMIN_IDS
from database.db import get_all_sub_admins, get_sub_admin_any, get_services
from database.sub_admin_pricing import (
    get_all_sub_admin_pricing, set_sub_admin_price, get_plan, remove_sub_admin_price
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

router = Router()


def _btn(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


class PricingStates(StatesGroup):
    waiting_new_price = State()


def subadmins_pricing_kb(subadmins: list):
    rows = []
    for sa in subadmins:
        uname = f"@{sa['username']}" if sa.get("username") else sa.get("full_name", "—")
        rows.append([_btn(f"👤 {uname}", f"ha:pricing:sa:{sa['telegram_id']}")])
    rows.append([_btn("⬅️ بازگشت", "ha:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def sa_pricing_detail_kb(telegram_id: int):
    from database.db import get_sub_admin
    sa = get_sub_admin_any(telegram_id)
    if not sa:
        return InlineKeyboardMarkup(inline_keyboard=[[_btn("⬅️ بازگشت", "ha:pricing")]])
    rows = [
        [_btn("📝 مشاهده/ویرایش", f"ha:pricing:detail:{sa['id']}")],
        [_btn("🔄 بازنشانی (قیمت عادی)", f"ha:pricing:reset:{sa['id']}")],
        [_btn("⬅️ بازگشت", "ha:pricing")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "ha:pricing")
async def ha_pricing(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("دسترسی ندارید", show_alert=True)
    sas = get_all_sub_admins()
    if not sas:
        return await cb.message.edit_text(
            "هنوز ساب‌ادمینی تعریف نشده",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[_btn("⬅️ بازگشت", "ha:home")]])
        )
    text = "📊 مدیریت تعرفه ساب‌ادمین‌ها\n\nروی یکی کلیک کن:"
    await cb.message.edit_text(text, reply_markup=subadmins_pricing_kb(sas))
    await cb.answer()


@router.callback_query(F.data.startswith("ha:pricing:sa:"))
async def ha_pricing_sa(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    tid = int(cb.data.split(":")[3])
    sa = get_sub_admin_any(tid)
    if not sa:
        return await cb.answer("ساب‌ادمین پیدا نشد", show_alert=True)
    text = (
        f"👤 {sa['full_name']}\n"
        f"@{sa['username'] if sa.get('username') else '—'}\n"
        f"آیدی: <code>{tid}</code>"
    )
    await cb.message.edit_text(text, reply_markup=sa_pricing_detail_kb(tid))
    await cb.answer()


@router.callback_query(F.data.startswith("ha:pricing:detail:"))
async def ha_pricing_detail(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    sa_id = int(cb.data.split(":")[3])
    from database.db import get_sub_admin
    sa = None
    for s in get_all_sub_admins():
        if s["id"] == sa_id:
            sa = s
            break
    if not sa:
        return await cb.answer("ساب‌ادمین پیدا نشد", show_alert=True)
    
    pricings = get_all_sub_admin_pricing(sa_id)
    if not pricings:
        text = (
            f"👤 {sa['full_name']}\n\n"
            f"هنوز قیمت اختصاصی تعریف نشده\n"
            f"همه پلن‌ها با قیمت عادی فروخته می‌شن"
        )
        return await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[_btn("⬅️ بازگشت", f"ha:pricing:sa:{sa['telegram_id']}")]]))
    
    text = f"👤 {sa['full_name']}\n\n📊 تعرفه‌های اختصاصی:\n\n"
    rows = []
    for p in pricings:
        default = p["default_price"]
        override = p["override_price_toman"]
        diff = override - default
        diff_text = f" ({diff:+,})" if diff != 0 else ""
        text += f"• {p['service_name']} - {p['title']}\n"
        text += f"  قیمت عادی: {default:,}T → اختصاصی: {override:,}T{diff_text}\n\n"
        rows.append([_btn(f"✏️ {p['title']}", f"ha:pricing:edit:{sa_id}:{p['plan_id']}")])
    
    rows.append([_btn("⬅️ بازگشت", f"ha:pricing:sa:{sa['telegram_id']}")])
    await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


@router.callback_query(F.data.startswith("ha:pricing:edit:"))
async def ha_pricing_edit(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    sa_id = int(cb.data.split(":")[3])
    plan_id = int(cb.data.split(":")[4])
    plan = get_plan(plan_id)
    if not plan:
        return await cb.answer("پلن پیدا نشد", show_alert=True)
    
    await state.update_data(sa_id=sa_id, plan_id=plan_id)
    await cb.message.edit_text(
        f"📝 ویرایش قیمت\n\n"
        f"پلن: {plan['title']}\n"
        f"قیمت عادی: {plan['price_toman']:,} تومان\n\n"
        f"قیمت جدید برای ساب‌ادمین رو بفرست:\n"
        f"(فقط عدد، مثال: 3000)"
    )
    await state.set_state(PricingStates.waiting_new_price)
    await cb.answer()


@router.message(PricingStates.waiting_new_price)
async def ha_pricing_new_price(msg, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        return
    if not msg.text or not msg.text.isdigit():
        return await msg.answer("فقط عدد قبول میشه")
    
    data = await state.get_data()
    sa_id = data.get("sa_id")
    plan_id = data.get("plan_id")
    new_price = int(msg.text.strip())
    
    if new_price <= 0:
        return await msg.answer("قیمت باید بزرگ‌تر از صفر باشه")
    
    set_sub_admin_price(sa_id, plan_id, new_price)
    await state.clear()
    await msg.answer(f"✅ قیمت تحدیث شد: {new_price:,} تومان")


@router.callback_query(F.data.startswith("ha:pricing:reset:"))
async def ha_pricing_reset(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    sa_id = int(cb.data.split(":")[3])
    # حذف همه قیمت‌های اختصاصی برای این ساب‌ادمین
    pricings = get_all_sub_admin_pricing(sa_id)
    for p in pricings:
        remove_sub_admin_price(sa_id, p["plan_id"])
    await cb.answer("✅ تعرفه‌های اختصاصی پاک شدن (برگشت به قیمت عادی)", show_alert=True)
    await cb.message.edit_text(
        "✅ همه قیمت‌های اختصاصی حذف شدن\n\nاین ساب‌ادمین الآن با قیمت عادی فروخته می‌کنه",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[_btn("⬅️ بازگشت", "ha:pricing")]])
    )
