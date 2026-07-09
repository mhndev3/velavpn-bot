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
from handlers.btn_filter import Btn

router = Router()


class BuyStates(StatesGroup):
    waiting_config_name = State()


def _sanitize_name(raw: str) -> str:
    """نام کانفیگ را امن می‌کند: فقط حروف انگلیسی/عدد/._- ، بدون فاصله، حداکثر ۲۴ کاراکتر."""
    s = (raw or "").strip().replace(" ", "_")
    s = re.sub(r"[^A-Za-z0-9_.\-]", "", s)
    return s[:24]


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


def _create_db_order(telegram_id: int, plan: dict, plan_id: int, config_name: str) -> int:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO orders
            (telegram_id, plan_id, service_name, plan_title, price_toman,
             duration_days, status, discount_amount, final_price_toman,
             referral_processed, config_name)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', 0, ?, 0, ?)
        """, (
            telegram_id, plan_id, _location_label_for_plan(plan), plan["title"],
            plan["price_toman"], plan.get("duration_days", 30), plan["price_toman"],
            config_name or "",
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
        return "بی‌انقضا"
    months = round(d / 30) or 1
    # RLM در ابتدا تا عدد لاتین کنار «ماهه» درست (راست‌به‌چپ) نمایش داده شود
    return "\u200f" + str(months) + " ماهه"


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
            out.append((sid, label_by_id.get(sid, "لوکیشن پیش‌فرض")))
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
        rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="sl_back_loc")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _plans_kb(sid, days):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    box = get_setting("emoji_box", "📦")
    rows = []
    for p in _plans_for_location(sid):
        if int(p.get("duration_days") or 0) != int(days):
            continue
        gb = (_fa(p["traffic_gb"]) + " گیگ") if p.get("traffic_gb") else "نامحدود"
        price = _fa("{:,}".format(p["price_toman"]))
        rows.append([InlineKeyboardButton(text="\u200f" + box + " " + gb + " | " + price + " تومان",
                                          callback_data="buy_plan:" + str(p["id"]))])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="sl_loc:" + str(sid))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _buy_entry_content():
    """(text, keyboard) برای ورود به خرید؛ اگر پلنی نبود None."""
    locs = _starlink_locations()
    if not locs:
        return None
    # همیشه مرحلهٔ انتخاب لوکیشن نمایش داده می‌شود (حتی با یک لوکیشن)
    return ("<b>انتخاب لوکیشن</b>\n━━━━━━━━━━━━━━\n\nلوکیشن مورد نظر را انتخاب کنید:",
            _loc_kb())


def create_starlink_order(telegram_id: int, volume_gb: int):
    starlink_plan = get_starlink_plan()
    if not starlink_plan:
        return None

    price = int(volume_gb) * starlink_price_per_gb()
    plan_title = f"استارلینک {volume_gb} گیگابایت | 1 ماهه | کاربر نامحدود"

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
        text = (
            "<b>Starlink اختصاصی WGV</b>\n"
            "━━━━━━━━━━━━━━\n\n"
            f"قیمت هر گیگابایت: {price:,} تومان\n"
            f"حجم قابل سفارش: ۱ تا {STARLINK_MAX_VOLUME_GB} گیگابایت\n\n"
            "حجم مورد نظر را انتخاب کنید:"
        )
        await send_screen(callback, state, text, reply_markup=starlink_volume_keyboard(), banner_key="starlink")
        await state.set_state(StarlinkOrderStates.waiting_for_volume_gb)


async def finalize_starlink_order(target, state: FSMContext, volume_gb: int, from_callback: bool = False):
    if not is_valid_starlink_volume(volume_gb):
        text = f"حجم انتخابی باید بین ۱ تا {STARLINK_MAX_VOLUME_GB} گیگابایت باشد. لطفاً عدد معتبر وارد کنید."
        if from_callback:
            await target.answer(text, show_alert=True)
        else:
            await target.answer(text)
        return

    user_id = target.from_user.id
    order_data = create_starlink_order(user_id, volume_gb)
    if not order_data:
        text = "سرویس استارلینک هنوز در دیتابیس فعال نیست. یک بار بات را ری‌استارت کنید تا داده‌های اولیه ساخته شود."
        if from_callback:
            await target.answer(text, show_alert=True)
        else:
            await target.answer(text)
        return

    order_id, price, plan_title = order_data
    text = (
        "✅ سفارش استارلینک ثبت شد\n"
        "━━━━━━━━━━━━━━\n\n"
        f"🧾 شماره سفارش: <code>{order_id}</code>\n"
        "سرویس: استارلینک اختصاصی\n"
        f"📦 حجم: {volume_gb} گیگابایت\n"
        "👥 تعداد کاربر: نامحدود\n"
        "⏳ اعتبار: 1 ماهه\n"
        f"{payment_price_block(price)}\n\n"
        "روش پرداخت موردنظر را انتخاب کنید. کارت‌به‌کارت از طریق هماهنگی با ادمین انجام می‌شود و پرداخت ارزی با USDT یا TRX قابل ثبت است."
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
        text = "قیمت هر گیگ: " + "{:,}".format(price) + " تومان\nحجم را انتخاب کنید:"
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
    lbl = dict(_starlink_locations()).get(sid, "لوکیشن")
    text = "<b>" + lbl + "</b>\n━━━━━━━━━━━━━━\n\nمدت اشتراک را انتخاب کنید:"
    await send_screen(cb, state, text, reply_markup=_dur_kb(sid, show_back=True), banner_key="starlink")
    await cb.answer()


@router.callback_query(F.data.startswith("sl_dur:"))
async def sl_dur_handler(cb: CallbackQuery, state: FSMContext):
    parts = cb.data.split(":")
    sid, days = int(parts[1]), int(parts[2])
    lbl = dict(_starlink_locations()).get(sid, "لوکیشن")
    text = ("<b>" + lbl + "</b>\n"
            "مدت: " + _dur_label(days) + "\n"
            "━━━━━━━━━━━━━━\n\nحجم مورد نظر را انتخاب کنید:")
    await send_screen(cb, state, text, reply_markup=_plans_kb(sid, days), banner_key="starlink")
    await cb.answer()


@router.callback_query(F.data.startswith("shop_category:"))
async def shop_category_handler(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split(":")[1]
    title = CATEGORY_TITLES.get(category)
    if not title:
        await callback.answer("دسته‌بندی نامعتبر است.", show_alert=True)
        return

    if category == "starlink":
        await show_starlink_intro(callback, state)
        return

    services = get_services_by_category(category)
    if not services:
        await send_screen(
            callback,
            state,
            f"{title}\n\nفعلاً پلنی برای این سرور فعال نیست. لطفاً کمی بعد دوباره بررسی کنید.",
            reply_markup=shop_category_keyboard(),
            banner_key=category,
        )
        return

    await send_screen(
        callback,
        state,
        f"{title}\n━━━━━━━━━━━━━━\n\nیکی از سرویس‌های فعال را انتخاب کنید. پس از ثبت سفارش، مسیر پرداخت و ارسال رسید نمایش داده می‌شود.",
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
            "✍️ <b>وارد کردن حجم دلخواه</b>\n━━━━━━━━━━━━━━\n\nلطفاً حجم موردنظر را فقط به عدد وارد کنید.\n\nمثال: <code>2</code> یعنی سفارش ۲ گیگابایت\n"
            f"محدوده مجاز سفارش: ۱ تا {STARLINK_MAX_VOLUME_GB} گیگابایت",
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
            "لطفاً فقط عدد حجم را ارسال کنید.\n"
            "مثال: <code>2</code> برای سفارش ۲ گیگابایت"
        )
        return
    await finalize_starlink_order(message, state, volume, from_callback=False)


@router.callback_query(F.data.startswith("shop_type:"))
async def shop_type_handler(callback: CallbackQuery):
    _, category, buy_type = callback.data.split(":")
    services = get_services_by_category_and_type(category=category, service_type=buy_type)
    title = CATEGORY_TITLES.get(category, "سرویس VPN")
    if not services:
        await send_screen(callback, None, f"{title}\n\nفعلاً سرویسی در این بخش ثبت نشده است.", reply_markup=shop_category_keyboard())
        return
    await send_screen(callback, None, f"{title}\n\nلطفاً سرویس مورد نظر را انتخاب کنید:", reply_markup=services_keyboard(services, category), banner_key=category)


@router.callback_query(F.data.startswith("service:"))
async def service_detail_handler(callback: CallbackQuery):
    service_id = int(callback.data.split(":")[1])
    service = get_service(service_id)
    if not service:
        await callback.answer("سرویس پیدا نشد.", show_alert=True)
        return

    label = "تک‌کاربره" if service["service_type"] == "single" else "چندکاربره / سازمانی"
    text = (
        f"✨ <b>{service['name']}</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        f"نوع سرویس: {label}\n\n"
        f"{service['description'] or 'توضیحات این سرویس به‌زودی تکمیل می‌شود.'}\n\n"
        "برای مشاهده پلن‌ها و ثبت سفارش، دکمه زیر را انتخاب کنید."
    )
    await send_screen(callback, None, text, reply_markup=service_buy_keyboard(service_id), banner_key=service["category"])


@router.callback_query(F.data.startswith("buy_service:"))
async def buy_service_handler(callback: CallbackQuery):
    service_id = int(callback.data.split(":")[1])
    plans = get_plans_by_service(service_id)
    if not plans:
        await send_screen(callback, None, "برای این سرویس هنوز پلنی ثبت نشده است.")
        return

    text = (
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
        await callback.answer("پلن پیدا نشد.", show_alert=True)
        return

    from database.sub_admin_pricing import get_price_for_user
    final_price = get_price_for_user(callback.from_user.id, plan_id)

    text = (
        "✅ پلن انتخاب شد\n"
        "━━━━━━━━━━━━━━\n\n"
        f"🔐 سرویس: {plan['service_name']}\n"
        f"💠 پلن: {plan['title']}\n"
        f"⏳ مدت اعتبار: {_dur_label(plan['duration_days'])}\n"
        f"{payment_price_block(final_price)}\n\n"
        "در صورت داشتن کد تخفیف، آن را اعمال کنید. در غیر این صورت، پرداخت را ادامه دهید."
    )
    await send_screen(callback, None, text, reply_markup=discount_decision_keyboard(plan_id), banner_key="payment")




@router.callback_query(F.data.startswith("buy_plan:"))
async def buy_plan_from_db(callback: CallbackQuery, state: FSMContext):
    """خرید پلن — ابتدا نام دلخواه کانفیگ از مشتری گرفته می‌شود."""
    plan_id = int(callback.data.split(":")[1])
    plan = _get_active_plan(plan_id)
    if not plan:
        return await callback.answer("این پلن دیگر موجود نیست.", show_alert=True)

    await state.clear()
    await state.update_data(buy_plan_id=plan_id)
    await state.set_state(BuyStates.waiting_config_name)
    await callback.message.answer(
        "🏷 <b>نام کانفیگت را انتخاب کن</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "یک نام دلخواه برای کانفیگت بفرست (فقط حروف انگلیسی، عدد، ـ یا -).\n"
        "مثلاً: <code>ali-vpn</code>\n\n"
        "اگر نمی‌خواهی نام انتخاب کنی، بنویس: <code>skip</code>"
    )
    await callback.answer()


@router.message(BuyStates.waiting_config_name)
async def buy_config_name(msg: Message, state: FSMContext):
    data = await state.get_data()
    plan_id = data.get("buy_plan_id")
    if not plan_id:
        await state.clear()
        return
    raw = (msg.text or "").strip()
    config_name = "" if raw.lower() in ("skip", "رد", "-", "بی‌خیال", "بیخیال") else _sanitize_name(raw)

    plan = _get_active_plan(plan_id)
    if not plan:
        await state.clear()
        return await msg.answer("این پلن دیگر موجود نیست.")

    order_id = _create_db_order(msg.from_user.id, plan, plan_id, config_name)
    await state.clear()

    price = plan["price_toman"]
    gb = str(plan["traffic_gb"]) + " GB" if plan.get("traffic_gb") else "نامحدود"
    dur = _dur_label(plan["duration_days"]) if plan.get("duration_days") else "بی‌انقضا"
    name_line = ("🏷 نام کانفیگ: " + config_name + "\n") if config_name else ""
    text = (
        "✅ سفارش ثبت شد\n"
        "━━━━━━━━━━━━━━\n\n"
        + name_line +
        "پلن: " + plan["title"] + "\n"
        "حجم: " + gb + "\n"
        "مدت: " + dur + "\n"
        "قیمت: " + "{:,}".format(price) + " تومان\n\n"
        "روش پرداخت را انتخاب کنید:"
    )
    await msg.answer(text, reply_markup=payment_methods_for_order_keyboard(order_id))


@router.callback_query(F.data == "shop_back:categories")
async def back_to_categories_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text = (
        "⚡ خرید کانفیگ VIP\n"
        "━━━━━━━━━━━━━━\n\n"
        "لطفاً سرویس موردنظر خود را انتخاب کنید:"
    )
    await send_screen(callback, state, text, reply_markup=shop_category_keyboard(), banner_key="shop")


@router.callback_query(F.data.startswith("shop_back:type:"))
async def back_to_shop_type_handler(callback: CallbackQuery, state: FSMContext):
    await back_to_categories_handler(callback, state)
