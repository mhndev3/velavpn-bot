# -*- coding: utf-8 -*-
"""
head_admin_users.py — مدیریت کاربران در پنل هد‌ادمین.

- لیست صفحه‌بندی‌شده (۲۵ کاربر در هر صفحه) با دکمه‌های صفحهٔ بعد/قبل
- برای هر کاربر یک دکمه که مشخصات کامل + موجودی کیف‌پول را نشان می‌دهد
- امکان تنظیم دستی موجودی کیف‌پول توسط ادمین
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config.settings import ADMIN_IDS
from database.db import get_connection
from database.wallet import get_wallet, set_wallet_balance

router = Router()

PAGE_SIZE = 25


class AdminUserStates(StatesGroup):
    waiting_balance = State()


def _btn(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


def _is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


# ─── دادهٔ کاربران ──────────────────────────────────────────
def _count_users() -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM users")
    n = cur.fetchone()["c"]
    conn.close()
    return n


def _users_page(page: int) -> list:
    """یک صفحه کاربر (جدیدترین‌ها اول)."""
    offset = max(0, page) * PAGE_SIZE
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT u.telegram_id, u.full_name, u.username, u.custom_username,
               COALESCE(w.balance_toman, 0) AS balance
        FROM users u
        LEFT JOIN wallets w ON w.telegram_id = u.telegram_id
        ORDER BY u.id DESC
        LIMIT ? OFFSET ?
        """,
        (PAGE_SIZE, offset),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def _user_full(telegram_id: int) -> dict | None:
    """مشخصات کامل کاربر + آمار خرید و اشتراک."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None
    u = dict(row)

    cur.execute(
        "SELECT COUNT(*) AS c FROM orders WHERE telegram_id = ? AND status = 'approved'",
        (telegram_id,),
    )
    u["orders_approved"] = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) AS c FROM orders WHERE telegram_id = ?", (telegram_id,))
    u["orders_total"] = cur.fetchone()["c"]

    cur.execute(
        "SELECT COALESCE(SUM(COALESCE(final_price_toman, price_toman, 0)), 0) AS s "
        "FROM orders WHERE telegram_id = ? AND status = 'approved'",
        (telegram_id,),
    )
    u["spent"] = cur.fetchone()["s"]

    cur.execute("SELECT COUNT(*) AS c FROM subscriptions WHERE telegram_id = ?", (telegram_id,))
    u["subs"] = cur.fetchone()["c"]

    cur.execute(
        "SELECT COUNT(*) AS c FROM xui_accounts WHERE order_id IN "
        "(SELECT id FROM orders WHERE telegram_id = ?)",
        (telegram_id,),
    )
    u["accounts"] = cur.fetchone()["c"]
    conn.close()

    w = get_wallet(telegram_id)
    u["balance"] = w["balance_toman"] if w else 0
    return u


# ─── کیبوردها ──────────────────────────────────────────────
def users_list_kb(page: int) -> InlineKeyboardMarkup:
    total = _count_users()
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    rows = []
    for u in _users_page(page):
        name = (u.get("custom_username") or u.get("full_name") or "").strip() or "بدون‌نام"
        if len(name) > 22:
            name = name[:22] + "…"
        label = "👤 " + name + " — " + "{:,}".format(u["balance"]) + "ت"
        rows.append([_btn(label, "ha:user:" + str(u["telegram_id"]) + ":" + str(page))])

    nav = []
    if page > 0:
        nav.append(_btn("◀️ صفحهٔ قبل", "ha:users:" + str(page - 1)))
    nav.append(_btn("صفحهٔ " + str(page + 1) + " از " + str(pages), "ha:users:noop"))
    if page < pages - 1:
        nav.append(_btn("صفحهٔ بعد ▶️", "ha:users:" + str(page + 1)))
    rows.append(nav)

    rows.append([_btn("⬅️ بازگشت", "ha:grp:sales")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def user_detail_kb(telegram_id: int, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("💰 تغییر موجودی کیف‌پول", "ha:ubal:" + str(telegram_id) + ":" + str(page))],
        [_btn("⬅️ بازگشت به لیست", "ha:users:" + str(page))],
    ])


def _user_text(u: dict) -> str:
    name = (u.get("full_name") or "—")
    uname = ("@" + u["username"]) if u.get("username") else "—"
    custom = u.get("custom_username") or "—"
    phone = u.get("phone") or "—"
    joined = (u.get("created_at") or "—")
    return (
        "👤 <b>مشخصات کاربر</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "🏷 نام: " + str(name) + "\n"
        "🆔 آیدی عددی: <code>" + str(u["telegram_id"]) + "</code>\n"
        "🔗 یوزرنیم: " + str(uname) + "\n"
        "✏️ نام انتخابی: " + str(custom) + "\n"
        "📱 شماره: " + str(phone) + "\n"
        "📅 عضویت: " + str(joined) + "\n\n"
        "💰 <b>موجودی کیف‌پول: " + "{:,}".format(u["balance"]) + " تومان</b>\n\n"
        "🧾 سفارش‌ها: " + str(u["orders_approved"]) + " تأییدشده از " + str(u["orders_total"]) + "\n"
        "💳 مجموع خرید: " + "{:,}".format(u["spent"]) + " تومان\n"
        "📦 اشتراک‌ها: " + str(u["subs"]) + "\n"
        "🔑 کانفیگ‌ها: " + str(u["accounts"])
    )


# ─── هندلرها ───────────────────────────────────────────────
@router.callback_query(F.data == "ha:users")
async def ha_users_home(cb: CallbackQuery):
    if not _is_admin(cb.from_user.id):
        return await cb.answer("دسترسی ندارید", show_alert=True)
    total = _count_users()
    await cb.message.edit_text(
        "👥 <b>کاربران</b> (" + str(total) + " نفر)\n"
        "━━━━━━━━━━━━━━\n\n"
        "برای دیدن مشخصات کامل و موجودی، روی کاربر بزنید:",
        reply_markup=users_list_kb(0),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("ha:users:"))
async def ha_users_page(cb: CallbackQuery):
    if not _is_admin(cb.from_user.id):
        return await cb.answer("دسترسی ندارید", show_alert=True)
    arg = cb.data.split(":")[2]
    if arg == "noop":
        return await cb.answer()
    try:
        page = int(arg)
    except ValueError:
        page = 0
    total = _count_users()
    await cb.message.edit_text(
        "👥 <b>کاربران</b> (" + str(total) + " نفر)\n"
        "━━━━━━━━━━━━━━\n\n"
        "برای دیدن مشخصات کامل و موجودی، روی کاربر بزنید:",
        reply_markup=users_list_kb(page),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("ha:user:"))
async def ha_user_detail(cb: CallbackQuery):
    if not _is_admin(cb.from_user.id):
        return await cb.answer("دسترسی ندارید", show_alert=True)
    parts = cb.data.split(":")
    uid = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0
    u = _user_full(uid)
    if not u:
        return await cb.answer("کاربر پیدا نشد", show_alert=True)
    await cb.message.edit_text(_user_text(u), reply_markup=user_detail_kb(uid, page))
    await cb.answer()


@router.callback_query(F.data.startswith("ha:ubal:"))
async def ha_user_balance_start(cb: CallbackQuery, state: FSMContext):
    if not _is_admin(cb.from_user.id):
        return await cb.answer("دسترسی ندارید", show_alert=True)
    parts = cb.data.split(":")
    uid = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0
    u = _user_full(uid)
    if not u:
        return await cb.answer("کاربر پیدا نشد", show_alert=True)

    await state.set_state(AdminUserStates.waiting_balance)
    await state.update_data(target_uid=uid, page=page)
    await cb.message.edit_text(
        "💰 <b>تغییر موجودی کیف‌پول</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "کاربر: " + str(u.get("full_name") or u["telegram_id"]) + "\n"
        "موجودی فعلی: <b>" + "{:,}".format(u["balance"]) + " تومان</b>\n\n"
        "مبلغ جدید را به تومان بفرستید (فقط عدد).\n"
        "برای افزایش/کاهش می‌توانید از + یا - استفاده کنید.\n"
        "مثال: <code>50000</code> یا <code>+20000</code> یا <code>-15000</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [_btn("⬅️ انصراف", "ha:user:" + str(uid) + ":" + str(page))]
        ]),
    )
    await cb.answer()


@router.message(AdminUserStates.waiting_balance)
async def ha_user_balance_set(msg: Message, state: FSMContext):
    if not _is_admin(msg.from_user.id):
        return
    data = await state.get_data()
    uid = data.get("target_uid")
    page = data.get("page", 0)
    if not uid:
        await state.clear()
        return await msg.answer("خطا در شناسایی کاربر.")

    raw = (msg.text or "").strip().replace(",", "").replace("،", "")
    u = _user_full(uid)
    if not u:
        await state.clear()
        return await msg.answer("کاربر پیدا نشد.")

    try:
        if raw.startswith("+"):
            target = u["balance"] + int(raw[1:])
        elif raw.startswith("-"):
            target = u["balance"] - int(raw[1:])
        else:
            target = int(raw)
    except ValueError:
        return await msg.answer("عدد نامعتبر است. فقط عدد بفرستید (مثلاً 50000).")

    if target < 0:
        target = 0

    res = set_wallet_balance(uid, target, changed_by=msg.from_user.id)
    await state.clear()

    sign = "➕" if res["delta"] > 0 else ("➖" if res["delta"] < 0 else "•")
    await msg.answer(
        "✅ موجودی به‌روزرسانی شد\n\n"
        "قبلی: " + "{:,}".format(res["old"]) + " تومان\n"
        "جدید: <b>" + "{:,}".format(res["new"]) + " تومان</b>\n"
        + sign + " تغییر: " + "{:,}".format(abs(res["delta"])) + " تومان",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [_btn("👤 مشاهدهٔ کاربر", "ha:user:" + str(uid) + ":" + str(page))],
            [_btn("⬅️ لیست کاربران", "ha:users:" + str(page))],
        ]),
    )

    # اطلاع به کاربر
    if res["delta"] != 0:
        try:
            txt = ("💰 موجودی کیف‌پول شما توسط پشتیبانی به‌روزرسانی شد.\n\n"
                   "موجودی جدید: " + "{:,}".format(res["new"]) + " تومان")
            await msg.bot.send_message(chat_id=uid, text=txt)
        except Exception:
            pass
