"""
sub_admin_panel.py — پنل ساب‌ادمین (دلال)
آمار روزانه، هفتگی، ماهانه + تعرفه اختصاصی
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta

from database.db import get_sub_admin, get_sub_admin_sales, get_sub_admin_orders, get_connection

router = Router()


def _btn(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


def sub_admin_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("📊 آمار کلی فروش", "sa:stats_total")],
        [_btn("📅 آمار امروز", "sa:stats_today"),
         _btn("📈 آمار هفتگی", "sa:stats_week")],
        [_btn("📆 آمار ماهانه", "sa:stats_month")],
        [_btn("🧾 سفارش‌های من", "sa:orders")],
        [_btn("💰 تعرفه من", "sa:my_pricing")],
    ])


def _back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("⬅️ بازگشت", "sa:home")]])


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
        f"👤 پنل ساب‌ادمین\n\nخوش اومدی!\nاز این پنل می‌تونی آمار فروشت رو ببینی.",
        reply_markup=sub_admin_main_kb(),
    )


@router.callback_query(F.data == "sa:home")
async def sa_home(cb: CallbackQuery):
    sa = get_sub_admin(cb.from_user.id)
    if not sa:
        return await cb.answer("دسترسی ندارید", show_alert=True)
    await cb.message.edit_text("👤 پنل ساب‌ادمین", reply_markup=sub_admin_main_kb())
    await cb.answer()


# ── آمار کلی ────────────────────────────────────────────────
@router.callback_query(F.data == "sa:stats_total")
async def sa_stats_total(cb: CallbackQuery):
    sa = get_sub_admin(cb.from_user.id)
    if not sa:
        return await cb.answer("دسترسی ندارید", show_alert=True)

    stats = get_sub_admin_sales(sa["id"])
    comm = sa.get("commission_percent", 0)
    comm_amount = int(stats["total_revenue"] * comm / 100) if comm else 0

    text = (
        "📊 آمار کلی فروش شما\n"
        "━━━━━━━━━━━━━━\n\n"
        f"🧾 کل سفارش‌های تایید شده: {stats['total_orders']}\n"
        f"💰 جمع کل فروش: {stats['total_revenue']:,} تومان\n"
    )
    if comm:
        text += (
            f"📈 درصد کمیسیون شما: {comm}%\n"
            f"💵 کمیسیون کل: {comm_amount:,} تومان\n"
        )
    await cb.message.edit_text(text, reply_markup=_back_kb())
    await cb.answer()


# ── آمار امروز ───────────────────────────────────────────────
@router.callback_query(F.data == "sa:stats_today")
async def sa_stats_today(cb: CallbackQuery):
    sa = get_sub_admin(cb.from_user.id)
    if not sa:
        return await cb.answer("دسترسی ندارید", show_alert=True)

    today = datetime.now().strftime("%Y-%m-%d")
    stats = _get_stats_for_period(sa["id"], today, today)
    comm = sa.get("commission_percent", 0)
    comm_amount = int(stats["total_revenue"] * comm / 100) if comm else 0

    text = (
        f"📅 آمار فروش امروز ({today})\n"
        "━━━━━━━━━━━━━━\n\n"
        f"🧾 سفارش‌ها: {stats['total_orders']}\n"
        f"💰 درآمد: {stats['total_revenue']:,} تومان\n"
    )
    if comm:
        text += f"💵 کمیسیون: {comm_amount:,} تومان\n"
    await cb.message.edit_text(text, reply_markup=_back_kb())
    await cb.answer()


# ── آمار هفتگی ───────────────────────────────────────────────
@router.callback_query(F.data == "sa:stats_week")
async def sa_stats_week(cb: CallbackQuery):
    sa = get_sub_admin(cb.from_user.id)
    if not sa:
        return await cb.answer("دسترسی ندارید", show_alert=True)

    today = datetime.now()
    week_start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    week_end = today.strftime("%Y-%m-%d")
    stats = _get_stats_for_period(sa["id"], week_start, week_end)
    comm = sa.get("commission_percent", 0)
    comm_amount = int(stats["total_revenue"] * comm / 100) if comm else 0

    text = (
        f"📈 آمار فروش ۷ روز اخیر\n"
        f"({week_start} تا {week_end})\n"
        "━━━━━━━━━━━━━━\n\n"
        f"🧾 سفارش‌ها: {stats['total_orders']}\n"
        f"💰 درآمد: {stats['total_revenue']:,} تومان\n"
    )
    if comm:
        text += f"💵 کمیسیون: {comm_amount:,} تومان\n"
    await cb.message.edit_text(text, reply_markup=_back_kb())
    await cb.answer()


# ── آمار ماهانه ──────────────────────────────────────────────
@router.callback_query(F.data == "sa:stats_month")
async def sa_stats_month(cb: CallbackQuery):
    sa = get_sub_admin(cb.from_user.id)
    if not sa:
        return await cb.answer("دسترسی ندارید", show_alert=True)

    today = datetime.now()
    month_start = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    month_end = today.strftime("%Y-%m-%d")
    stats = _get_stats_for_period(sa["id"], month_start, month_end)
    comm = sa.get("commission_percent", 0)
    comm_amount = int(stats["total_revenue"] * comm / 100) if comm else 0

    text = (
        f"📆 آمار فروش ۳۰ روز اخیر\n"
        f"({month_start} تا {month_end})\n"
        "━━━━━━━━━━━━━━\n\n"
        f"🧾 سفارش‌ها: {stats['total_orders']}\n"
        f"💰 درآمد: {stats['total_revenue']:,} تومان\n"
    )
    if comm:
        text += f"💵 کمیسیون: {comm_amount:,} تومان\n"
    await cb.message.edit_text(text, reply_markup=_back_kb())
    await cb.answer()


# ── سفارش‌های من ─────────────────────────────────────────────
@router.callback_query(F.data == "sa:orders")
async def sa_orders(cb: CallbackQuery):
    sa = get_sub_admin(cb.from_user.id)
    if not sa:
        return await cb.answer("دسترسی ندارید", show_alert=True)

    orders = get_sub_admin_orders(sa["id"], limit=15)
    if not orders:
        return await cb.message.edit_text("هنوز سفارشی برای شما ثبت نشده.", reply_markup=_back_kb())

    STATUS = {"pending": "⏳", "approved": "✅", "rejected": "❌"}
    text = "🧾 سفارش‌های شما:\n\n"
    for o in orders:
        price = o["final_price_toman"] or o["price_toman"]
        ico = STATUS.get(o["status"], "•")
        text += f"{ico} #{o['id']} | {o['plan_title']} | {price:,}T\n"

    await cb.message.edit_text(text, reply_markup=_back_kb())
    await cb.answer()


# ── تعرفه من ─────────────────────────────────────────────────
@router.callback_query(F.data == "sa:my_pricing")
async def sa_my_pricing(cb: CallbackQuery):
    sa = get_sub_admin(cb.from_user.id)
    if not sa:
        return await cb.answer("دسترسی ندارید", show_alert=True)

    from database.sub_admin_pricing import get_all_sub_admin_pricing
    pricings = get_all_sub_admin_pricing(sa["id"])

    if not pricings:
        text = (
            "💰 تعرفه اختصاصی شما\n\n"
            "هنوز تعرفه اختصاصی برای شما تنظیم نشده.\n"
            "با هد ادمین تماس بگیرید."
        )
    else:
        text = "💰 تعرفه اختصاصی شما:\n\n"
        for p in pricings:
            default = p["default_price"]
            override = p["override_price_toman"]
            saved = default - override
            text += (
                f"📦 {p['service_name']} — {p['title']}\n"
                f"   قیمت شما: {override:,}T"
                f" (قیمت عادی: {default:,}T، تخفیف: {saved:,}T)\n\n"
            )

    await cb.message.edit_text(text, reply_markup=_back_kb())
    await cb.answer()
