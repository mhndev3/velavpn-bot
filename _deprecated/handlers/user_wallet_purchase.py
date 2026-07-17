"""
handler خرید با کیف‌پول — بدون تایید ادمین
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database.db import (
    get_plan, create_order, update_order_status, get_sub_admin,
    deduct_from_wallet, save_user
)
from database.wallet import get_wallet, deduct_from_wallet as wallet_deduct
from database.sub_admin_pricing import get_price_for_user
from services.xui_service import provision_account

router = Router()


def _btn(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


@router.callback_query(F.data.startswith("shop:buy_with_wallet:"))
async def buy_with_wallet(cb: CallbackQuery):
    """خرید از کیف‌پول"""
    plan_id = int(cb.data.split(":")[2])
    plan = get_plan(plan_id)
    if not plan:
        return await cb.answer("پلن پیدا نشد", show_alert=True)
    
    # قیمت نهایی (برای ساب‌ادمین قیمت خاص)
    final_price = get_price_for_user(cb.from_user.id, plan_id)
    
    # چک کن کیف‌پول کافی باشه
    wallet = get_wallet(cb.from_user.id)
    if not wallet or wallet["balance_toman"] < final_price:
        wallet_balance = wallet["balance_toman"] if wallet else 0
        shortage = final_price - wallet_balance
        return await cb.answer(
            f"موجودی کیف‌پول کافی نیست\n\n"
            f"نیاز: {final_price:,}T\n"
            f"موجودی: {wallet_balance:,}T\n"
            f"کمبود: {shortage:,}T",
            show_alert=True,
        )
    
    # کسر از کیف‌پول
    save_user(cb.from_user.id, cb.from_user.full_name, cb.from_user.username)
    order_id = create_order(
        telegram_id=cb.from_user.id,
        plan_id=plan_id,
        service_name=plan["service_name"],
        plan_title=plan["title"],
        price_toman=plan["price_toman"],
        duration_days=plan["duration_days"],
        final_price_toman=final_price,
        payment_method="wallet",
        discount_amount=plan["price_toman"] - final_price,  # اگه ساب‌ادمین بود
    )
    
    if not order_id:
        return await cb.answer("خطایی در ایجاد سفارش", show_alert=True)
    
    # کسر از کیف‌پول
    if not wallet_deduct(cb.from_user.id, final_price, order_id):
        update_order_status(order_id, "cancelled")
        return await cb.answer("خطا در کسر کیف‌پول", show_alert=True)
    
    # تایید خودکار
    update_order_status(order_id, "approved")
    
    # سعی برای ساخت خودکار X-UI
    xui_result = await provision_account(
        order_id=order_id,
        telegram_id=cb.from_user.id,
        plan=plan,
        server_id=plan.get("server_id"),
    )
    
    if xui_result and xui_result.get("config_link"):
        # کانفیگ خودکار ساخت شد
        config_msg = (
            f"✅ سفارش تایید شد و کانفیگ ساخت شد\n\n"
            f"سرویس: {plan['service_name']}\n"
            f"پلن: {plan['title']}\n"
            f"مدت: {plan['duration_days']} روز\n"
            f"قیمت: {final_price:,} تومان\n\n"
            f"🔗 لینک کانفیگ ({xui_result['config_type'].upper()}):\n"
            f"<code>{xui_result['config_link']}</code>\n\n"
            f"🖥 سرور: {xui_result.get('server_label', '-')}\n"
            f"📦 حجم: {xui_result.get('traffic_gb', '-')} GB\n"
            f"⏰ انقضا: {xui_result.get('expires_at', '-')}"
        )
        await cb.message.edit_text(config_msg)
    else:
        # خودکار شکست خورد، ادمین دستی می‌فرسته
        await cb.message.edit_text(
            f"✅ سفارش ثبت شد\n\n"
            f"سرویس: {plan['service_name']}\n"
            f"پلن: {plan['title']}\n"
            f"قیمت: {final_price:,} تومان\n\n"
            f"⏳ در حال ساخت کانفیگ...\n"
            f"لطفاً منتظر باشید"
        )
    
    await cb.answer("✅ سفارش تایید شد!", show_alert=True)
