"""
head_admin_panel.py — پنل کامل هد ادمین
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from pathlib import Path
from datetime import datetime

from config.settings import ADMIN_IDS
from database.db import (
    get_all_servers, get_server, add_server, toggle_server, update_server,
    get_all_sub_admins, add_sub_admin, toggle_sub_admin, get_sub_admin_any,
    get_sub_admin_sales, get_count, get_recent_orders,
    get_pending_payments, get_recent_users, set_setting, get_setting, get_connection,
    is_head_admin, get_head_admins, add_head_admin, remove_head_admin,
    get_required_channels, add_required_channel, remove_required_channel,
)
from services.xui_service import test_server_connection, get_inbounds_for_server
from handlers.btn_filter import Btn

router = Router()


def is_admin(uid: int) -> bool:
    return is_head_admin(uid)


class HeadAdminStates(StatesGroup):
    add_telegram_id = State()
    set_server_domain = State()
    add_channel = State()


class ServerStates(StatesGroup):
    label = State()
    url = State()
    username = State()
    password = State()
    max_clients = State()
    priority = State()
    note = State()


class SubAdminStates(StatesGroup):
    telegram_id = State()
    commission_percent = State()
    note = State()


class BotSettingStates(StatesGroup):
    waiting_value = State()


class CardInfoStates(StatesGroup):
    card_number = State()
    card_name = State()


class AddPlanStates(StatesGroup):
    service_id = State()
    title = State()
    duration_months = State()
    traffic_gb = State()
    price = State()


def _btn(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


def head_admin_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("📊 فروش و مشتریان", "ha:grp:sales")],
        [_btn("🛒 محصولات و قیمت‌گذاری", "ha:grp:products")],
        [_btn("🖥 زیرساخت و کانال‌ها", "ha:grp:infra")],
        [_btn("👥 دسترسی‌ها و ادمین‌ها", "ha:grp:access")],
        [_btn("🎨 شخصی‌سازی و تنظیمات", "ha:grp:system")],
    ])


# ─── زیرمنوهای گروه‌بندی‌شدهٔ پنل هد‌ادمین ───────────────────
HA_GROUPS = {
    "sales": ("📊 فروش و مشتریان", [
        [("📊 آمار کلی", "ha:stats"), ("📈 آنالیتیکس", "admin:analytics")],
        [("👥 کاربران", "ha:users"), ("🧾 سفارش‌ها", "ha:orders")],
        [("⏳ پرداخت‌های در انتظار", "ha:pending")],
        [("💳 شارژهای کیف‌پول", "ha:wallet_charges")],
    ]),
    "products": ("🛒 محصولات و قیمت‌گذاری", [
        [("➕ افزودن پلن", "ha:add_plan")],
        [("📊 تعرفهٔ ساب‌ادمین", "ha:pricing")],
        [("🎟 مدیریت کد تخفیف", "admin:discounts")],
        [("🎁 تنظیمات اکانت تست", "ha:test")],
    ]),
    "infra": ("🖥 زیرساخت و کانال‌ها", [
        [("🖥 سرورهای X-UI", "ha:servers")],
        [("📢 کانال‌های اجباری", "ha:channels")],
        [("📲 مدیریت برنامه‌ها", "ha:apps")],
    ]),
    "access": ("👥 دسترسی‌ها و ادمین‌ها", [
        [("👤 ساب‌ادمین‌ها", "ha:subadmins")],
        [("👑 مدیریت هد‌ادمین‌ها", "ha:hadmins")],
    ]),
    "system": ("🎨 شخصی‌سازی و تنظیمات", [
        [("🎨 تنظیمات ظاهر و متن‌ها", "ui:home")],
        [("⚙️ تنظیمات بات", "ha:settings")],
    ]),
}


def ha_group_kb(gkey: str):
    group = HA_GROUPS.get(gkey)
    rows = []
    if group:
        for row in group[1]:
            rows.append([_btn(text, data) for text, data in row])
    rows.append([_btn("⬅️ بازگشت", "ha:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_kb(data="ha:home"):
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("⬅️ بازگشت", data)]])


# ── مدیریت کانال‌های عضویت اجباری ─────────────────────────────
def _channels_kb():
    rows = []
    for ch in get_required_channels():
        title = ch.get("title") or ch.get("chat_id") or "کانال"
        rows.append([_btn("🗑 " + title, "ha:chan_del:" + str(ch["id"]))])
    rows.append([_btn("➕ افزودن کانال", "ha:chan_add")])
    rows.append([_btn("⬅️ بازگشت", "ha:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "ha:channels")
async def ha_channels(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("دسترسی ندارید", show_alert=True)
    await state.clear()
    await cb.message.edit_text(
        "📢 کانال‌های عضویت اجباری\n"
        "━━━━━━━━━━━━━━\n\n"
        "کاربر جدید قبل از استفاده باید در این کانال‌ها عضو شود.\n"
        "برای حذف روی نام کانال بزن.\n\n"
        "نکته: بات باید در کانال ادمین باشد تا بتواند عضویت را بررسی کند.",
        reply_markup=_channels_kb(),
    )
    await cb.answer()


@router.callback_query(F.data == "ha:chan_add")
async def ha_chan_add(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("دسترسی ندارید", show_alert=True)
    await state.set_state(HeadAdminStates.add_channel)
    await cb.message.edit_text(
        "➕ افزودن کانال\n\n"
        "یکی از این‌ها را بفرست:\n"
        "• آیدی عمومی کانال مثل <code>@MyChannel</code>\n"
        "• یا لینک <code>https://t.me/MyChannel</code>\n"
        "• یا یک پیام از همان کانال را فوروارد کن.",
        reply_markup=back_kb("ha:channels"),
    )
    await cb.answer()


@router.message(HeadAdminStates.add_channel)
async def ha_chan_add_recv(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    chat_id = ""
    title = ""
    url = ""
    # حالت فوروارد از کانال
    fwd = getattr(msg, "forward_from_chat", None)
    if fwd:
        chat_id = str(fwd.id)
        title = fwd.title or (("@" + fwd.username) if fwd.username else str(fwd.id))
        if fwd.username:
            url = "https://t.me/" + fwd.username
            chat_id = "@" + fwd.username  # برای بررسی عضویت راحت‌تر است
    else:
        raw = (msg.text or "").strip()
        uname = ""
        if raw.startswith("@"):
            uname = raw[1:]
        elif "t.me/" in raw:
            uname = raw.split("t.me/")[1].strip("/").split("/")[0].split("?")[0]
        elif raw:
            uname = raw.lstrip("@")
        if uname:
            chat_id = "@" + uname
            title = "@" + uname
            url = "https://t.me/" + uname
    if not chat_id:
        return await msg.answer("❌ ورودی نامعتبر. @username یا لینک یا فوروارد بفرست.",
                                reply_markup=back_kb("ha:channels"))
    add_required_channel(chat_id, title, url)
    await state.clear()
    await msg.answer("✅ کانال اضافه شد: " + title, reply_markup=_channels_kb())


@router.callback_query(F.data.startswith("ha:chan_del:"))
async def ha_chan_del(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return await cb.answer("دسترسی ندارید", show_alert=True)
    remove_required_channel(int(cb.data.split(":")[2]))
    await cb.answer("حذف شد ✅")
    await cb.message.edit_text(
        "📢 کانال‌های عضویت اجباری\n━━━━━━━━━━━━━━\n\nکانال حذف شد.",
        reply_markup=_channels_kb(),
    )


# ── مدیریت هد‌ادمین‌ها ─────────────────────────────────────────
def _hadmins_kb():
    from config.settings import ADMIN_IDS
    rows = []
    for aid in ADMIN_IDS:
        rows.append([_btn("🔒 " + str(aid) + " (ثابت)", "ha:noop")])
    for h in get_head_admins():
        tid = h["telegram_id"]
        rows.append([_btn("🗑 حذف " + str(tid), "ha:hadmin_del:" + str(tid))])
    rows.append([_btn("➕ افزودن هد‌ادمین", "ha:hadmin_add")])
    rows.append([_btn("⬅️ بازگشت", "ha:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "ha:hadmins")
async def ha_hadmins(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("دسترسی ندارید", show_alert=True)
    await state.clear()
    await cb.message.edit_text(
        "👑 مدیریت هد‌ادمین‌ها\n"
        "━━━━━━━━━━━━━━\n\n"
        "هد‌ادمین‌ها به کل پنل مدیریت دسترسی کامل دارند.\n"
        "🔒 = ثابت (در فایل .env، از اینجا حذف نمی‌شود)\n\n"
        "برای افزودن، «➕ افزودن هد‌ادمین» را بزن و آیدی عددی کاربر را بفرست.",
        reply_markup=_hadmins_kb(),
    )
    await cb.answer()


@router.callback_query(F.data == "ha:noop")
async def ha_noop(cb: CallbackQuery):
    await cb.answer("این هد‌ادمین ثابت است و از اینجا حذف نمی‌شود.", show_alert=True)


@router.callback_query(F.data.startswith("ha:server_domain:"))
async def ha_server_domain(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("دسترسی ندارید", show_alert=True)
    sid = int(cb.data.split(":")[2])
    s = get_server(sid)
    cur = ((s.get("domain") if s else "") or "").strip() or "— (ست نشده)"
    await state.update_data(domain_server_id=sid)
    await state.set_state(HeadAdminStates.set_server_domain)
    await cb.message.edit_text(
        "🌐 تنظیم دامنهٔ سرور\n"
        "━━━━━━━━━━━━━━\n\n"
        "دامنهٔ فعلی: <code>" + cur + "</code>\n\n"
        "دامنهٔ جدید را بفرست (مثلاً <code>panel.example.com</code>).\n"
        "این دامنه در ساخت لینک کانفیگ‌های این سرور استفاده می‌شود "
        "(به‌جای IP یا دامنهٔ پنل).\n\n"
        "برای پاک‌کردن دامنه، بنویس: <b>حذف</b>",
        reply_markup=back_kb("ha:server:" + str(sid)),
    )
    await cb.answer()


@router.message(HeadAdminStates.set_server_domain)
async def ha_server_domain_recv(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    data = await state.get_data()
    sid = data.get("domain_server_id")
    if not sid:
        await state.clear()
        return
    raw = (msg.text or "").strip()
    if raw in ("حذف", "-", "خالی", "پاک"):
        domain = ""
    else:
        domain = raw.replace("https://", "").replace("http://", "").strip().strip("/")
    update_server(int(sid), domain=domain)
    await state.clear()
    s = get_server(int(sid))
    await msg.answer(
        "✅ دامنه ذخیره شد: <code>" + (domain or "(حذف شد)") + "</code>\n\n"
        "از این پس کانفیگ‌های این سرور با این دامنه ساخته می‌شوند.",
        reply_markup=server_detail_kb(int(sid), s["is_active"] if s else 1),
    )


@router.callback_query(F.data == "ha:hadmin_add")
async def ha_hadmin_add(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("دسترسی ندارید", show_alert=True)
    await state.set_state(HeadAdminStates.add_telegram_id)
    await cb.message.edit_text(
        "➕ افزودن هد‌ادمین\n\n"
        "آیدی عددی کاربر را بفرست (فقط عدد).\n"
        "نکته: کاربر بهتر است حداقل یک‌بار /start را زده باشد.",
        reply_markup=back_kb("ha:hadmins"),
    )
    await cb.answer()


@router.message(HeadAdminStates.add_telegram_id)
async def ha_hadmin_add_recv(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    raw = (msg.text or "").strip()
    if not raw.isdigit():
        return await msg.answer("❌ آیدی نامعتبر. فقط عدد بفرست.",
                                reply_markup=back_kb("ha:hadmins"))
    tid = int(raw)
    add_head_admin(tid, added_by=msg.from_user.id)
    await state.clear()
    await msg.answer("✅ هد‌ادمین اضافه شد: " + str(tid), reply_markup=_hadmins_kb())


@router.callback_query(F.data.startswith("ha:hadmin_del:"))
async def ha_hadmin_del(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("دسترسی ندارید", show_alert=True)
    tid = int(cb.data.split(":")[2])
    remove_head_admin(tid)
    await cb.answer("حذف شد ✅")
    await cb.message.edit_text(
        "👑 مدیریت هد‌ادمین‌ها\n━━━━━━━━━━━━━━\n\nهد‌ادمین حذف شد.",
        reply_markup=_hadmins_kb(),
    )


def settings_kb():
    card_info = get_setting("card_info", "تنظیم نشده")
    short = card_info[:30] + "..." if len(card_info) > 30 else card_info
    glass_on = get_setting("ui_glass_mode", "") == "1"
    glass_lbl = ("🪟 دکمه‌های شیشه‌ای: 🟢 روشن" if glass_on
                 else "🪟 دکمه‌های شیشه‌ای: 🔴 خاموش")
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("💬 متن خوشامد",             "ha:set:start_message")],
        [_btn("💳 کارت: " + short,          "ha:set_card_info")],
        [_btn("🎁 درصد کمیسیون رفرال",     "ha:set:referral_commission_percent")],
        [_btn(glass_lbl,                    "ha:toggle_glass")],
        [_btn("🗄 بکاپ کامل (بات + پنل‌ها)", "ha:backup_all")],
        [_btn("💾 دانلود دیتابیس",          "ha:download_db")],
        [_btn("⬅️ بازگشت",                 "ha:home")],
    ])


@router.callback_query(F.data == "ha:backup_all")
async def ha_backup_all(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return await cb.answer("دسترسی ندارید", show_alert=True)
    await cb.answer("⏳ در حال گرفتن بکاپ...", show_alert=False)
    try:
        from database.backup import run_full_backup
        report = await run_full_backup(cb.bot, notify_id=cb.from_user.id)
    except Exception as e:
        report = "❌ خطا در بکاپ: " + repr(e)[:80]
    try:
        await cb.message.answer(report, reply_markup=back_kb("ha:settings"))
    except Exception:
        pass


@router.callback_query(F.data == "ha:toggle_glass")
async def ha_toggle_glass(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return await cb.answer("دسترسی ندارید", show_alert=True)
    cur = get_setting("ui_glass_mode", "") == "1"
    set_setting("ui_glass_mode", "" if cur else "1")
    await cb.answer("✅ حالت شیشه‌ای " + ("خاموش شد" if cur else "روشن شد"))
    try:
        await cb.message.edit_reply_markup(reply_markup=settings_kb())
    except Exception:
        pass



SETTING_LABELS = {
    "start_message": "متن خوشامد",
    "starlink_price_per_gb": "قیمت هر گیگ استارلینک",
    "referral_commission_percent": "درصد کمیسیون رفرال",
}


def servers_kb(servers: list):
    rows = []
    for s in servers:
        ico = "🟢" if s["is_active"] else "🔴"
        rows.append([_btn(
            ico + " " + s["label"] + " (" + str(s["current_clients"]) + "/" + str(s["max_clients"]) + ")",
            "ha:server:" + str(s["id"])
        )])
    rows.append([_btn("➕ افزودن سرور جدید", "ha:server_add")])
    rows.append([_btn("⬅️ بازگشت", "ha:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def server_detail_kb(server_id: int, is_active: int):
    toggle_lbl = "🔴 غیرفعال کن" if is_active else "🟢 فعال کن"
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("🔌 تست اتصال", "ha:server_test:" + str(server_id)),
         _btn("📋 لیست اینباند", "ha:server_inbounds:" + str(server_id))],
        [_btn(toggle_lbl, "ha:server_toggle:" + str(server_id))],
        [_btn("🌐 تنظیم دامنه", "ha:server_domain:" + str(server_id))],
        [_btn("🗑 حذف سرور", "ha:server_delete:" + str(server_id))],
        [_btn("⬅️ بازگشت", "ha:servers")],
    ])


def subadmins_kb(sas: list):
    rows = []
    for sa in sas:
        ico = "🟢" if sa["is_active"] else "🔴"
        uname = "@" + sa["username"] if sa.get("username") else sa.get("full_name", "—")
        rows.append([_btn(ico + " " + uname, "ha:sa:" + str(sa["telegram_id"]))])
    rows.append([_btn("➕ افزودن ساب‌ادمین", "ha:sa_add")])
    rows.append([_btn("⬅️ بازگشت", "ha:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def subadmin_detail_kb(tid: int, is_active: int):
    toggle_lbl = "🔴 غیرفعال" if is_active else "🟢 فعال"
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("📊 آمار فروشش", "ha:sa_stats:" + str(tid)),
         _btn(toggle_lbl, "ha:sa_toggle:" + str(tid))],
        [_btn("⬅️ بازگشت", "ha:subadmins")],
    ])


# ── Entry ────────────────────────────────────────────────────
@router.message(Btn("btn_admin", "👑 پنل مدیریت", "/headadmin"))
async def head_admin_entry(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("👑 پنل هد ادمین", reply_markup=head_admin_main_kb())


@router.callback_query(F.data == "ha:home")
async def ha_home(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return await cb.answer("دسترسی ندارید", show_alert=True)
    await cb.message.edit_text(
        "👑 <b>پنل هد ادمین</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "یک بخش را انتخاب کنید:",
        reply_markup=head_admin_main_kb()
    )
    await cb.answer()


@router.callback_query(F.data.startswith("ha:grp:"))
async def ha_group(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return await cb.answer("دسترسی ندارید", show_alert=True)
    gkey = cb.data.split(":")[2]
    group = HA_GROUPS.get(gkey)
    if not group:
        return await cb.answer("بخش پیدا نشد", show_alert=True)
    await cb.message.edit_text(
        f"{group[0]}\n"
        "━━━━━━━━━━━━━━\n\n"
        "یک گزینه را انتخاب کنید:",
        reply_markup=ha_group_kb(gkey)
    )
    await cb.answer()


# ── Stats ────────────────────────────────────────────────────
@router.callback_query(F.data == "ha:stats")
async def ha_stats(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    approved = get_count("orders", "status='approved'")
    pending  = get_count("payments", "status='waiting_admin_review'")
    act_sub  = get_count("subscriptions", "status='active'")
    act_srv  = get_count("xui_servers", "is_active=1")
    text = (
        "📊 آمار کلی ربات\n\n"
        "👥 کاربران: " + str(get_count("users")) + "\n"
        "🧾 کل سفارش‌ها: " + str(get_count("orders")) + "\n"
        "✅ تایید شده: " + str(approved) + "\n"
        "⏳ در انتظار: " + str(pending) + "\n"
        "📦 اشتراک فعال: " + str(act_sub) + "\n"
        "🖥 سرور فعال: " + str(act_srv) + "\n"
    )
    await cb.message.edit_text(text, reply_markup=back_kb())
    await cb.answer()


@router.callback_query(F.data == "ha:users")
async def ha_users(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    users = get_recent_users(15)
    text = "👥 آخرین کاربران:\n\n"
    for u in users:
        un = "@" + u["username"] if u.get("username") else "—"
        text += "• " + str(u["full_name"]) + " | " + un + " | " + str(u["telegram_id"]) + "\n"
    await cb.message.edit_text(text or "کاربری نیست", reply_markup=back_kb())
    await cb.answer()


@router.callback_query(F.data == "ha:orders")
async def ha_orders(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    orders = get_recent_orders(10)
    if not orders:
        return await cb.message.edit_text("سفارشی ثبت نشده", reply_markup=back_kb())
    text = "🧾 سفارش‌های اخیر:\n\n"
    for o in orders:
        price = o["final_price_toman"] or o["price_toman"]
        text += "#" + str(o["id"]) + " | " + str(o["service_name"]) + " | " + str(price) + "T | " + str(o["status"]) + "\n"
    await cb.message.edit_text(text, reply_markup=back_kb())
    await cb.answer()


@router.callback_query(F.data == "ha:pending")
async def ha_pending(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    payments = get_pending_payments(10)
    if not payments:
        return await cb.message.edit_text("پرداخت در انتظاری نیست", reply_markup=back_kb())
    text = "⏳ پرداخت‌های در انتظار:\n\n"
    for p in payments:
        price = p["final_price_toman"] or p["price_toman"]
        text += "#" + str(p["order_id"]) + " | " + str(p["service_name"]) + " | " + str(price) + "T | " + str(p["telegram_id"]) + "\n"
    await cb.message.edit_text(text, reply_markup=back_kb())
    await cb.answer()


# ── X-UI Servers ─────────────────────────────────────────────
@router.callback_query(F.data == "ha:servers")
async def ha_servers(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    servers = get_all_servers()
    await cb.message.edit_text("🖥 مدیریت سرورهای X-UI:", reply_markup=servers_kb(servers))
    await cb.answer()


@router.callback_query(F.data.startswith("ha:server:"))
async def ha_server_detail(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    sid = int(cb.data.split(":")[2])
    s = get_server(sid)
    if not s:
        return await cb.answer("سرور پیدا نشد", show_alert=True)
    text = (
        "🖥 " + s["label"] + "\n\n"
        "آدرس: " + s["url"] + "\n"
        "یوزرنیم: " + s["username"] + "\n"
        "وضعیت: " + ("🟢 فعال" if s["is_active"] else "🔴 غیرفعال") + "\n"
        "کلاینت‌ها: " + str(s["current_clients"]) + "/" + str(s["max_clients"]) + "\n"
        "یادداشت: " + (s["note"] or "—") + "\n"
    )
    await cb.message.edit_text(text, reply_markup=server_detail_kb(sid, s["is_active"]))
    await cb.answer()


@router.callback_query(F.data.startswith("ha:server_test:"))
async def ha_server_test(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    sid = int(cb.data.split(":")[2])
    s = get_server(sid)
    if not s:
        return await cb.answer("سرور پیدا نشد", show_alert=True)
    await cb.answer("⏳ در حال تست...", show_alert=False)
    ok, msg = await test_server_connection(s)
    await cb.message.reply(msg)


@router.callback_query(F.data.startswith("ha:server_inbounds:"))
async def ha_server_inbounds(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    sid = int(cb.data.split(":")[2])
    s = get_server(sid)
    if not s:
        return await cb.answer("سرور پیدا نشد", show_alert=True)
    await cb.answer("⏳ در حال دریافت...", show_alert=False)
    inbounds = await get_inbounds_for_server(s)
    if not inbounds:
        return await cb.message.reply("اینباندی پیدا نشد یا اتصال ناموفق بود")
    text = "📋 اینباندهای " + s["label"] + ":\n\n"
    for ib in inbounds:
        ico = "🟢" if ib.get("enable") else "🔴"
        text += ico + " ID:" + str(ib["id"]) + " | " + str(ib.get("remark", "—")) + " | " + str(ib.get("protocol", "?")) + " | پورت " + str(ib.get("port", "?")) + "\n"
    await cb.message.reply(text)


@router.callback_query(F.data.startswith("ha:server_toggle:"))
async def ha_server_toggle(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    sid = int(cb.data.split(":")[2])
    new = toggle_server(sid)
    await cb.answer("وضعیت: " + ("🟢 فعال" if new else "🔴 غیرفعال"), show_alert=True)
    s = get_server(sid)
    text = "🖥 " + s["label"] + "\nوضعیت: " + ("🟢 فعال" if s["is_active"] else "🔴 غیرفعال") + "\n"
    await cb.message.edit_text(text, reply_markup=server_detail_kb(sid, s["is_active"]))


@router.callback_query(F.data.startswith("ha:server_delete:"))
async def ha_server_delete_confirm(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    sid = int(cb.data.split(":")[2])
    s = get_server(sid)
    if not s:
        return await cb.answer("سرور پیدا نشد", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [_btn("✅ بله حذف کن", "ha:server_delete_yes:" + str(sid)),
         _btn("❌ انصراف", "ha:server:" + str(sid))],
    ])
    await cb.message.edit_text(
        "⚠️ آیا سرور «" + s["label"] + "» حذف بشه؟\n\nبرگشت‌پذیر نیست!",
        reply_markup=kb
    )
    await cb.answer()


@router.callback_query(F.data.startswith("ha:server_delete_yes:"))
async def ha_server_delete_yes(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    sid = int(cb.data.split(":")[2])
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM xui_servers WHERE id = ?", (sid,))
    conn.commit()
    conn.close()
    await cb.answer("✅ سرور حذف شد", show_alert=True)
    await cb.message.edit_text("🖥 سرورهای X-UI:", reply_markup=servers_kb(get_all_servers()))


@router.callback_query(F.data == "ha:server_add")
async def ha_server_add_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await state.clear()
    await cb.message.edit_text(
        "➕ افزودن سرور X-UI\n\n"
        "اسم سرور رو بفرست:\nمثال: سرور آلمان",
        reply_markup=back_kb("ha:servers"),
    )
    await state.set_state(ServerStates.label)
    await cb.answer()


@router.message(ServerStates.label)
async def ha_server_label(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    await state.update_data(label=msg.text.strip())
    await msg.answer(
        "آدرس کامل پنل:\n"
        "مثال: http://1.2.3.4:54321/مسیر\n\n"
        "نکته مهم: اگه پنل مسیر اختصاصی داره حتماً اون رو هم وارد کن"
    )
    await state.set_state(ServerStates.url)


@router.message(ServerStates.url)
async def ha_server_url(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    await state.update_data(url=msg.text.strip().rstrip("/"))
    await msg.answer("یوزرنیم پنل X-UI:")
    await state.set_state(ServerStates.username)


@router.message(ServerStates.username)
async def ha_server_username(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    await state.update_data(username=msg.text.strip())
    await msg.answer("پسورد پنل X-UI:")
    await state.set_state(ServerStates.password)


@router.message(ServerStates.password)
async def ha_server_password(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    await state.update_data(password=msg.text.strip())
    await msg.answer(
        "حداکثر تعداد کلاینت این سرور؟\n\n"
        "یعنی چند نفر می‌تونن روی این سرور کانفیگ داشته باشن.\n"
        "وقتی پر شد سفارش‌ها به سرور بعدی می‌رن.\n\n"
        "فقط عدد (پیش‌فرض: 500)"
    )
    await state.set_state(ServerStates.max_clients)


@router.message(ServerStates.max_clients)
async def ha_server_max(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    val = int(msg.text.strip()) if msg.text.strip().isdigit() else 500
    await state.update_data(max_clients=val)
    await msg.answer(
        "اولویت سرور؟\n\n"
        "سرور با عدد بزرگ‌تر اول استفاده می‌شه.\n"
        "اگه یک سرور داری: 0"
    )
    await state.set_state(ServerStates.priority)


@router.message(ServerStates.priority)
async def ha_server_priority(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    val = int(msg.text.strip()) if msg.text.strip().lstrip("-").isdigit() else 0
    await state.update_data(priority=val)
    await msg.answer(
        "یادداشت اختیاری:\nمثلاً: سرور آلمان - هتزنر\n\n"
        "اگه نمی‌خوای 0 بفرست."
    )
    await state.set_state(ServerStates.note)


@router.message(ServerStates.note)
async def ha_server_note(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    data = await state.get_data()
    note = "" if msg.text.strip() == "0" else msg.text.strip()
    srv_id = add_server(
        label=data["label"], url=data["url"],
        username=data["username"], password=data["password"],
        max_clients=data["max_clients"], priority=data["priority"], note=note,
    )
    await state.clear()
    s = get_server(srv_id)
    await msg.answer("⏳ تست اتصال...")
    ok, test_msg = await test_server_connection(s)
    await msg.answer(
        "✅ سرور ثبت شد (ID: " + str(srv_id) + ")\n\n" + test_msg,
        reply_markup=server_detail_kb(srv_id, 1),
    )


# ── Sub Admins ───────────────────────────────────────────────
@router.callback_query(F.data == "ha:subadmins")
async def ha_subadmins(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    sas = get_all_sub_admins()
    await cb.message.edit_text("👤 ساب‌ادمین‌ها:", reply_markup=subadmins_kb(sas))
    await cb.answer()


@router.callback_query(F.data.startswith("ha:sa:"))
async def ha_sa_detail(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    tid = int(cb.data.split(":")[2])
    sa = get_sub_admin_any(tid)
    if not sa:
        return await cb.answer("ساب‌ادمین پیدا نشد", show_alert=True)
    un = "@" + sa["username"] if sa.get("username") else "—"
    text = (
        "👤 " + str(sa["full_name"]) + "\n"
        "یوزرنیم: " + un + "\n"
        "آیدی: " + str(tid) + "\n"
        "کمیسیون: " + str(sa["commission_percent"]) + "%\n"
        "وضعیت: " + ("🟢 فعال" if sa["is_active"] else "🔴 غیرفعال") + "\n"
        "یادداشت: " + (sa["note"] or "—") + "\n"
    )
    await cb.message.edit_text(text, reply_markup=subadmin_detail_kb(tid, sa["is_active"]))
    await cb.answer()


@router.callback_query(F.data.startswith("ha:sa_stats:"))
async def ha_sa_stats(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    tid = int(cb.data.split(":")[2])
    sa = get_sub_admin_any(tid)
    if not sa:
        return await cb.answer("پیدا نشد", show_alert=True)
    stats = get_sub_admin_sales(sa["id"])
    comm = sa.get("commission_percent", 0)
    comm_amount = int(stats["total_revenue"] * comm / 100) if comm else 0
    await cb.answer(
        "📊 سفارشات: " + str(stats["total_orders"]) + "\n"
        "درآمد: " + "{:,}".format(stats["total_revenue"]) + " تومان\n"
        "کمیسیون: " + "{:,}".format(comm_amount) + " تومان",
        show_alert=True,
    )


@router.callback_query(F.data.startswith("ha:sa_toggle:"))
async def ha_sa_toggle(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    tid = int(cb.data.split(":")[2])
    new = toggle_sub_admin(tid)
    await cb.answer("وضعیت: " + ("🟢 فعال" if new else "🔴 غیرفعال"), show_alert=True)
    sa = get_sub_admin_any(tid)
    await cb.message.edit_reply_markup(reply_markup=subadmin_detail_kb(tid, sa["is_active"]))


@router.callback_query(F.data == "ha:sa_add")
async def ha_sa_add_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await state.clear()
    await cb.message.edit_text("➕ افزودن ساب‌ادمین\n\nآیدی عددی تلگرام ساب‌ادمین:")
    await state.set_state(SubAdminStates.telegram_id)
    await cb.answer()


@router.message(SubAdminStates.telegram_id)
async def ha_sa_tid(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    if not msg.text.strip().isdigit():
        return await msg.answer("فقط آیدی عددی قبول میشه")
    await state.update_data(telegram_id=int(msg.text.strip()))
    await msg.answer("درصد کمیسیون؟ (0 اگه نداره)")
    await state.set_state(SubAdminStates.commission_percent)


@router.message(SubAdminStates.commission_percent)
async def ha_sa_commission(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    val = int(msg.text.strip()) if msg.text.strip().isdigit() else 0
    await state.update_data(commission_percent=val)
    await msg.answer("یادداشت اختیاری (یا 0):")
    await state.set_state(SubAdminStates.note)


@router.message(SubAdminStates.note)
async def ha_sa_note(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    data = await state.get_data()
    note = "" if msg.text.strip() == "0" else msg.text.strip()
    add_sub_admin(
        telegram_id=data["telegram_id"], full_name="—", username="",
        added_by=msg.from_user.id, commission_percent=data["commission_percent"], note=note,
    )
    await state.clear()
    await msg.answer("✅ ساب‌ادمین اضافه شد: " + str(data["telegram_id"]), reply_markup=back_kb("ha:subadmins"))


# ── Settings ─────────────────────────────────────────────────
@router.callback_query(F.data == "ha:settings")
async def ha_settings(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("⚙️ تنظیمات بات:", reply_markup=settings_kb())
    await cb.answer()


@router.callback_query(F.data.startswith("ha:set:"))
async def ha_set_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    key = cb.data.split(":")[2]
    label = SETTING_LABELS.get(key, key)
    await state.update_data(setting_key=key)
    await cb.message.edit_text("⚙️ " + label + "\n\nمقدار جدید رو بفرست:")
    await state.set_state(BotSettingStates.waiting_value)
    await cb.answer()


@router.message(BotSettingStates.waiting_value)
async def ha_set_value(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    data = await state.get_data()
    key = data.get("setting_key")
    set_setting(key, msg.text.strip())
    label = SETTING_LABELS.get(key, key)
    await state.clear()
    await msg.answer("✅ " + label + " ذخیره شد.", reply_markup=back_kb("ha:settings"))


# ── Card Info (شماره کارت + نام صاحب کارت) ──────────────────
@router.callback_query(F.data == "ha:set_card_info")
async def ha_set_card_info_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    current = get_setting("card_info", "تنظیم نشده")
    await cb.message.edit_text(
        "💳 تنظیم کارت بانکی\n\n"
        "فعلی:\n<code>" + current + "</code>\n\n"
        "شماره کارت جدید رو بفرست:\n"
        "مثال: 6037-9971-1234-5678"
    )
    await state.set_state(CardInfoStates.card_number)
    await cb.answer()


@router.message(CardInfoStates.card_number)
async def ha_card_number(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    await state.update_data(card_number=msg.text.strip())
    await msg.answer(
        "نام صاحب کارت رو بفرست:\n"
        "مثال: علی محمدی"
    )
    await state.set_state(CardInfoStates.card_name)


@router.message(CardInfoStates.card_name)
async def ha_card_name(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    data = await state.get_data()
    card_number = data.get("card_number", "")
    card_name = msg.text.strip()
    # ذخیره هر دو با هم
    card_info = card_number + "\nبه نام: " + card_name
    set_setting("card_info", card_info)
    await state.clear()
    await msg.answer(
        "✅ اطلاعات کارت ذخیره شد:\n\n<code>" + card_info + "</code>",
        reply_markup=back_kb("ha:settings")
    )


# ── افزودن پلن ───────────────────────────────────────────────
@router.callback_query(F.data == "ha:add_plan")
async def ha_add_plan_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await state.clear()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM services WHERE is_active = 1 ORDER BY id")
    services = [dict(r) for r in cursor.fetchall()]
    conn.close()
    if not services:
        return await cb.answer("هیچ سرویسی در دیتابیس نیست", show_alert=True)
    rows = [[_btn(svc["name"], "ha:plan_svc:" + str(svc["id"]))] for svc in services]
    rows.append([_btn("⬅️ بازگشت", "ha:home")])
    await cb.message.edit_text(
        "➕ افزودن پلن جدید\n\nاول سرویس رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )
    await cb.answer()


@router.callback_query(F.data.startswith("ha:plan_svc:"))
async def ha_plan_svc(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    svc_id = int(cb.data.split(":")[2])
    await state.update_data(service_id=svc_id)
    await cb.message.edit_text("اسم پلن رو بفرست:\nمثال: پلن یک ماهه 30 گیگ")
    await state.set_state(AddPlanStates.title)
    await cb.answer()


@router.message(AddPlanStates.title)
async def ha_plan_title(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    await state.update_data(title=msg.text.strip())
    await msg.answer("مدت چند ماهه؟ (عدد)\n0 = بدون انقضا")
    await state.set_state(AddPlanStates.duration_months)


@router.message(AddPlanStates.duration_months)
async def ha_plan_duration(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    if not msg.text.strip().isdigit():
        return await msg.answer("فقط عدد")
    months = int(msg.text.strip())
    await state.update_data(duration_days=months * 30, duration_months=months)
    await msg.answer("حجم چند گیگابایت؟ (عدد)\n0 = نامحدود")
    await state.set_state(AddPlanStates.traffic_gb)


@router.message(AddPlanStates.traffic_gb)
async def ha_plan_traffic(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    if not msg.text.strip().isdigit():
        return await msg.answer("فقط عدد")
    await state.update_data(traffic_gb=int(msg.text.strip()))
    await msg.answer("قیمت پلن به تومان؟ (عدد)\nمثال: 150000")
    await state.set_state(AddPlanStates.price)


@router.message(AddPlanStates.price)
async def ha_plan_price(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    if not msg.text.strip().isdigit():
        return await msg.answer("فقط عدد")
    data = await state.get_data()
    price = int(msg.text.strip())
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO plans (service_id, title, price_toman, duration_days, traffic_gb, is_active) VALUES (?, ?, ?, ?, ?, 1)",
        (data["service_id"], data["title"], price, data["duration_days"], data["traffic_gb"])
    )
    plan_id = cursor.lastrowid
    conn.commit()
    conn.close()
    await state.clear()
    gb_txt  = str(data["traffic_gb"]) + " GB" if data["traffic_gb"] > 0 else "نامحدود"
    dur_txt = str(data["duration_months"]) + " ماه" if data["duration_days"] > 0 else "بی‌انقضا"
    await msg.answer(
        "✅ پلن اضافه شد!\n\n"
        "نام: " + data["title"] + "\n"
        "مدت: " + dur_txt + "\n"
        "حجم: " + gb_txt + "\n"
        "قیمت: " + "{:,}".format(price) + " تومان\n"
        "ID: " + str(plan_id),
        reply_markup=back_kb("ha:home")
    )


# ── Download DB ──────────────────────────────────────────────
@router.callback_query(F.data == "ha:download_db")
async def ha_download_db(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return await cb.answer("دسترسی ندارید", show_alert=True)
    await cb.answer("⏳ آماده‌سازی...", show_alert=False)
    db_path = Path(__file__).resolve().parent.parent / "bot.db"
    if not db_path.exists():
        return await cb.message.answer("فایل دیتابیس پیدا نشد")
    try:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        doc = FSInputFile(str(db_path), filename="backup_" + stamp + ".db")
        await cb.bot.send_document(
            chat_id=cb.from_user.id, document=doc,
            caption="💾 بکاپ دیتابیس - " + stamp,
        )
    except Exception as e:
        await cb.message.answer("خطا: " + str(e))
