"""
sub_admin_panel.py — پنل ساب‌ادمین (دلال)
آمار روزانه، هفتگی، ماهانه + تعرفه اختصاصی
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta

from database.db import get_sub_admin, get_sub_admin_sales, get_sub_admin_orders, get_connection
from services.ui_texts import T, TF

router = Router()


def _btn(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


def sub_admin_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(T("sa_btn_total", "📊 آمار کلی فروش"), "sa:stats_total")],
        [_btn(T("sa_btn_today", "📅 آمار امروز"), "sa:stats_today"),
         _btn(T("sa_btn_week", "📈 آمار هفتگی"), "sa:stats_week")],
        [_btn(T("sa_btn_month", "📆 آمار ماهانه"), "sa:stats_month")],
        [_btn(T("sa_btn_orders", "🧾 سفارش‌های من"), "sa:orders")],
        [_btn(T("sa_btn_pricing", "💰 تعرفه من"), "sa:my_pricing")],
    ])


def _back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(T("sa_btn_back", "⬅️ بازگشت"), "sa:home")]])


def _get_stats_for_period(sa_id: int, start_date: str, end_date: str) -> dict:
    """آمار فروش در یک بازه زمانی"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(*) as total_orders,
               COALESCE(SUM(final_price_toman), 0) as total_revenue
        FROM orders
        WHERE sub_admin_id = ?
          AND status = 'approved'
          AND DATE(created_at) BETWEEN ? AND ?
        """,
        (sa_id, start_date, end_date),
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"total_orders": row["total_orders"], "total_revenue": row["total_revenue"]}
    return {"total_orders": 0, "total_revenue": 0}


# ── Entry ────────────────────────────────────────────────────
@router.message(F.text.in_(["👤 پنل ساب‌ادمین", "📊 آمار فروش من"]))
async def sub_admin_entry(msg: Message):
    sa = get_sub_admin(msg.from_user.id)
    if not sa:
        return
    await msg.answer(
        T("sa_welcome", "👤 پنل ساب‌ادمین\n\nخوش اومدی!\nاز این پنل می‌تونی آمار فروشت رو ببینی."),
        reply_markup=sub_admin_main_kb(),
    )


@router.callback_query(F.data == "sa:home")
async def sa_home(cb: CallbackQuery):
    sa = get_sub_admin(cb.from_user.id)
    if not sa:
        return await cb.answer(T("sa_no_access", "دسترسی ندارید"), show_alert=True)
    await cb.message.edit_text(T("sa_home_title", "👤 پنل ساب‌ادمین"), reply_markup=sub_admin_main_kb())
    await cb.answer()


# ── آمار کلی ────────────────────────────────────────────────
@router.callback_query(F.data == "sa:stats_total")
async def sa_stats_total(cb: CallbackQuery):
    sa = get_sub_admin(cb.from_user.id)
    if not sa:
        return await cb.answer(T("sa_no_access", "دسترسی ندارید"), show_alert=True)

    stats = get_sub_admin_sales(sa["id"])
    comm = sa.get("commission_percent", 0)
    comm_amount = int(stats["total_revenue"] * comm / 100) if comm else 0

    text = TF(
        "sa_total",
        "📊 آمار کلی فروش شما\n"
        "━━━━━━━━━━━━━━\n\n"
        "🧾 کل سفارش‌های تایید شده: {orders}\n"
        "💰 جمع کل فروش: {revenue} تومان\n",
        orders=stats["total_orders"], revenue="{:,}".format(stats["total_revenue"]),
    )
    if comm:
        text += TF(
            "sa_commission_block",
            "📈 درصد کمیسیون شما: {percent}%\n"
            "💵 کمیسیون کل: {amount} تومان\n",
            percent=comm, amount="{:,}".format(comm_amount),
        )
    await cb.message.edit_text(text, reply_markup=_back_kb())
    await cb.answer()


# ── آمار امروز ───────────────────────────────────────────────
@router.callback_query(F.data == "sa:stats_today")
async def sa_stats_today(cb: CallbackQuery):
    sa = get_sub_admin(cb.from_user.id)
    if not sa:
        return await cb.answer(T("sa_no_access", "دسترسی ندارید"), show_alert=True)

    today = datetime.now().strftime("%Y-%m-%d")
    stats = _get_stats_for_period(sa["id"], today, today)
    comm = sa.get("commission_percent", 0)
    comm_amount = int(stats["total_revenue"] * comm / 100) if comm else 0

    text = TF(
        "sa_today",
        "📅 آمار فروش امروز ({date})\n"
        "━━━━━━━━━━━━━━\n\n"
        "🧾 سفارش‌ها: {orders}\n"
        "💰 درآمد: {revenue} تومان\n",
        date=today, orders=stats["total_orders"],
        revenue="{:,}".format(stats["total_revenue"]),
    )
    if comm:
        text += TF("sa_comm_line", "💵 کمیسیون: {amount} تومان\n",
                   amount="{:,}".format(comm_amount))
    await cb.message.edit_text(text, reply_markup=_back_kb())
    await cb.answer()


# ── آمار هفتگی ───────────────────────────────────────────────
@router.callback_query(F.data == "sa:stats_week")
async def sa_stats_week(cb: CallbackQuery):
    sa = get_sub_admin(cb.from_user.id)
    if not sa:
        return await cb.answer(T("sa_no_access", "دسترسی ندارید"), show_alert=True)

    today = datetime.now()
    week_start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    week_end = today.strftime("%Y-%m-%d")
    stats = _get_stats_for_period(sa["id"], week_start, week_end)
    comm = sa.get("commission_percent", 0)
    comm_amount = int(stats["total_revenue"] * comm / 100) if comm else 0

    text = TF(
        "sa_week",
        "📈 آمار فروش ۷ روز اخیر\n"
        "({start} تا {end})\n"
        "━━━━━━━━━━━━━━\n\n"
        "🧾 سفارش‌ها: {orders}\n"
        "💰 درآمد: {revenue} تومان\n",
        start=week_start, end=week_end, orders=stats["total_orders"],
        revenue="{:,}".format(stats["total_revenue"]),
    )
    if comm:
        text += TF("sa_comm_line", "💵 کمیسیون: {amount} تومان\n",
                   amount="{:,}".format(comm_amount))
    await cb.message.edit_text(text, reply_markup=_back_kb())
    await cb.answer()


# ── آمار ماهانه ──────────────────────────────────────────────
@router.callback_query(F.data == "sa:stats_month")
async def sa_stats_month(cb: CallbackQuery):
    sa = get_sub_admin(cb.from_user.id)
    if not sa:
        return await cb.answer(T("sa_no_access", "دسترسی ندارید"), show_alert=True)

    today = datetime.now()
    month_start = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    month_end = today.strftime("%Y-%m-%d")
    stats = _get_stats_for_period(sa["id"], month_start, month_end)
    comm = sa.get("commission_percent", 0)
    comm_amount = int(stats["total_revenue"] * comm / 100) if comm else 0

    text = TF(
        "sa_month",
        "📆 آمار فروش ۳۰ روز اخیر\n"
        "({start} تا {end})\n"
        "━━━━━━━━━━━━━━\n\n"
        "🧾 سفارش‌ها: {orders}\n"
        "💰 درآمد: {revenue} تومان\n",
        start=month_start, end=month_end, orders=stats["total_orders"],
        revenue="{:,}".format(stats["total_revenue"]),
    )
    if comm:
        text += TF("sa_comm_line", "💵 کمیسیون: {amount} تومان\n",
                   amount="{:,}".format(comm_amount))
    await cb.message.edit_text(text, reply_markup=_back_kb())
    await cb.answer()


# ── سفارش‌های من ─────────────────────────────────────────────
@router.callback_query(F.data == "sa:orders")
async def sa_orders(cb: CallbackQuery):
    sa = get_sub_admin(cb.from_user.id)
    if not sa:
        return await cb.answer(T("sa_no_access", "دسترسی ندارید"), show_alert=True)

    orders = get_sub_admin_orders(sa["id"], limit=15)
    if not orders:
        return await cb.message.edit_text(
            T("sa_orders_empty", "هنوز سفارشی برای شما ثبت نشده."), reply_markup=_back_kb())

    STATUS = {"pending": "⏳", "approved": "✅", "rejected": "❌"}
    text = T("sa_orders_title", "🧾 سفارش‌های شما:\n\n")
    for o in orders:
        price = o["final_price_toman"] or o["price_toman"]
        ico = STATUS.get(o["status"], "•")
        text += TF("sa_order_item", "{icon} #{order_id} | {plan} | {price}T\n",
                   icon=ico, order_id=o["id"], plan=o["plan_title"],
                   price="{:,}".format(price))

    await cb.message.edit_text(text, reply_markup=_back_kb())
    await cb.answer()


# ── تعرفه من ─────────────────────────────────────────────────
@router.callback_query(F.data == "sa:my_pricing")
async def sa_my_pricing(cb: CallbackQuery):
    sa = get_sub_admin(cb.from_user.id)
    if not sa:
        return await cb.answer(T("sa_no_access", "دسترسی ندارید"), show_alert=True)

    from database.sub_admin_pricing import get_all_sub_admin_pricing
    pricings = get_all_sub_admin_pricing(sa["id"])

    if not pricings:
        text = T(
            "sa_pricing_empty",
            "💰 تعرفه اختصاصی شما\n\n"
            "هنوز تعرفه اختصاصی برای شما تنظیم نشده.\n"
            "با هد ادمین تماس بگیرید."
        )
    else:
        text = T("sa_pricing_title", "💰 تعرفه اختصاصی شما:\n\n")
        for p in pricings:
            default = p["default_price"]
            override = p["override_price_toman"]
            saved = default - override
            text += TF(
                "sa_pricing_item",
                "📦 {service} — {plan}\n"
                "   قیمت شما: {price}T"
                " (قیمت عادی: {normal}T، تخفیف: {saved}T)\n\n",
                service=p["service_name"], plan=p["title"],
                price="{:,}".format(override), normal="{:,}".format(default),
                saved="{:,}".format(saved),
            )

    await cb.message.edit_text(text, reply_markup=_back_kb())
    await cb.answer()
