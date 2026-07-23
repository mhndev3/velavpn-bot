from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import re

from config.settings import STARLINK_PRICE_PER_GB, STARLINK_MAX_VOLUME_GB
from database.db import get_connection, get_setting
from keyboards.user_keyboards import (
    shop_category_keyboard,
    services_keyboard,
    service_buy_keyboard,
    plans_keyboard,
    discount_decision_keyboard,
    starlink_volume_keyboard,
    payment_methods_for_order_keyboard,
)
from states.user_states import StarlinkOrderStates
from services.ui_service import send_screen
from services.price_service import payment_price_block
from services.ui_texts import T, TF
from handlers.btn_filter import Btn

router = Router()


class BuyStates(StatesGroup):
    waiting_config_name = State()
    waiting_quantity = State()


def _sanitize_name(raw: str) -> str:
    """نام کانفیگ را امن می‌کند: فقط حروف انگلیسی/عدد/._- ، بدون فاصله، حداکثر ۲۴ کاراکتر."""
    s = (raw or "").strip().replace(" ", "_")
    s = re.sub(r"[^A-Za-z0-9_.\-]", "", s)
    return s[:24]


def _random_config_name() -> str:
    """یک نام تصادفی و تمیز برای کانفیگ می‌سازد."""
    import random
    import string
    return "vpn-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))


def _random_config_names(count: int) -> list:
    """`count` نامِ تصادفیِ یکتا می‌سازد (برای سفارش چند-اکانتی)."""
    names, seen = [], set()
    guard = 0
    while len(names) < max(1, count) and guard < count * 20 + 50:
        guard += 1
        n = _random_config_name()
        if n not in seen:
            seen.add(n)
            names.append(n)
    return names


def _split_names(raw: str) -> list:
    """
    ورودی کاربر را به فهرست نام تبدیل می‌کند.

    جداکننده‌ها: کاما (انگلیسی و فارسی)، خط جدید، سمی‌کالن و فاصله.
    هر نام جداگانه امن‌سازی می‌شود و موارد خالی حذف می‌شوند.
    """
    if not raw:
        return []
    parts = re.split(r"[,\u060C;\n\r\t ]+", raw.strip())
    out = []
    for p in parts:
        s = _sanitize_name(p)
        if s:
            out.append(s)
    return out


def _expand_names(names: list, qty: int) -> list:
    """
    فهرست نام‌ها را به اندازهٔ `qty` می‌رساند و یکتا می‌کند.

    - اگر کاربر یک نام برای چند اکانت داده باشد، شماره‌گذاری می‌شود:
      name, name-2, name-3 …
    - اگر کمتر از تعداد داده باشد، بقیه از آخرین نام شماره‌گذاری می‌شوند.
    - اگر بیشتر داده باشد، فقط `qty` تای اول استفاده می‌شود.
    - نام‌های تکراری هم شماره می‌گیرند تا روی پنل تداخل نکنند.
    """
    qty = max(1, int(qty or 1))
    base = [n for n in (names or []) if n]
    if not base:
        return _random_config_names(qty)

    out, seen = [], set()

    def _add(candidate: str):
        c = candidate[:24] or "vpn"
        if c not in seen:
            seen.add(c)
            out.append(c)
            return
        i = 2
        while (c + "-" + str(i))[:24] in seen:
            i += 1
        c2 = (c + "-" + str(i))[:24]
        seen.add(c2)
        out.append(c2)

    for n in base[:qty]:
        _add(n)

    # کمبود را از آخرین نام شماره‌گذاری کن
    stem = base[-1]
    i = 2
    while len(out) < qty:
        _add(stem + "-" + str(i))
        i += 1

    return out[:qty]


def _name_kb():
    """کیبورد مرحلهٔ انتخاب نام: دکمهٔ ساخت نام رندوم + بازگشت."""
    from services.ui_texts import T
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=T("buy_btn_random_name", "🎲 ساخت نام رندوم"),
                              callback_data="buy:randname")],
        [InlineKeyboardButton(text=T("buy_btn_back", "⬅️ بازگشت"),
                              callback_data="u:menu")],
    ])


def _location_label_for_plan(plan: dict) -> str:
    """لوکیشن واقعی خرید = برچسب سرورِ پلن (مثل «آلمان ۱»)؛ اگر نبود، اسم سرویس."""
    sid = plan.get("server_id") or 0
    if sid:
        try:
            from database.db import get_server
            srv = get_server(sid)
            if srv and srv.get("label"):
                return srv["label"]
        except Exception:
            pass
    return plan.get("service_name") or "استارلینک اختصاصی"


