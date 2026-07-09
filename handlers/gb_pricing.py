"""
سیستم قیمت‌گذاری بر اساس گیگابایت
هد ادمین قیمت هر گیگ رو تنظیم می‌کنه — کاربر حجم رو انتخاب می‌کنه
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from database.db import get_connection, get_setting, set_setting
from config.settings import ADMIN_IDS

router = Router()

# ─── کلیدهای تنظیمات ───────────────────────────────────────
PRICE_PER_GB_KEY = "price_per_gb_toman"
GB_STEPS_KEY = "gb_steps"  # مثلاً "10,20,30,50,100"

DEFAULT_PRICE_PER_GB = 5000
DEFAULT_GB_STEPS = [10, 20, 30, 50, 100]


def get_price_per_gb() -> int:
    try:
        return int(get_setting(PRICE_PER_GB_KEY, str(DEFAULT_PRICE_PER_GB)))
    except Exception:
        return DEFAULT_PRICE_PER_GB


def get_gb_steps() -> list[int]:
    try:
        raw = get_setting(GB_STEPS_KEY, "")
        if raw:
            return [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]
    except Exception:
        pass
    return DEFAULT_GB_STEPS


def calc_price(gb: int) -> int:
    return gb * get_price_per_gb()


# ─── States ─────────────────────────────────────────────────
class GBPurchaseStates(StatesGroup):
    custom_gb = State()


class GBAdminStates(StatesGroup):
    price_per_gb = State()
    gb_steps = State()


# ─── Keyboards ──────────────────────────────────────────────
def _btn(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


def gb_selector_kb():
    steps = get_gb_steps()
    price_per_gb = get_price_per_gb()
    rows = []
    for gb in steps:
        price = gb * price_per_gb
        rows.append([_btn(f"📦 {gb} گیگ — {price:,} تومان", f"gb_buy:{gb}")])
    rows.append([_btn("✍️ حجم دلخواه", "gb_buy:custom")])
    rows.append([_btn("⬅️ بازگشت", "user:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def gb_confirm_kb(gb: int):
    price = calc_price(gb)
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(f"✅ تأیید خرید {gb} گیگ — {price:,} تومان", f"gb_confirm:{gb}")],
        [_btn("⬅️ بازگشت", "gb_selector")],
    ])


# ─── User Handlers ───────────────────────────────────────────
@router.message(F.text.in_(["📦 خرید بر اساس حجم", "خرید حجمی"]))
async def gb_purchase_start(msg: Message):
    price_per_gb = get_price_per_gb()
    await msg.answer(
        f"📦 خرید بر اساس حجم\n\n"
        f"قیمت هر گیگابایت: {price_per_gb:,} تومان\n\n"
        f"حجم مورد نظر رو انتخاب کن:",
        reply_markup=gb_selector_kb()
    )


@router.callback_query(F.data == "gb_selector")
async def gb_selector(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    price_per_gb = get_price_per_gb()
    await cb.message.edit_text(
        f"📦 خرید بر اساس حجم\n\n"
        f"قیمت هر گیگابایت: {price_per_gb:,} تومان\n\n"
        f"حجم مورد نظر رو انتخاب کن:",
        reply_markup=gb_selector_kb()
    )
    await cb.answer()


@router.callback_query(F.data.startswith("gb_buy:"))
async def gb_buy(cb: CallbackQuery, state: FSMContext):
    val = cb.data.split(":")[1]
    if val == "custom":
        await cb.message.edit_text(
            "✍️ حجم دلخواه\n\n"
            f"قیمت هر گیگ: {get_price_per_gb():,} تومان\n\n"
            "تعداد گیگابایت رو بفرست (عدد):"
        )
        await state.set_state(GBPurchaseStates.custom_gb)
        await cb.answer()
        return

    gb = int(val)
    price = calc_price(gb)
    await cb.message.edit_text(
        f"📦 تأیید خرید\n\n"
        f"حجم: {gb} گیگابایت\n"
        f"قیمت: {price:,} تومان\n\n"
        f"پرداخت از کیف‌پول انجام می‌شه.",
        reply_markup=gb_confirm_kb(gb)
    )
    await cb.answer()


@router.message(GBPurchaseStates.custom_gb)
async def gb_custom_amount(msg: Message, state: FSMContext):
    if not msg.text or not msg.text.isdigit():
        return await msg.answer("فقط عدد قبول میشه")
    gb = int(msg.text.strip())
    if gb <= 0 or gb > 10000:
        return await msg.answer("بین 1 تا 10000 گیگابایت وارد کن")
    price = calc_price(gb)
    await state.clear()
    await msg.answer(
        f"📦 تأیید خرید\n\n"
        f"حجم: {gb} گیگابایت\n"
        f"قیمت: {price:,} تومان\n\n"
        f"پرداخت از کیف‌پول انجام می‌شه.",
        reply_markup=gb_confirm_kb(gb)
    )


@router.callback_query(F.data.startswith("gb_confirm:"))
async def gb_confirm(cb: CallbackQuery):
    gb = int(cb.data.split(":")[1])
    price = calc_price(gb)

    from database.wallet import get_wallet, deduct_from_wallet
    wallet = get_wallet(cb.from_user.id)
    balance = wallet["balance_toman"] if wallet else 0

    if balance < price:
        shortage = price - balance
        return await cb.answer(
            f"موجودی کافی نیست\n\n"
            f"نیاز: {price:,}T\n"
            f"موجودی: {balance:,}T\n"
            f"کمبود: {shortage:,}T\n\n"
            f"ابتدا کیف‌پول رو شارژ کن",
            show_alert=True
        )

    # ثبت سفارش
    from database.db import get_connection as _conn
    conn = _conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO orders
        (telegram_id, plan_id, service_name, plan_title, price_toman,
         duration_days, payment_method, final_price_toman, status)
        VALUES (?, 0, ?, ?, ?, 30, 'wallet', ?, 'approved')
        """,
        (cb.from_user.id, "خرید حجمی", f"{gb} گیگابایت", price, price)
    )
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # کسر از کیف‌پول
    deduct_from_wallet(cb.from_user.id, price, order_id)

    # اطلاع ادمین
    for admin_id in ADMIN_IDS:
        try:
            await cb.bot.send_message(
                chat_id=admin_id,
                text=f"🔔 سفارش حجمی جدید\n\n"
                     f"کاربر: {cb.from_user.full_name}\n"
                     f"آیدی: <code>{cb.from_user.id}</code>\n"
                     f"حجم: {gb} گیگابایت\n"
                     f"قیمت: {price:,} تومان\n"
                     f"سفارش: #{order_id}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [_btn(f"📤 ارسال کانفیگ #{order_id}", f"admin_send_config:{order_id}:{cb.from_user.id}")]
                ])
            )
        except Exception:
            pass

    await cb.message.edit_text(
        f"✅ سفارش ثبت شد\n\n"
        f"حجم: {gb} گیگابایت\n"
        f"قیمت: {price:,} تومان\n"
        f"سفارش: #{order_id}\n\n"
        f"⏳ کانفیگ اختصاصی شما توسط ادمین ارسال می‌شه"
    )
    await cb.answer()


