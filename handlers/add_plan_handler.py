"""
add_plan_handler.py — مدیریت کامل پلن‌ها:
- نمایش پلن‌های موجود
- حذف پلن
- افزودن پلن جدید با flow: نام > مدت > حجم > قیمت > سرور > اینباند > تأیید
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from config.settings import ADMIN_IDS
from database.db import get_connection, get_all_servers, get_server
from services.xui_service import get_inbounds_for_server

router = Router()


class AddPlanStates(StatesGroup):
    title = State()
    duration_months = State()
    traffic_gb = State()
    price = State()
    # ویرایش پلن موجود
    edit_price = State()
    edit_gb = State()
    edit_duration = State()


def _btn(t, d):
    return InlineKeyboardButton(text=t, callback_data=d)


_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _fa(value) -> str:
    # اعداد لاتین می‌مانند
    return str(value)


def _back_home():
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("⬅️ بازگشت", "ha:home")]])


def _get_all_plans() -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, s.name as service_name
        FROM plans p
        LEFT JOIN services s ON s.id = p.service_id
        ORDER BY p.is_active DESC, p.id ASC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def plans_list_kb(plans: list) -> InlineKeyboardMarkup:
    rows = []
    for p in plans:
        ico = "🟢" if p["is_active"] else "🔴"
        gb = (_fa(p["traffic_gb"]) + " گیگ") if p["traffic_gb"] > 0 else "نامحدود"
        days = (_fa(p["duration_days"]) + " روز") if p["duration_days"] > 0 else "بدون انقضا"
        # RLM در ابتدا تا چیدمان کاملاً راست‌به‌چپ و بدون به‌هم‌ریختگی باشد
        label = "\u200f" + ico + " " + str(p["title"]) + " | " + gb + " | " + days + " | کد " + _fa(p["id"])
        rows.append([_btn(label, "haplan:detail:" + str(p["id"]))])
    rows.append([_btn("➕ افزودن پلن جدید", "haplan:add")])
    rows.append([_btn("⬅️ بازگشت", "ha:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def plan_detail_kb(plan_id: int, is_active: int) -> InlineKeyboardMarkup:
    tog = "🔴 غیرفعال کن" if is_active else "🟢 فعال کن"
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("✏️ ویرایش پلن", "haplan:edit:" + str(plan_id))],
        [_btn(tog, "haplan:toggle:" + str(plan_id))],
        [_btn("🗑 حذف این پلن", "haplan:delete_confirm:" + str(plan_id))],
        [_btn("⬅️ بازگشت به پلن‌ها", "ha:add_plan")],
    ])


def plan_edit_kb(plan_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("💰 قیمت", "haplan:edit_price:" + str(plan_id)),
         _btn("📦 حجم", "haplan:edit_gb:" + str(plan_id))],
        [_btn("⏳ مدت", "haplan:edit_dur:" + str(plan_id)),
         _btn("🌍 لوکیشن", "haplan:edit_loc:" + str(plan_id))],
        [_btn("⬅️ بازگشت", "haplan:detail:" + str(plan_id))],
    ])


# ── ورود به مدیریت پلن‌ها ────────────────────────────────────
@router.callback_query(F.data == "ha:add_plan")
async def plan_manage(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("دسترسی ندارید", show_alert=True)
    await state.clear()
    plans = _get_all_plans()
    count = len(plans)
    await cb.message.edit_text(
        "📦 مدیریت پلن‌ها\n\n"
        "تعداد پلن‌های فعلی: " + str(count) + "\n\n"
        "روی هر پلن کلیک کن برای جزئیات/حذف:",
        reply_markup=plans_list_kb(plans)
    )
    await cb.answer()


# ── جزئیات پلن ───────────────────────────────────────────────
@router.callback_query(F.data.startswith("haplan:detail:"))
async def plan_detail(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    plan_id = int(cb.data.split(":")[2])
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, s.name as service_name, xs.label as server_label
        FROM plans p
        LEFT JOIN services s ON s.id = p.service_id
        LEFT JOIN xui_servers xs ON xs.id = p.server_id
        WHERE p.id = ?
    """, (plan_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return await cb.answer("پلن پیدا نشد", show_alert=True)
    p = dict(row)
    gb = str(p["traffic_gb"]) + " GB" if p["traffic_gb"] > 0 else "نامحدود"
    dur = str(p["duration_days"]) + " روز" if p["duration_days"] > 0 else "بی‌انقضا"
    text = (
        "📦 پلن #" + str(plan_id) + "\n"
        "━━━━━━━━━━━━━━\n\n"
        "نام: " + p["title"] + "\n"
        "سرویس: " + str(p.get("service_name") or "—") + "\n"
        "مدت: " + dur + "\n"
        "حجم: " + gb + "\n"
        "قیمت: " + "{:,}".format(p["price_toman"]) + " تومان\n"
        "سرور: " + str(p.get("server_label") or "—") + "\n"
        "وضعیت: " + ("🟢 فعال" if p["is_active"] else "🔴 غیرفعال") + "\n"
    )
    await cb.message.edit_text(text, reply_markup=plan_detail_kb(plan_id, p["is_active"]))
    await cb.answer()


# ── ویرایش پلن ───────────────────────────────────────────────
def _plan_detail_view(plan_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, s.name as service_name, xs.label as server_label
        FROM plans p
        LEFT JOIN services s ON s.id = p.service_id
        LEFT JOIN xui_servers xs ON xs.id = p.server_id
        WHERE p.id = ?
    """, (plan_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None, None
    p = dict(row)
    gb = str(p["traffic_gb"]) + " GB" if p["traffic_gb"] > 0 else "نامحدود"
    dur = str(p["duration_days"]) + " روز" if p["duration_days"] > 0 else "بی‌انقضا"
    text = (
        "📦 پلن #" + str(plan_id) + "\n"
        "━━━━━━━━━━━━━━\n\n"
        "نام: " + p["title"] + "\n"
        "سرویس: " + str(p.get("service_name") or "—") + "\n"
        "مدت: " + dur + "\n"
        "حجم: " + gb + "\n"
        "قیمت: " + "{:,}".format(p["price_toman"]) + " تومان\n"
        "سرور: " + str(p.get("server_label") or "—") + "\n"
        "وضعیت: " + ("🟢 فعال" if p["is_active"] else "🔴 غیرفعال") + "\n"
    )
    return text, p["is_active"]


def _update_plan(plan_id: int, field: str, value):
    if field not in ("price_toman", "traffic_gb", "duration_days", "server_id", "inbound_id"):
        return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE plans SET " + field + " = ? WHERE id = ?", (value, plan_id))
    conn.commit()
    conn.close()


@router.callback_query(F.data.startswith("haplan:edit:"))
async def plan_edit_menu(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("دسترسی ندارید", show_alert=True)
    await state.clear()
    plan_id = int(cb.data.split(":")[2])
    await cb.message.edit_text(
        "✏️ ویرایش پلن #" + str(plan_id) + "\n\nکدام مورد را می‌خواهی تغییر بدهی؟",
        reply_markup=plan_edit_kb(plan_id),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("haplan:edit_price:"))
async def plan_edit_price(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    plan_id = int(cb.data.split(":")[2])
    await state.update_data(edit_plan_id=plan_id)
    await state.set_state(AddPlanStates.edit_price)
    await cb.message.edit_text("💰 قیمت جدید را به تومان بفرست (فقط عدد):",
                               reply_markup=_back_edit(plan_id))
    await cb.answer()


@router.callback_query(F.data.startswith("haplan:edit_gb:"))
async def plan_edit_gb(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    plan_id = int(cb.data.split(":")[2])
    await state.update_data(edit_plan_id=plan_id)
    await state.set_state(AddPlanStates.edit_gb)
    await cb.message.edit_text("📦 حجم جدید را به گیگابایت بفرست (0 = نامحدود):",
                               reply_markup=_back_edit(plan_id))
    await cb.answer()


@router.callback_query(F.data.startswith("haplan:edit_dur:"))
async def plan_edit_dur(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    plan_id = int(cb.data.split(":")[2])
    await state.update_data(edit_plan_id=plan_id)
    await state.set_state(AddPlanStates.edit_duration)
    await cb.message.edit_text("⏳ مدت جدید را به ماه بفرست (0 = بی‌انقضا):",
                               reply_markup=_back_edit(plan_id))
    await cb.answer()


def _back_edit(plan_id):
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("⬅️ انصراف", "haplan:edit:" + str(plan_id))]])


async def _finish_edit(msg: Message, state: FSMContext, plan_id: int):
    await state.clear()
    text, is_active = _plan_detail_view(plan_id)
    if text:
        await msg.answer("✅ ذخیره شد.\n\n" + text, reply_markup=plan_detail_kb(plan_id, is_active))
    else:
        await msg.answer("✅ ذخیره شد.")


@router.message(AddPlanStates.edit_price)
async def plan_edit_price_recv(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        return
    if not (msg.text or "").strip().isdigit():
        return await msg.answer("❌ فقط عدد بفرست.")
    data = await state.get_data()
    pid = data.get("edit_plan_id")
    _update_plan(pid, "price_toman", int(msg.text.strip()))
    await _finish_edit(msg, state, pid)


@router.message(AddPlanStates.edit_gb)
async def plan_edit_gb_recv(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        return
    if not (msg.text or "").strip().isdigit():
        return await msg.answer("❌ فقط عدد بفرست.")
    data = await state.get_data()
    pid = data.get("edit_plan_id")
    _update_plan(pid, "traffic_gb", int(msg.text.strip()))
    await _finish_edit(msg, state, pid)


@router.message(AddPlanStates.edit_duration)
async def plan_edit_dur_recv(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        return
    if not (msg.text or "").strip().isdigit():
        return await msg.answer("❌ فقط عدد بفرست.")
    data = await state.get_data()
    pid = data.get("edit_plan_id")
    _update_plan(pid, "duration_days", int(msg.text.strip()) * 30)
    await _finish_edit(msg, state, pid)


@router.callback_query(F.data.startswith("haplan:edit_loc:"))
async def plan_edit_loc(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    plan_id = int(cb.data.split(":")[2])
    servers = [s for s in get_all_servers() if s["is_active"]]
    if not servers:
        return await cb.answer("سروری نیست", show_alert=True)
    rows = [[_btn("🖥 " + s["label"], "haplan:setloc:" + str(plan_id) + ":" + str(s["id"]))]
            for s in servers]
    rows.append([_btn("⬅️ انصراف", "haplan:edit:" + str(plan_id))])
    await cb.message.edit_text("🌍 لوکیشن (سرور) جدید پلن را انتخاب کن:",
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


@router.callback_query(F.data.startswith("haplan:setloc:"))
async def plan_set_loc(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    parts = cb.data.split(":")
    plan_id, sid = int(parts[2]), int(parts[3])
    _update_plan(plan_id, "server_id", sid)
    _update_plan(plan_id, "inbound_id", 0)  # اینباند = اولین فعالِ سرور جدید
    await cb.answer("✅ لوکیشن تغییر کرد")
    text, is_active = _plan_detail_view(plan_id)
    if text:
        await cb.message.edit_text(text, reply_markup=plan_detail_kb(plan_id, is_active))


# ── فعال/غیرفعال پلن ─────────────────────────────────────────
@router.callback_query(F.data.startswith("haplan:toggle:"))
async def plan_toggle(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    plan_id = int(cb.data.split(":")[2])
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_active FROM plans WHERE id = ?", (plan_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return await cb.answer("پیدا نشد", show_alert=True)
    new_status = 0 if row["is_active"] else 1
    cursor.execute("UPDATE plans SET is_active = ? WHERE id = ?", (new_status, plan_id))
    conn.commit()
    conn.close()
    await cb.answer("✅ وضعیت تغییر کرد", show_alert=True)
    # بازگشت به لیست
    plans = _get_all_plans()
    await cb.message.edit_text(
        "📦 مدیریت پلن‌ها — تعداد: " + str(len(plans)),
        reply_markup=plans_list_kb(plans)
    )


# ── حذف پلن — تأیید ──────────────────────────────────────────
@router.callback_query(F.data.startswith("haplan:delete_confirm:"))
async def plan_delete_confirm(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    plan_id = int(cb.data.split(":")[2])
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT title FROM plans WHERE id = ?", (plan_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return await cb.answer("پیدا نشد", show_alert=True)
    await cb.message.edit_text(
        "⚠️ آیا پلن «" + row["title"] + "» حذف بشه؟\n\nبرگشت‌پذیر نیست!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [_btn("✅ بله حذف کن", "haplan:delete_yes:" + str(plan_id)),
             _btn("❌ انصراف", "haplan:detail:" + str(plan_id))],
        ])
    )
    await cb.answer()


# ── حذف پلن — اجرا ───────────────────────────────────────────
@router.callback_query(F.data.startswith("haplan:delete_yes:"))
async def plan_delete_yes(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    plan_id = int(cb.data.split(":")[2])
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM plans WHERE id = ?", (plan_id,))
    conn.commit()
    conn.close()
    await cb.answer("✅ پلن حذف شد", show_alert=True)
    plans = _get_all_plans()
    await cb.message.edit_text(
        "📦 مدیریت پلن‌ها — تعداد: " + str(len(plans)),
        reply_markup=plans_list_kb(plans)
    )


# ── افزودن پلن جدید — شروع ───────────────────────────────────
@router.callback_query(F.data == "haplan:add")
async def add_plan_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("دسترسی ندارید", show_alert=True)
    await state.clear()
    await cb.message.edit_text(
        "➕ افزودن پلن جدید\n\n"
        "مرحله ۱/۵ — نام پلن:"
    )
    await state.set_state(AddPlanStates.title)
    await cb.answer()


@router.message(AddPlanStates.title)
async def add_plan_title(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        return
    await state.update_data(title=msg.text.strip())
    await msg.answer("مرحله ۲/۵ — مدت (ماه):\n0 = بدون انقضا")
    await state.set_state(AddPlanStates.duration_months)


@router.message(AddPlanStates.duration_months)
async def add_plan_duration(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        return
    if not msg.text.strip().isdigit():
        return await msg.answer("❌ فقط عدد")
    months = int(msg.text.strip())
    await state.update_data(duration_months=months, duration_days=months * 30)
    await msg.answer("مرحله ۳/۵ — حجم (گیگابایت):\n0 = نامحدود")
    await state.set_state(AddPlanStates.traffic_gb)


@router.message(AddPlanStates.traffic_gb)
async def add_plan_traffic(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        return
    if not msg.text.strip().isdigit():
        return await msg.answer("❌ فقط عدد")
    await state.update_data(traffic_gb=int(msg.text.strip()))
    await msg.answer("مرحله ۴/۵ — قیمت (تومان):")
    await state.set_state(AddPlanStates.price)


@router.message(AddPlanStates.price)
async def add_plan_price(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        return
    if not msg.text.strip().isdigit():
        return await msg.answer("❌ فقط عدد")
    await state.update_data(price=int(msg.text.strip()))
    # نمایش سرورها
    servers = [s for s in get_all_servers() if s["is_active"]]
    if not servers:
        return await msg.answer(
            "❌ سرور X-UI فعالی ندارید.\nابتدا سرور اضافه کنید.",
            reply_markup=_back_home()
        )
    rows = []
    for s in servers:
        rows.append([_btn(
            "🖥 " + s["label"] + " (" + str(s["current_clients"]) + "/" + str(s["max_clients"]) + ")",
            "haplan_srv:" + str(s["id"])
        )])
    rows.append([_btn("❌ انصراف", "ha:add_plan")])
    await msg.answer(
        "مرحله ۵الف — انتخاب سرور X-UI:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )


@router.callback_query(F.data.startswith("haplan_srv:"))
async def add_plan_server(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    srv_id = int(cb.data.split(":")[1])
    server = get_server(srv_id)
    if not server:
        return await cb.answer("سرور پیدا نشد", show_alert=True)
    await state.update_data(server_id=srv_id)
    await cb.answer("⏳ دریافت اینباندها...", show_alert=False)
    inbounds = await get_inbounds_for_server(server)
    if not inbounds:
        await cb.message.edit_text(
            "⚠️ اینباندی در سرور «" + server["label"] + "» پیدا نشد.\n"
            "اولین اینباند فعال انتخاب می‌شه.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [_btn("✅ تأیید", "haplan_ib:0")],
                [_btn("❌ انصراف", "ha:add_plan")],
            ])
        )
        return
    rows = []
    for ib in inbounds:
        ico = "🟢" if ib.get("enable") else "🔴"
        label = ico + " " + str(ib.get("remark", "—")) + " | " + str(ib.get("protocol", "?")) + " | پورت " + str(ib.get("port", "?"))
        rows.append([_btn(label, "haplan_ib:" + str(ib["id"]))])
    rows.append([_btn("❌ انصراف", "ha:add_plan")])
    await cb.message.edit_text(
        "مرحله ۵ب — انتخاب اینباند:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )


@router.callback_query(F.data.startswith("haplan_ib:"))
async def add_plan_inbound(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    ib_id = int(cb.data.split(":")[1])
    await state.update_data(inbound_id=ib_id)
    data = await state.get_data()
    srv = get_server(data.get("server_id"))
    srv_name = srv["label"] if srv else "—"
    gb = str(data["traffic_gb"]) + " GB" if data["traffic_gb"] > 0 else "نامحدود"
    dur = str(data["duration_months"]) + " ماه" if data["duration_days"] > 0 else "بی‌انقضا"
    ib_txt = "اینباند #" + str(ib_id) if ib_id > 0 else "اولین فعال"
    await cb.message.edit_text(
        "✅ تأیید پلن جدید\n"
        "━━━━━━━━━━━━━━\n\n"
        "نام: " + data["title"] + "\n"
        "مدت: " + dur + "\n"
        "حجم: " + gb + "\n"
        "قیمت: " + "{:,}".format(data["price"]) + " تومان\n"
        "سرور: " + srv_name + "\n"
        "اینباند: " + ib_txt + "\n\n"
        "تأیید می‌کنی؟",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [_btn("✅ تأیید و ذخیره", "haplan_confirm")],
            [_btn("❌ انصراف", "ha:add_plan")],
        ])
    )
    await cb.answer()


@router.callback_query(F.data == "haplan_confirm")
async def add_plan_confirm(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    await state.clear()
    conn = get_connection()
    cursor = conn.cursor()
    # پلن‌های اضافه‌شده به سرویس استارلینک وصل می‌شن (چون بخش خرید از استارلینک می‌خونه)
    cursor.execute("SELECT id FROM services WHERE category='starlink' AND is_active=1 ORDER BY id LIMIT 1")
    svc = cursor.fetchone()
    if not svc:
        # اگه سرویس استارلینک نبود بساز
        cursor.execute("""
            INSERT INTO services (category, service_type, name, description, is_active)
            VALUES ('starlink', 'custom_volume', 'استارلینک اختصاصی', 'سرویس استارلینک', 1)
        """)
        conn.commit()
        cursor.execute("SELECT id FROM services WHERE category='starlink' AND is_active=1 ORDER BY id LIMIT 1")
        svc = cursor.fetchone()
    svc_id = svc["id"] if svc else 1
    cursor.execute("""
        INSERT INTO plans (service_id, title, price_toman, duration_days, traffic_gb, server_id, inbound_id, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
    """, (svc_id, data["title"], data["price"], data["duration_days"],
          data["traffic_gb"], data.get("server_id"), data.get("inbound_id", 0)))
    plan_id = cursor.lastrowid
    conn.commit()
    conn.close()
    srv = get_server(data.get("server_id")) if data.get("server_id") else None
    gb = str(data["traffic_gb"]) + " GB" if data["traffic_gb"] > 0 else "نامحدود"
    dur = str(data["duration_months"]) + " ماه" if data["duration_days"] > 0 else "بی‌انقضا"
    await cb.message.edit_text(
        "✅ پلن #" + str(plan_id) + " اضافه شد!\n\n"
        "نام: " + data["title"] + "\n"
        "مدت: " + dur + "\n"
        "حجم: " + gb + "\n"
        "قیمت: " + "{:,}".format(data["price"]) + " تومان\n"
        "سرور: " + (srv["label"] if srv else "—") + "\n",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [_btn("📦 مدیریت پلن‌ها", "ha:add_plan")],
            [_btn("⬅️ پنل اصلی", "ha:home")],
        ])
    )