def _create_db_order(telegram_id: int, plan: dict, plan_id: int, config_name: str, quantity: int = 1) -> int:
    conn = get_connection()
    cur = conn.cursor()
    try:
        qty = max(1, int(quantity or 1))
        total = plan["price_toman"] * qty
        cur.execute("""
            INSERT INTO orders
            (telegram_id, plan_id, service_name, plan_title, price_toman,
             duration_days, status, discount_amount, final_price_toman,
             referral_processed, config_name, quantity)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', 0, ?, 0, ?, ?)
        """, (
            telegram_id, plan_id, _location_label_for_plan(plan), plan["title"],
            total, plan.get("duration_days", 30), total,
            config_name or "", qty,
        ))
        order_id = cur.lastrowid
        conn.commit()
        return order_id
    finally:
        conn.close()


def _get_active_plan(plan_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, s.name as service_name, s.category
        FROM plans p
        JOIN services s ON s.id = p.service_id
        WHERE p.id = ? AND p.is_active = 1 AND s.is_active = 1
    """, (plan_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def starlink_price_per_gb() -> int:
    """قیمت هر گیگ استارلینک — از تنظیمات دیتابیس (قابل تغییر توسط هد ادمین) یا fallback"""
    try:
        val = get_setting("starlink_price_per_gb", "")
        if val and str(val).isdigit():
            return int(val)
    except Exception:
        pass
    return int(STARLINK_PRICE_PER_GB)

CATEGORY_TITLES = {
    "v2ray": "🟢 V2Ray VIP",
    "l2tp": "🟠 L2TP نامحدود",
    "openvpn": "🔵 OpenVPN تک‌کاربره",
    "starlink": "استارلینک اختصاصی",
}


def rows_to_dicts(cursor, rows):
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def get_services_by_category(category: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, category, service_type, name, description
    FROM services
    WHERE category = ? AND is_active = 1
    ORDER BY id ASC
    """, (category,))
    rows = cursor.fetchall()
    services = rows_to_dicts(cursor, rows)
    conn.close()
    return services