# ─── Admin Handlers ──────────────────────────────────────────
def gb_admin_kb():
    price_per_gb = get_price_per_gb()
    steps = get_gb_steps()
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(f"💰 قیمت هر گیگ: {price_per_gb:,}T", "gb_admin:set_price")],
        [_btn(f"📊 مراحل انتخاب: {','.join(map(str,steps))}", "gb_admin:set_steps")],
        [_btn("⬅️ بازگشت", "ha:home")],
    ])


@router.callback_query(F.data == "ha:gb_pricing")
async def admin_gb_pricing(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("دسترسی ندارید", show_alert=True)
    price_per_gb = get_price_per_gb()
    steps = get_gb_steps()
    await cb.message.edit_text(
        f"📦 تنظیمات قیمت‌گذاری حجمی\n\n"
        f"قیمت هر گیگ: {price_per_gb:,} تومان\n"
        f"گزینه‌های حجم: {', '.join(str(s)+'GB' for s in steps)}\n\n"
        f"چی رو تغییر بدم?",
        reply_markup=gb_admin_kb()
    )
    await cb.answer()


@router.callback_query(F.data == "gb_admin:set_price")
async def admin_set_price(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    await cb.message.edit_text(
        f"💰 قیمت هر گیگابایت\n\n"
        f"قیمت فعلی: {get_price_per_gb():,} تومان\n\n"
        f"قیمت جدید رو بفرست (فقط عدد):"
    )
    await state.set_state(GBAdminStates.price_per_gb)
    await cb.answer()


@router.message(GBAdminStates.price_per_gb)
async def admin_save_price(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        return
    if not msg.text or not msg.text.isdigit():
        return await msg.answer("فقط عدد قبول میشه")
    price = int(msg.text.strip())
    set_setting(PRICE_PER_GB_KEY, str(price))
    await state.clear()
    await msg.answer(
        f"✅ قیمت هر گیگ تنظیم شد: {price:,} تومان",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [_btn("⬅️ بازگشت", "ha:gb_pricing")]
        ])
    )


@router.callback_query(F.data == "gb_admin:set_steps")
async def admin_set_steps(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    current = ",".join(map(str, get_gb_steps()))
    await cb.message.edit_text(
        f"📊 گزینه‌های حجم\n\n"
        f"فعلی: {current}\n\n"
        f"مقادیر جدید رو با کاما جدا کن:\n"
        f"مثال: 10,20,30,50,100"
    )
    await state.set_state(GBAdminStates.gb_steps)
    await cb.answer()


@router.message(GBAdminStates.gb_steps)
async def admin_save_steps(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        return
    raw = msg.text.strip()
    try:
        steps = [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]
        if not steps:
            return await msg.answer("حداقل یک عدد معتبر وارد کن")
    except Exception:
        return await msg.answer("فرمت نادرست! مثال: 10,20,30,50")
    set_setting(GB_STEPS_KEY, ",".join(map(str, steps)))
    await state.clear()
    await msg.answer(
        f"✅ گزینه‌ها ذخیره شدن: {', '.join(str(s)+'GB' for s in steps)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [_btn("⬅️ بازگشت", "ha:gb_pricing")]
        ])
    )
