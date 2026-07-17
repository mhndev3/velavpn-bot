"""
handler خرید inline — بدون reply keyboard
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from database.db import get_services_by_category, get_service, get_plans_for_service, get_plan
from keyboards.shop_inline import categories_kb_inline, service_kb_inline, plans_kb_inline

router = Router()


@router.message(F.text == "⚡ خرید کانفیگ")
async def buy_start(msg: Message):
    """شروع خرید — نمایش دسته‌بندی‌ها"""
    await msg.answer(
        "⚡ خرید کانفیگ\n\nدسته‌بندی رو انتخاب کن:",
        reply_markup=categories_kb_inline()
    )


@router.callback_query(F.data.startswith("shop:category:"))
async def shop_category(cb: CallbackQuery):
    """نمایش سرویس‌های یک دسته"""
    category = cb.data.split(":")[2]
    services = get_services_by_category(category)
    if not services:
        return await cb.answer("سرویسی موجود نیست", show_alert=True)
    
    category_labels = {
        "v2ray": "🟢 V2Ray VIP",
        "l2tp": "🟠 L2TP نامحدود",
        "openvpn": "🔵 OpenVPN تک‌کاربره",
        "starlink": "🛰 استارلینک اختصاصی",
    }
    text = f"سرویس‌های {category_labels.get(category, category)}:\n\nسرویس رو انتخاب کن:"
    await cb.message.edit_text(text, reply_markup=service_kb_inline(services, category))
    await cb.answer()


@router.callback_query(F.data.startswith("shop:service:"))
async def shop_service(cb: CallbackQuery):
    """نمایش پلن‌های یک سرویس"""
    service_id = int(cb.data.split(":")[2])
    service = get_service(service_id)
    if not service:
        return await cb.answer("سرویس پیدا نشد", show_alert=True)
    
    plans = get_plans_for_service(service_id)
    if not plans:
        return await cb.answer("پلنی موجود نیست", show_alert=True)
    
    text = f"سرویس: {service['name']}\n\nپلن‌های موجود:\n\nپلن رو انتخاب کن:"
    await cb.message.edit_text(text, reply_markup=plans_kb_inline(plans, cb.from_user.id, service_id))
    await cb.answer()


@router.callback_query(F.data.startswith("shop:plan_info:"))
async def shop_plan_info(cb: CallbackQuery):
    """نمایش جزئیات پلن"""
    plan_id = int(cb.data.split(":")[2])
    plan = get_plan(plan_id)
    if not plan:
        return await cb.answer("پلن پیدا نشد", show_alert=True)
    
    from database.sub_admin_pricing import get_price_for_user
    final_price = get_price_for_user(cb.from_user.id, plan_id)
    
    text = (
        f"📋 جزئیات پلن\n\n"
        f"سرویس: {plan['service_name']}\n"
        f"نام پلن: {plan['title']}\n"
        f"مدت اشتراک: {plan['duration_days']} روز\n"
        f"قیمت: {final_price:,} تومان\n"
        f"حجم: {plan.get('traffic_gb', '∞')} GB\n"
    )
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 خرید — {final_price:,}T", callback_data=f"shop:buy_with_wallet:{plan_id}")],
        [InlineKeyboardButton(text="⬅️ بازگشت", callback_data=f"shop:service:{plan['service_id']}")],
    ])
    
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()