def get_services_by_category_and_type(category: str, service_type: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, category, service_type, name, description
    FROM services
    WHERE category = ? AND service_type = ? AND is_active = 1
    ORDER BY id ASC
    """, (category, service_type))
    rows = cursor.fetchall()
    services = rows_to_dicts(cursor, rows)
    conn.close()
    return services


def get_service(service_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, category, service_type, name, description
    FROM services
    WHERE id = ? AND is_active = 1
    """, (service_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    service = rows_to_dicts(cursor, [row])[0]
    conn.close()
    return service


def get_plans_by_service(service_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, service_id, title, price_toman, duration_days
    FROM plans
    WHERE service_id = ? AND is_active = 1
    ORDER BY duration_days ASC, price_toman ASC
    """, (service_id,))
    rows = cursor.fetchall()
    plans = rows_to_dicts(cursor, rows)
    conn.close()
    return plans


def get_plan(plan_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT plans.id, plans.service_id, plans.title, plans.price_toman,
           plans.duration_days, services.name AS service_name,
           services.category AS category, services.service_type AS service_type
    FROM plans
    JOIN services ON services.id = plans.service_id
    WHERE plans.id = ? AND plans.is_active = 1
    """, (plan_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    plan = rows_to_dicts(cursor, [row])[0]
    conn.close()
    return plan


def get_starlink_plan():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT plans.id, services.name AS service_name
    FROM plans
    JOIN services ON services.id = plans.service_id
    WHERE services.category = 'starlink' AND plans.is_active = 1 AND services.is_active = 1
    ORDER BY plans.id ASC
    LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {"id": row[0], "service_name": row[1]}



def get_all_starlink_plans():
    """همه پلن‌های فعال استارلینک از دیتابیس"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, p.title, p.price_toman, p.duration_days, p.traffic_gb,
               p.server_id, p.inbound_id, s.name as service_name
        FROM plans p
        JOIN services s ON s.id = p.service_id
        WHERE s.category = 'starlink' AND p.is_active = 1 AND s.is_active = 1
        ORDER BY p.price_toman ASC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


# ─── جریان سلسله‌مراتبی خرید: لوکیشن → مدت → حجم ─────────────
_FA_TR = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _fa(s):
    # اعداد لاتین می‌مانند (هم درخواست کارفرما، هم جلوگیری از به‌هم‌ریختگی جهت متن RTL)
    return str(s)


def _dur_label(days):
    d = int(days or 0)
    if d <= 0:
        return T("u_no_expiry", "بی‌انقضا")
    months = round(d / 30) or 1
    # RLM در ابتدا تا عدد لاتین کنار «ماهه» درست (راست‌به‌چپ) نمایش داده شود
    return "\u200f" + str(months) + T("u_month_suffix", " ماهه")


def _starlink_locations():
    """[(server_id, label)] برای سرورهایی که پلن استارلینک فعال دارند (به ترتیب)."""
    from database.db import get_all_servers
    label_by_id = {}
    try:
        for s in get_all_servers():
            label_by_id[s["id"]] = s["label"]
    except Exception:
        pass
    out, seen = [], set()
    for p in get_all_starlink_plans():
        sid = p.get("server_id") or 0
        if sid not in seen:
            seen.add(sid)
            out.append((sid, label_by_id.get(sid, T("shop_loc_fallback", "لوکیشن پیش‌فرض"))))
    return out


def _plans_for_location(sid):
    return [p for p in get_all_starlink_plans() if (p.get("server_id") or 0) == int(sid)]


def _loc_kb():
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    rows = [[InlineKeyboardButton(text=lbl, callback_data="sl_loc:" + str(sid))]
            for sid, lbl in _starlink_locations()]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _dur_kb(sid, show_back=True):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    days_seen = []
    for p in _plans_for_location(sid):
        d = int(p.get("duration_days") or 0)
        if d not in days_seen:
            days_seen.append(d)
    days_seen.sort()
    rows = [[InlineKeyboardButton(text="⏳ " + _dur_label(d),
                                  callback_data="sl_dur:" + str(sid) + ":" + str(d))]
            for d in days_seen]
    if show_back:
        rows.append([InlineKeyboardButton(text=T("shop_btn_back", "⬅️ بازگشت"), callback_data="sl_back_loc")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _plans_kb(sid, days):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    box = get_setting("emoji_box", "📦")
    rows = []
    for p in _plans_for_location(sid):
        if int(p.get("duration_days") or 0) != int(days):
            continue
        gb = (_fa(p["traffic_gb"]) + T("u_gig", " گیگ")) if p.get("traffic_gb") else T("u_unlimited", "نامحدود")
        price = _fa("{:,}".format(p["price_toman"]))
        rows.append([InlineKeyboardButton(text="\u200f" + box + " " + gb + " | " + price + T("u_toman", " تومان"),
                                          callback_data="buy_plan:" + str(p["id"]))])
    rows.append([InlineKeyboardButton(text=T("shop_btn_back", "⬅️ بازگشت"), callback_data="sl_loc:" + str(sid))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _buy_entry_content():
    """(text, keyboard) برای ورود به خرید؛ اگر پلنی نبود None."""
    locs = _starlink_locations()
    if not locs:
        return None
    # همیشه مرحلهٔ انتخاب لوکیشن نمایش داده می‌شود (حتی با یک لوکیشن)
    return (T("shop_loc_title", "<b>انتخاب لوکیشن</b>\n━━━━━━━━━━━━━━\n\nلوکیشن مورد نظر را انتخاب کنید:"),
            _loc_kb())


def create_starlink_order(telegram_id: int, volume_gb: int):
    starlink_plan = get_starlink_plan()
    if not starlink_plan:
        return None

    price = int(volume_gb) * starlink_price_per_gb()
    plan_title = TF("shop_sl_plan_title", "استارلینک {gb} گیگابایت | 1 ماهه | کاربر نامحدود", gb=volume_gb)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO orders (
        telegram_id,
        plan_id,
        service_name,
        plan_title,
        price_toman,
        duration_days,
        payment_method,
        status,
        discount_code,
        discount_amount,
        final_price_toman,
        referral_processed
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        telegram_id,
        starlink_plan["id"],
        starlink_plan["service_name"],
        plan_title,
        price,
        30,
        None,
        "pending",
        None,
        0,
        price,
        0,
    ))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return order_id, price, plan_title


def parse_volume(text: str):
    if not text:
        return None
    cleaned = text.strip().replace("گیگ", "").replace("GB", "").replace("gb", "").strip()
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    for i, digit in enumerate(persian_digits):
        cleaned = cleaned.replace(digit, str(i))
    for i, digit in enumerate(arabic_digits):
        cleaned = cleaned.replace(digit, str(i))
    if not cleaned.isdigit():
        return None
    return int(cleaned)


def is_valid_starlink_volume(volume: int):
    return 1 <= int(volume) <= int(STARLINK_MAX_VOLUME_GB)


async def show_starlink_intro(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    content = _buy_entry_content()
    if content:
        await send_screen(callback, state, content[0], reply_markup=content[1], banner_key="starlink")
    else:
        # fallback: volume keyboard
        price = starlink_price_per_gb()
        text = TF(
            "shop_sl_intro",
            "<b>Starlink اختصاصی WGV</b>\n"
            "━━━━━━━━━━━━━━\n\n"
            "قیمت هر گیگابایت: {price} تومان\n"
            "حجم قابل سفارش: ۱ تا {max} گیگابایت\n\n"
            "حجم مورد نظر را انتخاب کنید:",
            price="{:,}".format(price), max=STARLINK_MAX_VOLUME_GB,
        )
        await send_screen(callback, state, text, reply_markup=starlink_volume_keyboard(), banner_key="starlink")
        await state.set_state(StarlinkOrderStates.waiting_for_volume_gb)


async def finalize_starlink_order(target, state: FSMContext, volume_gb: int, from_callback: bool = False):
    if not is_valid_starlink_volume(volume_gb):
        text = TF("shop_vol_invalid",
                  "حجم انتخابی باید بین ۱ تا {max} گیگابایت باشد. لطفاً عدد معتبر وارد کنید.",
                  max=STARLINK_MAX_VOLUME_GB)
        if from_callback:
            await target.answer(text, show_alert=True)
        else:
            await target.answer(text)
        return

    user_id = target.from_user.id
    order_data = create_starlink_order(user_id, volume_gb)
    if not order_data:
        text = T("shop_sl_missing",
                 "سرویس استارلینک هنوز در دیتابیس فعال نیست. یک بار بات را ری‌استارت کنید تا داده‌های اولیه ساخته شود.")
        if from_callback:
            await target.answer(text, show_alert=True)
        else:
            await target.answer(text)
        return

    order_id, price, plan_title = order_data
    text = TF(
        "shop_sl_invoice",
        "✅ سفارش استارلینک ثبت شد\n"
        "━━━━━━━━━━━━━━\n\n"
        "🧾 شماره سفارش: <code>{order_id}</code>\n"
        "سرویس: استارلینک اختصاصی\n"
        "📦 حجم: {gb} گیگابایت\n"
        "👥 تعداد کاربر: نامحدود\n"
        "⏳ اعتبار: 1 ماهه\n"
        "{price_block}\n\n"
        "روش پرداخت موردنظر را انتخاب کنید. کارت‌به‌کارت از طریق هماهنگی با ادمین انجام می‌شود و پرداخت ارزی با USDT یا TRX قابل ثبت است.",
        order_id=order_id, gb=volume_gb, price_block=payment_price_block(price),
    )

    await send_screen(target, state, text, reply_markup=payment_methods_for_order_keyboard(order_id), banner_key="payment")
    await state.clear()


@router.message(Btn("btn_buy", "⚡ خرید کانفیگ", "خرید کانفیگ", "خرید اشتراک"))
async def buy_subscription_handler(message: Message, state: FSMContext):
    await state.clear()
    # مستقیم به صفحه استارلینک برو
    await show_starlink_intro_msg(message, state)


async def show_starlink_intro_msg(target, state: FSMContext):
    """نمایش صفحه استارلینک برای message"""
    await state.clear()
    content = _buy_entry_content()
    if content:
        await target.answer(content[0], reply_markup=content[1], parse_mode="HTML")
    else:
        price = starlink_price_per_gb()
        text = TF("shop_sl_intro_short", "قیمت هر گیگ: {price} تومان\nحجم را انتخاب کنید:",
                  price="{:,}".format(price))
        await target.answer(text, reply_markup=starlink_volume_keyboard(), parse_mode="HTML")
        await state.set_state(StarlinkOrderStates.waiting_for_volume_gb)


@router.callback_query(F.data == "sl_back_loc")
async def sl_back_loc_handler(cb: CallbackQuery, state: FSMContext):
    content = _buy_entry_content()
    if content:
        await send_screen(cb, state, content[0], reply_markup=content[1], banner_key="starlink")
    await cb.answer()


@router.callback_query(F.data.startswith("sl_loc:"))
async def sl_loc_handler(cb: CallbackQuery, state: FSMContext):
    sid = int(cb.data.split(":")[1])
    lbl = dict(_starlink_locations()).get(sid, T("shop_loc_fallback", "لوکیشن"))
    text = TF("shop_dur_title",
              "<b>{loc}</b>\n━━━━━━━━━━━━━━\n\nمدت اشتراک را انتخاب کنید:", loc=lbl)
    await send_screen(cb, state, text, reply_markup=_dur_kb(sid, show_back=True), banner_key="starlink")
    await cb.answer()


@router.callback_query(F.data.startswith("sl_dur:"))
async def sl_dur_handler(cb: CallbackQuery, state: FSMContext):
    parts = cb.data.split(":")
    sid, days = int(parts[1]), int(parts[2])
    lbl = dict(_starlink_locations()).get(sid, T("shop_loc_fallback", "لوکیشن"))
    text = TF("shop_vol_title",
              "<b>{loc}</b>\n"
              "مدت: {dur}\n"
              "━━━━━━━━━━━━━━\n\nحجم مورد نظر را انتخاب کنید:",
              loc=lbl, dur=_dur_label(days))
    await send_screen(cb, state, text, reply_markup=_plans_kb(sid, days), banner_key="starlink")
    await cb.answer()


@router.callback_query(F.data.startswith("shop_category:"))
async def shop_category_handler(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split(":")[1]
    title = CATEGORY_TITLES.get(category)
    if not title:
        await callback.answer(T("shop_cat_invalid", "دسته‌بندی نامعتبر است."), show_alert=True)
        return
    title = T("shop_cat_" + category, title)

    if category == "starlink":
        await show_starlink_intro(callback, state)
        return

    services = get_services_by_category(category)
    if not services:
        await send_screen(
            callback,
            state,
            TF("shop_cat_empty",
               "{title}\n\nفعلاً پلنی برای این سرور فعال نیست. لطفاً کمی بعد دوباره بررسی کنید.",
               title=title),
            reply_markup=shop_category_keyboard(),
            banner_key=category,
        )
        return

    await send_screen(
        callback,
        state,
        TF("shop_cat_services",
           "{title}\n━━━━━━━━━━━━━━\n\nیکی از سرویس‌های فعال را انتخاب کنید. پس از ثبت سفارش، مسیر پرداخت و ارسال رسید نمایش داده می‌شود.",
           title=title),
        reply_markup=services_keyboard(services, category),
        banner_key=category,
    )


@router.callback_query(F.data.startswith("starlink_volume:"))
async def starlink_volume_callback(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":")[1]
    if value == "custom":
        await send_screen(
            callback,
            state,
            TF("shop_vol_custom",
               "✍️ <b>وارد کردن حجم دلخواه</b>\n━━━━━━━━━━━━━━\n\nلطفاً حجم موردنظر را فقط به عدد وارد کنید.\n\nمثال: <code>2</code> یعنی سفارش ۲ گیگابایت\n"
               "محدوده مجاز سفارش: ۱ تا {max} گیگابایت",
               max=STARLINK_MAX_VOLUME_GB),
            banner_key="starlink",
        )
        await state.set_state(StarlinkOrderStates.waiting_for_volume_gb)
        return

    volume = parse_volume(value)
    await finalize_starlink_order(callback, state, volume, from_callback=True)


@router.message(StarlinkOrderStates.waiting_for_volume_gb)
async def starlink_custom_volume_message(message: Message, state: FSMContext):
    volume = parse_volume(message.text or "")
    if volume is None:
        await message.answer(
            T("shop_vol_numeric",
              "لطفاً فقط عدد حجم را ارسال کنید.\n"
              "مثال: <code>2</code> برای سفارش ۲ گیگابایت")
        )
        return
    await finalize_starlink_order(message, state, volume, from_callback=False)


@router.callback_query(F.data.startswith("shop_type:"))
async def shop_type_handler(callback: CallbackQuery):
    _, category, buy_type = callback.data.split(":")
    services = get_services_by_category_and_type(category=category, service_type=buy_type)
    title = T("shop_cat_" + category, CATEGORY_TITLES.get(category, "سرویس VPN"))
    if not services:
        await send_screen(callback, None,
                          TF("shop_type_empty", "{title}\n\nفعلاً سرویسی در این بخش ثبت نشده است.", title=title),
                          reply_markup=shop_category_keyboard())
        return
    await send_screen(callback, None,
                      TF("shop_type_pick", "{title}\n\nلطفاً سرویس مورد نظر را انتخاب کنید:", title=title),
                      reply_markup=services_keyboard(services, category), banner_key=category)


@router.callback_query(F.data.startswith("service:"))
async def service_detail_handler(callback: CallbackQuery):
    service_id = int(callback.data.split(":")[1])
    service = get_service(service_id)
    if not service:
        await callback.answer(T("shop_svc_gone", "سرویس پیدا نشد."), show_alert=True)
        return

    label = T("shop_svc_single", "تک‌کاربره") if service["service_type"] == "single" else T("shop_svc_multi", "چندکاربره / سازمانی")
    text = TF(
        "shop_svc_detail",
        "✨ <b>{name}</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "نوع سرویس: {type}\n\n"
        "{desc}\n\n"
        "برای مشاهده پلن‌ها و ثبت سفارش، دکمه زیر را انتخاب کنید.",
        name=service["name"], type=label,
        desc=service["description"] or T("shop_svc_no_desc", "توضیحات این سرویس به‌زودی تکمیل می‌شود."),
    )
    await send_screen(callback, None, text, reply_markup=service_buy_keyboard(service_id), banner_key=service["category"])


@router.callback_query(F.data.startswith("buy_service:"))
async def buy_service_handler(callback: CallbackQuery):
    service_id = int(callback.data.split(":")[1])
    plans = get_plans_by_service(service_id)
    if not plans:
        await send_screen(callback, None, T("shop_svc_no_plans", "برای این سرویس هنوز پلنی ثبت نشده است."))
        return

    text = T(
        "shop_vip_pick",
        "💎 انتخاب پلن VIP\n"
        "━━━━━━━━━━━━━━\n\n"
        "پلن مناسب مصرف خود را انتخاب کنید. مبلغ هر پلن در مرحله بعد همراه با معادل USDT و TRX نمایش داده می‌شود."
    )
    await send_screen(callback, None, text, reply_markup=plans_keyboard(plans, service_id, callback.from_user.id), banner_key="payment")


@router.callback_query(F.data.startswith("select_plan:"))
async def select_plan_handler(callback: CallbackQuery):
    plan_id = int(callback.data.split(":")[1])
    plan = get_plan(plan_id)
    if not plan:
        await callback.answer(T("shop_plan_notfound", "پلن پیدا نشد."), show_alert=True)
        return

    from database.sub_admin_pricing import get_price_for_user
    final_price = get_price_for_user(callback.from_user.id, plan_id)

    text = TF(
        "shop_plan_selected",
        "✅ پلن انتخاب شد\n"
        "━━━━━━━━━━━━━━\n\n"
        "🔐 سرویس: {service}\n"
        "💠 پلن: {plan}\n"
        "⏳ مدت اعتبار: {dur}\n"
        "{price_block}\n\n"
        "در صورت داشتن کد تخفیف، آن را اعمال کنید. در غیر این صورت، پرداخت را ادامه دهید.",
        service=plan["service_name"], plan=plan["title"],
        dur=_dur_label(plan["duration_days"]), price_block=payment_price_block(final_price),
    )
    await send_screen(callback, None, text, reply_markup=discount_decision_keyboard(plan_id), banner_key="payment")




@router.callback_query(F.data.startswith("buy_plan:"))
async def buy_plan_from_db(callback: CallbackQuery, state: FSMContext):
    """خرید پلن — ابتدا نام دلخواه کانفیگ از مشتری گرفته می‌شود."""
    from services.ui_texts import T
    plan_id = int(callback.data.split(":")[1])
    plan = _get_active_plan(plan_id)
    if not plan:
        return await callback.answer(T("shop_plan_gone", "این پلن دیگر موجود نیست."), show_alert=True)

    await state.clear()
    await state.update_data(buy_plan_id=plan_id)
    await _ask_quantity(callback.message, state)
    await callback.answer()


async def _ask_quantity(target, state: FSMContext):
    """اول تعداد اکانت را می‌پرسد (بعد نام‌ها، چون تعداد نام‌ها به آن بستگی دارد)."""
    from services.ui_texts import T
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    await state.set_state(BuyStates.waiting_quantity)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=T("buy_btn_back", "⬅️ بازگشت"), callback_data="u:menu")],
    ])
    await target.answer(
        T("buy_qty_title", "🔢 <b>چند اکانت می‌خواهی؟</b>") + "\n"
        "━━━━━━━━━━━━━━\n\n"
        + T("buy_qty_hint", "تعداد اکانت موردنظرت را به عدد بفرست.\nمثلاً: <code>1</code> یا <code>10</code>"),
        reply_markup=kb,
    )


async def _ask_config_name(target, state: FSMContext, qty: int):
    """
    نام کانفیگ‌ها را می‌پرسد؛ راهنما بر اساس تعداد تنظیم می‌شود.

    برای سفارش چند-اکانتی توضیح می‌دهد که چطور چند نام وارد شود و اگر یک نام
    بدهد چه اتفاقی می‌افتد.
    """
    from services.ui_texts import T, TF
    await state.set_state(BuyStates.waiting_config_name)

    rules = T(
        "buy_name_rules",
        "📌 <b>قواعد نام:</b>\n"
        "• فقط حروف <b>انگلیسی</b> و عدد (فارسی قابل قبول نیست)\n"
        "• بدون فاصله — به‌جای فاصله از <code>_</code> یا <code>-</code> استفاده کن\n"
        "• بدون علامت‌های خاص مثل <code>@ # $ % / \\ ( )</code>\n"
        "• حداکثر ۲۴ کاراکتر",
    )

    if qty > 1:
        body = TF(
            "buy_name_multi_hint",
            "برای <b>{qty}</b> اکانت، {qty} نام بفرست — با کاما یا خط جدید جدا کن.\n\n"
            "مثال:\n<code>ali-1, ali-2, ali-3</code>\n\n"
            "🔹 اگر فقط <b>یک</b> نام بفرستی، بقیه خودکار شماره می‌گیرند "
            "(مثلاً <code>ali</code> → <code>ali</code>, <code>ali-2</code>, <code>ali-3</code>)\n"
            "🔹 اگر کمتر از {qty} نام بفرستی، بقیه از آخرین نام ساخته می‌شوند\n"
            "🔹 یا دکمهٔ زیر را بزن تا برای هر {qty} اکانت نام رندوم ساخته شود",
            qty=_fa(qty),
        )
    else:
        body = T(
            "buy_name_single_hint",
            "یک نام دلخواه برای کانفیگت بفرست.\n"
            "مثلاً: <code>ali-vpn</code>\n\n"
            "یا برای ساخت خودکار، دکمهٔ زیر را بزن:",
        )

    await target.answer(
        T("buy_name_title", "🏷 <b>نام کانفیگت را انتخاب کن</b>") + "\n"
        "━━━━━━━━━━━━━━\n\n" + body + "\n\n" + rules,
        reply_markup=_name_kb(),
    )


@router.callback_query(BuyStates.waiting_config_name, F.data == "buy:randname")
async def buy_random_name(callback: CallbackQuery, state: FSMContext):
    """ساخت نام رندوم — برای سفارش چند-اکانتی، به تعداد اکانت‌ها نام می‌سازد."""
    data = await state.get_data()
    qty = int(data.get("buy_qty") or 1)
    names = _random_config_names(qty)
    await callback.answer(T("buy_name_made", "🎲 نام ساخته شد"))
    if qty > 1:
        shown = "\n".join("• <code>" + n + "</code>" for n in names)
        await callback.message.answer(
            TF("buy_names_show_multi", "🏷 نام‌های ساخته‌شده ({qty} عدد):\n{names}",
               qty=_fa(qty), names=shown)
        )
    else:
        await callback.message.answer(
            TF("buy_name_show", "🏷 نام کانفیگ: <code>{name}</code>", name=names[0])
        )
    await _finalize_buy_order(callback.message, state, callback.from_user.id, names, qty)


@router.message(BuyStates.waiting_config_name)
async def buy_config_name(msg: Message, state: FSMContext):
    data = await state.get_data()
    plan_id = data.get("buy_plan_id")
    qty = int(data.get("buy_qty") or 1)
    if not plan_id:
        await state.clear()
        return

    raw = (msg.text or "").strip()
    # رد کردن مرحله: نام خودکار ساخته می‌شود
    if raw.lower() in ("skip", "رد", "-", "بی‌خیال", "بیخیال"):
        names = _random_config_names(qty)
    else:
        given = _split_names(raw)
        if not given:
            # هیچ کاراکتر مجازی نمانده (مثلاً کاربر فارسی فرستاده)
            return await msg.answer(
                T("buy_name_invalid",
                  "❌ نام معتبر نبود.\n\n"
                  "لطفاً فقط از حروف <b>انگلیسی</b> و عدد استفاده کن؛ بدون فاصله و "
                  "علامت خاص. مثلاً: <code>ali-vpn</code>\n\n"
                  "یا دکمهٔ «🎲 ساخت نام رندوم» را بزن."),
                reply_markup=_name_kb(),
            )
        names = _expand_names(given, qty)
        # اگر کاربر کمتر از تعداد نام داد، خبر بده که بقیه چطور ساخته شد
        if qty > 1 and len(given) < qty:
            shown = "\n".join("• <code>" + n + "</code>" for n in names)
            await msg.answer(
                TF("buy_names_autofilled",
                   "ℹ️ {given} نام فرستادی و {qty} اکانت سفارش دادی؛ بقیه خودکار ساخته شد:\n{names}",
                   given=_fa(len(given)), qty=_fa(qty), names=shown)
            )

    await _finalize_buy_order(msg, state, msg.from_user.id, names, qty)


async def _finalize_buy_order(target, state: FSMContext, user_id: int, names: list, qty: int):
    """سفارش را در دیتابیس می‌سازد و فاکتور را نمایش می‌دهد."""
    data = await state.get_data()
    plan_id = data.get("buy_plan_id")
    plan = _get_active_plan(plan_id) if plan_id else None
    if not plan:
        await state.clear()
        return await target.answer(T("shop_plan_gone", "این پلن دیگر موجود نیست."))

    names = _expand_names(names, qty)
    config_name = ",".join(names)
    order_id = _create_db_order(user_id, plan, plan_id, config_name, qty)
    await state.clear()

    unit = plan["price_toman"]
    total = unit * qty
    gb = str(plan["traffic_gb"]) + " GB" if plan.get("traffic_gb") else T("u_unlimited", "نامحدود")
    dur = _dur_label(plan["duration_days"]) if plan.get("duration_days") else T("u_no_expiry", "بی‌انقضا")

    if qty > 1:
        name_line = TF("shop_invoice_names_line", "🏷 نام‌ها: {names}\n",
                       names="، ".join(names))
    else:
        name_line = TF("shop_invoice_name_line", "🏷 نام کانفیگ: {name}\n", name=names[0])

    qty_block = TF(
        "shop_invoice_qty_block",
        "🔢 تعداد: {qty} عدد\n"
        "💵 قیمت واحد: {unit} تومان\n",
        qty="{:,}".format(qty), unit="{:,}".format(unit),
    ) if qty > 1 else ""

    text = TF(
        "shop_invoice",
        "✅ سفارش ثبت شد\n"
        "━━━━━━━━━━━━━━\n\n"
        "{name_line}"
        "پلن: {plan}\n"
        "حجم: {gb}\n"
        "مدت: {dur}\n"
        "{qty_block}"
        "💰 مبلغ قابل پرداخت: {total} تومان\n\n"
        "{hint}",
        name_line=name_line, plan=plan["title"], gb=gb, dur=dur, qty_block=qty_block,
        total="{:,}".format(total),
        hint=T("disc_decision_hint", "اگر کد تخفیف داری، اعمالش کن؛ در غیر این صورت بدون کد ادامه بده:"),
    )
    from keyboards.user_keyboards import discount_decision_for_order
    await target.answer(text, reply_markup=discount_decision_for_order(order_id))


@router.message(BuyStates.waiting_quantity)
async def buy_quantity(msg: Message, state: FSMContext):
    """تعداد را می‌گیرد و بعد نام‌ها را می‌پرسد."""
    from services.ui_texts import T
    data = await state.get_data()
    plan_id = data.get("buy_plan_id")
    if not plan_id:
        await state.clear()
        return

    # تبدیل ارقام فارسی به انگلیسی و اعتبارسنجی
    raw = (msg.text or "").strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
    if not raw.isdigit() or int(raw) < 1:
        return await msg.answer(T("buy_qty_invalid", "❌ لطفاً یک عدد معتبر بفرست (مثلاً 1 تا 100)."))
    qty = int(raw)
    if qty > 100:
        return await msg.answer(T("buy_qty_toomany", "❌ حداکثر ۱۰۰ اکانت در هر سفارش. عدد کمتری بفرست."))

    plan = _get_active_plan(plan_id)
    if not plan:
        await state.clear()
        return await msg.answer(T("shop_plan_gone", "این پلن دیگر موجود نیست."))

    await state.update_data(buy_qty=qty)
    await _ask_config_name(msg, state, qty)


@router.callback_query(F.data == "shop_back:categories")
async def back_to_categories_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text = T(
        "shop_back_title",
        "⚡ خرید کانفیگ VIP\n"
        "━━━━━━━━━━━━━━\n\n"
        "لطفاً سرویس موردنظر خود را انتخاب کنید:"
    )
    await send_screen(callback, state, text, reply_markup=shop_category_keyboard(), banner_key="shop")


@router.callback_query(F.data.startswith("shop_back:type:"))
async def back_to_shop_type_handler(callback: CallbackQuery, state: FSMContext):
    await back_to_categories_handler(callback, state)
