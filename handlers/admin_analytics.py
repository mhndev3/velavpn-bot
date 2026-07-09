"""
handler آنالیتیکس — داشبورد ادمین
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database.analytics import (
    get_daily_analytics, get_revenue_chart_data, get_weekly_report, get_monthly_report
)
from config.settings import ADMIN_IDS

router = Router()


def _btn(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


@router.callback_query(F.data == "admin:analytics")
async def admin_analytics(cb: CallbackQuery):
    """داشبورد آنالیتیکس"""
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("دسترسی ندارید", show_alert=True)
    
    text = "📊 داشبورد آنالیتیکس\n\nگزارش رو انتخاب کن:"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [_btn("📈 امروز", "analytics:today")],
        [_btn("📊 هفتگی", "analytics:weekly")],
        [_btn("📈 ماهانه", "analytics:monthly")],
        [_btn("📉 نمودار درآمد", "analytics:chart")],
        [_btn("⬅️ بازگشت", "ha:home")],
    ])
    
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data == "analytics:today")
async def analytics_today(cb: CallbackQuery):
    """آمار امروز"""
    dailies = get_daily_analytics(days=1)
    
    if not dailies:
        return await cb.answer("داده‌ای برای امروز نیست", show_alert=True)
    
    today = dailies[0]
    
    text = (
        f"📊 آمار امروز\n\n"
        f"تاریخ: {today['date']}\n"
        f"سفارش‌ها: {today['total_orders']}\n"
        f"درآمد: {today['total_revenue_toman']:,} تومان\n"
        f"کاربران جدید: {today['new_users']}\n"
        f"کل کاربران: {today['total_users']}"
    )
    
    await cb.answer(text, show_alert=True)


@router.callback_query(F.data == "analytics:weekly")
async def analytics_weekly(cb: CallbackQuery):
    """گزارش هفتگی"""
    report = get_weekly_report()
    
    text = (
        f"📊 گزارش هفتگی\n\n"
        f"کل سفارش‌ها: {report['total_orders']}\n"
        f"کل درآمد: {report['total_revenue']:,} تومان\n"
        f"میانگین روزانه: {report['avg_daily_revenue']:,} تومان\n"
        f"بیشترین درآمد: {report['max_daily_revenue']:,} تومان\n"
        f"کمترین درآمد: {report['min_daily_revenue']:,} تومان"
    )
    
    await cb.answer(text, show_alert=True)


@router.callback_query(F.data == "analytics:monthly")
async def analytics_monthly(cb: CallbackQuery):
    """گزارش ماهانه"""
    report = get_monthly_report()
    
    text = (
        f"📈 گزارش ماهانه\n\n"
        f"کل سفارش‌ها: {report['total_orders']}\n"
        f"کل درآمد: {report['total_revenue']:,} تومان\n"
        f"میانگین روزانه: {report['avg_daily_revenue']:,} تومان\n"
        f"بیشترین درآمد: {report['max_daily_revenue']:,} تومان\n"
        f"کمترین درآمد: {report['min_daily_revenue']:,} تومان"
    )
    
    await cb.answer(text, show_alert=True)


@router.callback_query(F.data == "analytics:chart")
async def analytics_chart(cb: CallbackQuery):
    """نمودار درآمد"""
    chart_data = get_revenue_chart_data(days=30)
    
    if not chart_data:
        return await cb.answer("داده‌ای برای نمودار نیست", show_alert=True)
    
    # ساخت نمودار سادّه (متنی)
    text = "📉 نمودار درآمد (30 روز)\n\n"
    
    max_revenue = max(chart_data.values()) if chart_data else 1
    
    for date, revenue in chart_data.items():
        bar_length = int((revenue / max_revenue) * 20) if max_revenue > 0 else 0
        bar = "█" * bar_length
        text += f"{date}: {bar} {revenue:,}T\n"
    
    await cb.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [_btn("⬅️ بازگشت", "admin:analytics")]
        ])
    )
    await cb.answer()
