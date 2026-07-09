"""
کیبورد inline برای نمایش و خرید پلن‌ها
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.sub_admin_pricing import get_price_for_user


def _btn(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


def plans_kb_inline(plans: list, telegram_id: int, service_id: int):
    """کیبورد inline برای پلن‌های یک سرویس — با نمایش قیمت و دکمه‌های خرید"""
    rows = []
    for plan in plans:
        # قیمت نهایی (برای ساب‌ادمین قیمت خاص)
        final_price = get_price_for_user(telegram_id, plan["id"])
        price_display = f"{final_price:,}T"
        
        # هر پلن ۲ دکمه: نمایش جزئیات + خرید
        rows.append([
            _btn(f"📋 {plan['title']} — {price_display}", f"shop:plan_info:{plan['id']}"),
        ])
        rows.append([
            _btn(f"💳 خرید", f"shop:buy_with_wallet:{plan['id']}"),
        ])
        rows.append([
            _btn(f"", ""),  # جداکننده
        ])
    
    rows.append([_btn("⬅️ بازگشت", f"shop:service:{service_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def service_kb_inline(services: list, category: str):
    """کیبورد inline برای سرویس‌های یک دسته‌بندی"""
    rows = []
    for svc in services:
        rows.append([_btn(f"🛍 {svc['name']}", f"shop:service:{svc['id']}")])
    rows.append([_btn("⬅️ بازگشت", f"shop:category:{category}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def categories_kb_inline():
    """کیبورد inline برای دسته‌بندی‌های سرویس"""
    categories = [
        ("v2ray", "🟢 V2Ray VIP"),
        ("l2tp", "🟠 L2TP نامحدود"),
        ("openvpn", "🔵 OpenVPN تک‌کاربره"),
        ("starlink", "🛰 استارلینک اختصاصی"),
    ]
    rows = [[_btn(label, f"shop:category:{cat}")] for cat, label in categories]
    rows.append([_btn("⬅️ بازگشت", "user:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
