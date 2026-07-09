"""
handler منوی اصلی inline — دکمه‌های inline
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()


def _btn(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


def main_menu_inline_kb(telegram_id: int):
    """منوی اصلی inline — برای ساب‌ادمین اضافه دکمه پنل"""
    from database.db import get_sub_admin
    from config.settings import ADMIN_IDS
    
    buttons = [
        [_btn("⚡ خرید کانفیگ", "user:shop")],
        [_btn("💳 کیف‌پول", "user:wallet"), _btn("🛟 پشتیبانی", "user:support")],
        [_btn("📘 راهنما", "user:guide"), _btn("🔎 پیگیری", "user:tracking")],
        [_btn("👤 حساب", "user:account"), _btn("❓ FAQ", "user:faq")],
        [_btn("🎁 دعوت", "user:referral")],
    ]
    
    # اگه هد ادمین باشه
    if telegram_id in ADMIN_IDS:
        buttons.append([_btn("👑 پنل مدیریت", "ha:home")])
    # اگه ساب‌ادمین باشه
    elif get_sub_admin(telegram_id):
        buttons.append([_btn("👤 پنل ساب‌ادمین", "sa:home")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(F.text == "منو")
async def main_menu_inline(msg: Message):
    """نمایش منوی inline"""
    await msg.answer("📱 منوی اصلی:", reply_markup=main_menu_inline_kb(msg.from_user.id))


@router.callback_query(F.data == "user:shop")
async def user_shop_btn(cb: CallbackQuery):
    """دکمه خرید"""
    from keyboards.shop_inline import categories_kb_inline
    await cb.message.edit_text(
        "⚡ خرید کانفیگ\n\nدسته‌بندی رو انتخاب کن:",
        reply_markup=categories_kb_inline()
    )
    await cb.answer()


@router.callback_query(F.data == "user:wallet")
async def user_wallet_btn(cb: CallbackQuery):
    """دکمه کیف‌پول"""
    from database.wallet import get_or_create_wallet
    wallet = get_or_create_wallet(cb.from_user.id)
    text = (
        f"💳 کیف‌پول شما\n\n"
        f"موجودی: {wallet['balance_toman']:,} تومان\n"
        f"کل شارژ شده: {wallet['total_charged_toman']:,} تومان\n\n"
        "گزینه رو انتخاب کن:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [_btn("➕ شارژ کیف‌پول", "wallet:charge_start")],
        [_btn("📊 تاریخچه", "wallet:history")],
        [_btn("⬅️ بازگشت", "user:menu")],
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data.startswith("user:"))
async def user_stub_handlers(cb: CallbackQuery):
    """بقیه دکمه‌ها (placeholder)"""
    action = cb.data.split(":")[1]
    messages = {
        "support": "🛟 پشتیبانی سریع\n\nراه‌های تماس:\n@support_bot",
        "guide": "📘 راهنمای اتصال\n\nدستورات اتصال:",
        "tracking": "🔎 پیگیری سفارش\n\nسفارش‌های شما:",
        "account": "👤 حساب کاربری\n\nاطلاعات شما:",
        "faq": "❓ سوالات متداول\n\nسوالات اصلی:",
        "referral": "🎁 دعوت دوستان\n\nلینک معرف شما:",
    }
    text = messages.get(action, "منو")
    await cb.answer(text, show_alert=True)
