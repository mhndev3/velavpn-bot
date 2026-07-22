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
        [_btn("⬅️ بازگشت", "ha:grp:sales")],
    ])
    
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


def _back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("⬅️ بازگشت", "admin:analytics")]])


@router.callback_query(F.data == "analytics:today")
async def analytics_today(cb: CallbackQuery):
    """آمار امروز (و چند روز اخیر)"""
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("دسترسی ندارید", show_alert=True)
    dailies = get_daily_analytics(days=7)

    if not dailies:
        return await cb.message.edit_text(
            "📊 <b>آمار روزانه</b>\n━━━━━━━━━━━━━━\n\nهنوز سفارشی ثبت نشده است.",
            reply_markup=_back_kb())

    t = dailies[0]
    text = (
        "📊 <b>آمار روزانه</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "📅 <b>" + str(t["date"]) + "</b> (آخرین روز فعال)\n"
        "🧾 سفارش‌ها: " + str(t["total_orders"]) + "\n"
        "💰 درآمد: " + "{:,}".format(t["total_revenue_toman"]) + " تومان\n"
        "🆕 کاربران جدید: " + str(t["new_users"]) + "\n"
        "👥 کل کاربران: " + str(t["total_users"]) + "\n\n"
        "<b>۷ روز اخیر:</b>\n"
    )
    for d in dailies:
        text += ("• " + str(d["date"]) + " — " + str(d["total_orders"]) + " سفارش، "
                 + "{:,}".format(d["total_revenue_toman"]) + " ت\n")

    await cb.message.edit_text(text, reply_markup=_back_kb())
    await cb.answer()


def _report_text(title: str, report: dict) -> str:
    return (
        title + "\n"
        "━━━━━━━━━━━━━━\n\n"
        "🧾 کل سفارش‌ها: " + str(report["total_orders"]) + "\n"
        "✅ تأییدشده: " + str(report.get("approved_orders", 0)) + "\n"
        "🆕 کاربران جدید: " + str(report.get("new_users", 0)) + "\n\n"
        "💰 کل درآمد: <b>" + "{:,}".format(report["total_revenue"]) + " تومان</b>\n"
        "📊 میانگین روزانه: " + "{:,}".format(report["avg_daily_revenue"]) + " تومان\n"
        "🔼 بیشترین روز: " + "{:,}".format(report["max_daily_revenue"]) + " تومان\n"
        "🔽 کمترین روز: " + "{:,}".format(report["min_daily_revenue"]) + " تومان"
    )


@router.callback_query(F.data == "analytics:weekly")
async def analytics_weekly(cb: CallbackQuery):
    """گزارش هفتگی"""
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("دسترسی ندارید", show_alert=True)
    await cb.message.edit_text(
        _report_text("📊 <b>گزارش هفتگی</b> (۷ روز اخیر)", get_weekly_report()),
        reply_markup=_back_kb())
    await cb.answer()


@router.callback_query(F.data == "analytics:monthly")
async def analytics_monthly(cb: CallbackQuery):
    """گزارش ماهانه"""
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("دسترسی ندارید", show_alert=True)
    await cb.message.edit_text(
        _report_text("📈 <b>گزارش ماهانه</b> (۳۰ روز اخیر)", get_monthly_report()),
        reply_markup=_back_kb())
    await cb.answer()


@router.callback_query(F.data == "analytics:chart")
async def analytics_chart(cb: CallbackQuery):
    """نمودار درآمد"""
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("دسترسی ندارید", show_alert=True)
    chart_data = get_revenue_chart_data(days=30)

    if not chart_data:
        return await cb.message.edit_text(
            "📉 <b>نمودار درآمد</b>\n━━━━━━━━━━━━━━\n\nهنوز فروش تأییدشده‌ای ثبت نشده است.",
            reply_markup=_back_kb())

    text = "📉 <b>نمودار درآمد</b> (۳۰ روز اخیر)\n━━━━━━━━━━━━━━\n\n"
    max_revenue = max(chart_data.values()) or 1
    for date, revenue in chart_data.items():
        bar_length = int((revenue / max_revenue) * 14) if max_revenue > 0 else 0
        text += (str(date) + "  " + ("█" * bar_length) + " "
                 + "{:,}".format(revenue) + "ت\n")

    total = sum(chart_data.values())
    text += "\n💰 جمع کل: <b>" + "{:,}".format(total) + " تومان</b>"

    # تلگرام سقف ۴۰۹۶ کاراکتر دارد
    if len(text) > 3900:
        text = text[:3900] + "\n…"

    await cb.message.edit_text(text, reply_markup=_back_kb())
    await cb.answer()
