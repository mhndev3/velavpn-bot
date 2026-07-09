"""
handler رفرال — دعوت و کمیسیون
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database.db import save_user
from database.referral import (
    get_or_create_referral_code, add_referral, get_referral_stats
)

router = Router()


def _btn(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


@router.message(F.text == "🎁 دعوت دوستان")
async def referral_menu(msg: Message):
    """منوی رفرال"""
    save_user(msg.from_user.id, msg.from_user.full_name, msg.from_user.username)
    
    code = get_or_create_referral_code(msg.from_user.id)
    stats = get_referral_stats(msg.from_user.id)
    
    text = (
        f"🎁 دعوت دوستان\n\n"
        f"کد دعوت شما: <code>{code}</code>\n\n"
        f"📊 آمار:\n"
        f"👥 تعداد معرّفی‌ها: {stats['referred_count']}\n"
        f"💰 کل کمیسیون: {stats['total_commission']:,} تومان\n\n"
        f"دوستان رو دعوت کن و کمیسیون بگیر!"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [_btn("📋 کپی کد", "referral:copy_code")],
        [_btn("⬅️ بازگشت", "user:menu")],
    ])
    
    await msg.answer(text, reply_markup=kb)


@router.callback_query(F.data == "referral:copy_code")
async def copy_referral_code(cb: CallbackQuery):
    """کپی کد رفرال"""
    code = get_or_create_referral_code(cb.from_user.id)
    
    await cb.answer(
        f"کد دعوت:\n{code}\n\n"
        f"این کد رو برای دوستانت بفرست تا وقتی\u200c"
        f"ثبت‌نام کنن، به عنوان معرّف به حساب شما اضافه بشن!",
        show_alert=True
    )
