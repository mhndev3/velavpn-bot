"""
menu_dynamic.py — handler های داینامیک منو
"""
from aiogram import Router, F
from aiogram.types import Message
from config.settings import ADMIN_IDS
from database.db import get_sub_admin
from services.ui_texts import T
from handlers.btn_filter import Btn

router = Router()

# متن‌های دکمه‌ها — همه حالت‌های ممکن
ADMIN_BTN_TEXTS = ["👑 پنل مدیریت"]
SA_BTN_TEXTS    = ["📊 آمار فروش من"]
REFERRAL_TEXTS  = ["🎁 دعوت دوستان"]


@router.message(Btn("btn_admin", "👑 پنل مدیریت"))
async def admin_panel_btn(msg: Message):
    if msg.from_user.id not in ADMIN_IDS:
        return  # یوزر عادی نمیتونه ببینه ولی اگه تایپ کرد نادیده بگیر
    from handlers.head_admin_panel import head_admin_main_kb
    await msg.answer("👑 پنل هد ادمین", reply_markup=head_admin_main_kb())


@router.message(Btn("btn_sa_stats", "📊 آمار فروش من"))
async def sa_stats_btn(msg: Message):
    if msg.from_user.id in ADMIN_IDS:
        return
    sa = get_sub_admin(msg.from_user.id)
    if not sa:
        return
    from handlers.sub_admin_panel import sub_admin_main_kb
    await msg.answer(T("sa_home_title", "👤 پنل ساب‌ادمین"), reply_markup=sub_admin_main_kb())
