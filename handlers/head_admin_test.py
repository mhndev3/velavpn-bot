"""
head_admin_test.py — تنظیمات اکانت تست (پنل هد‌ادمین).

فلو:
  تنظیمات اکانت تست → فعال/غیرفعال → ویرایش اکانت تست →
  انتخاب سرور → انتخاب اینباند → انتخاب حجم → انتخاب زمان (ساعت)

داده در setting «test_accounts» (JSON) ذخیره می‌شود؛ همان که user_test_account می‌خواند.
"""
import json

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from config.settings import ADMIN_IDS
from database.db import get_setting, set_setting, get_active_servers
from handlers.user_test_account import get_test_config

router = Router()


class TestStates(StatesGroup):
    add_traffic = State()
    add_hours = State()
    add_name = State()


def _btn(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


def _save(cfg: dict):
    set_setting("test_accounts", json.dumps(cfg, ensure_ascii=False))


# ── صفحهٔ اصلی تنظیمات اکانت تست ─────────────────────────────
def _home_kb():
    cfg = get_test_config()
    on = cfg.get("enabled")
    toggle = ("🟢 فعال (برای غیرفعال‌کردن بزنید)" if on
              else "🔴 غیرفعال (برای فعال‌کردن بزنید)")
    rows = [
        [_btn(toggle, "ha:test:toggle")],
        [_btn("✏️ ویرایش اکانت‌های تست", "ha:test:edit")],
        [_btn("⬅️ بازگشت", "ha:home")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "ha:test")
async def test_home(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("دسترسی ندارید", show_alert=True)
    await state.clear()
    cfg = get_test_config()
    txt = ("🎁 <b>تنظیمات اکانت تست</b>\n\n"
           "وضعیت: " + ("🟢 فعال" if cfg.get("enabled") else "🔴 غیرفعال") + "\n"
           "تعداد اکانت‌های تست: " + str(len(cfg.get("tests", []))))
    try:
        await cb.message.edit_text(txt, reply_markup=_home_kb())
    except Exception:
        await cb.message.answer(txt, reply_markup=_home_kb())
    await cb.answer()


@router.callback_query(F.data == "ha:test:toggle")
async def test_toggle(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return await cb.answer("دسترسی ندارید", show_alert=True)
    cfg = get_test_config()
    cfg["enabled"] = not cfg.get("enabled")
    _save(cfg)
    await cb.answer("🟢 فعال شد" if cfg["enabled"] else "🔴 غیرفعال شد")
    cfg2 = get_test_config()
    txt = ("🎁 <b>تنظیمات اکانت تست</b>\n\n"
           "وضعیت: " + ("🟢 فعال" if cfg2.get("enabled") else "🔴 غیرفعال") + "\n"
           "تعداد اکانت‌های تست: " + str(len(cfg2.get("tests", []))))
    try:
        await cb.message.edit_text(txt, reply_markup=_home_kb())
    except Exception:
        pass


# ── لیست/ویرایش اکانت‌های تست ────────────────────────────────
def _edit_kb():
    cfg = get_test_config()
    rows = []
    for i, t in enumerate(cfg.get("tests", [])):
        name = t.get("name") or ("تست " + str(i + 1))
        info = str(t.get("traffic_mb", 0)) + "MB/" + str(t.get("duration_hours", 0)) + "h"
        rows.append([
            _btn("🎁 " + name + " (" + info + ")", "ha:test:noop"),
            _btn("🗑", "ha:test:del:" + str(i)),
        ])
    rows.append([_btn("➕ افزودن اکانت تست", "ha:test:add")])
    rows.append([_btn("⬅️ بازگشت", "ha:test")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "ha:test:noop")
async def test_noop(cb: CallbackQuery):
    await cb.answer()


@router.callback_query(F.data == "ha:test:edit")
async def test_edit(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("دسترسی ندارید", show_alert=True)
    await state.clear()
    txt = "✏️ <b>اکانت‌های تست</b>\n\nاز اینجا می‌توانید اکانت تست اضافه/حذف کنید."
    try:
        await cb.message.edit_text(txt, reply_markup=_edit_kb())
    except Exception:
        await cb.message.answer(txt, reply_markup=_edit_kb())
    await cb.answer()


@router.callback_query(F.data.startswith("ha:test:del:"))
async def test_del(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return await cb.answer("دسترسی ندارید", show_alert=True)
    idx = int(cb.data.split(":")[3])
    cfg = get_test_config()
    tests = cfg.get("tests", [])
    if 0 <= idx < len(tests):
        tests.pop(idx)
        cfg["tests"] = tests
        _save(cfg)
        await cb.answer("🗑 حذف شد")
    try:
        await cb.message.edit_reply_markup(reply_markup=_edit_kb())
    except Exception:
        pass


# ── افزودن اکانت تست: سرور → اینباند → حجم → زمان → نام ───────
@router.callback_query(F.data == "ha:test:add")
async def test_add_server(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("دسترسی ندارید", show_alert=True)
    await state.clear()
    servers = get_active_servers()
    if not servers:
        return await cb.answer("سرور فعالی وجود ندارد", show_alert=True)
    rows = [[_btn("🖥 " + (s.get("label") or ("سرور " + str(s["id"]))),
                  "ha:test:srv:" + str(s["id"]))] for s in servers]
    rows.append([_btn("⬅️ بازگشت", "ha:test:edit")])
    try:
        await cb.message.edit_text("1️⃣ سرور را انتخاب کنید:",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception:
        await cb.message.answer("1️⃣ سرور را انتخاب کنید:",
                                reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


@router.callback_query(F.data.startswith("ha:test:srv:"))
async def test_add_inbound(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("دسترسی ندارید", show_alert=True)
    from services.xui_service import get_inbounds_for_server
    from database.db import get_server
    server_id = int(cb.data.split(":")[3])
    await state.update_data(server_id=server_id)
    server = get_server(server_id)
    await cb.answer("⏳ در حال خواندن اینباندها...")
    inbounds = await get_inbounds_for_server(server) if server else []
    if not inbounds:
        return await cb.answer("اینباندی یافت نشد", show_alert=True)
    rows = []
    for ib in inbounds:
        if not ib.get("enable", True):
            continue
        remark = ib.get("remark") or ("inbound " + str(ib.get("id")))
        proto = ib.get("protocol", "")
        rows.append([_btn("📡 " + remark + " (" + proto + ")",
                          "ha:test:ib:" + str(ib.get("id")))])
    rows.append([_btn("⬅️ بازگشت", "ha:test:add")])
    try:
        await cb.message.edit_text("2️⃣ اینباند را انتخاب کنید:",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception:
        await cb.message.answer("2️⃣ اینباند را انتخاب کنید:",
                                reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data.startswith("ha:test:ib:"))
async def test_add_traffic(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("دسترسی ندارید", show_alert=True)
    inbound_id = int(cb.data.split(":")[3])
    await state.update_data(inbound_id=inbound_id)
    await state.set_state(TestStates.add_traffic)
    await cb.message.answer("3️⃣ حجم اکانت تست را به مگابایت بفرست (مثلاً 200):")
    await cb.answer()


@router.message(TestStates.add_traffic)
async def test_set_traffic(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    txt = (msg.text or "").strip()
    try:
        mb = int(float(txt))
        if mb < 0:
            raise ValueError()
    except Exception:
        return await msg.answer("عدد معتبر بفرست (مثلاً 200).")
    await state.update_data(traffic_mb=mb)
    await state.set_state(TestStates.add_hours)
    await msg.answer("4️⃣ مدت اعتبار اکانت تست را به ساعت بفرست (مثلاً 24):")


@router.message(TestStates.add_hours)
async def test_set_hours(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    txt = (msg.text or "").strip()
    try:
        hrs = int(float(txt))
        if hrs <= 0:
            raise ValueError()
    except Exception:
        return await msg.answer("عدد معتبر بفرست (مثلاً 24).")
    await state.update_data(duration_hours=hrs)
    await state.set_state(TestStates.add_name)
    await msg.answer("5️⃣ یک نام برای این اکانت تست بفرست (مثلاً: تست آلمان):")


@router.message(TestStates.add_name)
async def test_set_name(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    name = (msg.text or "").strip() or "اکانت تست"
    data = await state.get_data()
    cfg = get_test_config()
    cfg.setdefault("tests", []).append({
        "name": name,
        "server_id": data.get("server_id"),
        "inbound_id": data.get("inbound_id"),
        "traffic_mb": data.get("traffic_mb"),
        "duration_hours": data.get("duration_hours"),
    })
    _save(cfg)
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[_btn("⬅️ بازگشت به لیست", "ha:test:edit")]])
    await msg.answer(
        "✅ اکانت تست «" + name + "» اضافه شد.\n"
        "📥 حجم: " + str(data.get("traffic_mb")) + " مگابایت\n"
        "⏳ اعتبار: " + str(data.get("duration_hours")) + " ساعت",
        reply_markup=kb)
