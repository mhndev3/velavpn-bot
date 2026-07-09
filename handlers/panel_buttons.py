"""
handler برای دکمه‌های پنل — روی منوی اصلی
"""
from aiogram import Router, F
from aiogram.types import Message

from config.settings import ADMIN_IDS
from database.db import get_sub_admin
from handlers.head_admin_panel import head_admin_main_kb
from handlers.sub_admin_panel import sub_admin_main_kb

router = Router()


@router.message(F.text == "👑 پنل مدیریت")
async def admin_panel_button(msg: Message):
    if msg.from_user.id not in ADMIN_IDS:
        return
    await msg.answer("👑 پنل هد ادمین", reply_markup=head_admin_main_kb())


@router.message(F.text == "👤 پنل ساب‌ادمین")
async def sub_admin_panel_button(msg: Message):
    if not get_sub_admin(msg.from_user.id):
        return
    await msg.answer("👤 پنل ساب‌ادمین", reply_markup=sub_admin_main_kb())
