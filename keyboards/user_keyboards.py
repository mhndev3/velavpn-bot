from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from services.price_service import crypto_amounts


def _get(key, default):
    try:
        from database.db import get_setting
        v = get_setting(key, "")
        return v if v else default
    except Exception:
        return default


def _hidden(key):
    # دکمهٔ «اشتراک‌های من / کانفیگ‌های من» همیشه باید دیده شود
    if key == "btn_subs":
        return False
    try:
        from database.db import get_setting
        return get_setting("hide_" + key, "") == "1"
    except Exception:
        return False


# ترتیب پیش‌فرض دکمه‌های منوی اصلی (btn_buy همیشه اول و تنهاست)
DEFAULT_MENU_ORDER = [
    "btn_profile", "btn_wallet", "btn_subs", "btn_apps", "btn_support",
    "btn_faq", "btn_coop", "btn_guide", "btn_cfg_update", "btn_addcfg",
]


def get_menu_order():
    """ترتیب دکمه‌ها را از تنظیمات می‌خواند (کلید menu_order = لیست جداشده با کاما)."""
    try:
        from database.db import get_setting
        raw = get_setting("menu_order", "")
        if raw:
            saved = [k.strip() for k in raw.split(",") if k.strip()]
            # فقط کلیدهای معتبر، و افزودن هر کلید جدیدی که در تنظیمات نبوده
            order = [k for k in saved if k in DEFAULT_MENU_ORDER]
            for k in DEFAULT_MENU_ORDER:
                if k not in order:
                    order.append(k)
            return order
    except Exception:
        pass
    return list(DEFAULT_MENU_ORDER)


MAX_PER_ROW = 2  # سقف دکمه در هر ردیف (محدودیت عرض تلگرام)


def get_menu_layout():
    """
    چیدمان ردیف‌محور دکمه‌ها را برمی‌گرداند: لیستی از ردیف‌ها که هر ردیف
    لیستی از کلیدهاست. مثال: [["btn_profile","btn_wallet"], ["btn_subs"]]

    منبع: کلید تنظیمات menu_layout با قالب  row1a,row1b|row2a|row3a,row3b
    اگر ثبت نشده باشد، از ترتیب قدیمی (menu_order) به‌صورت دوتایی ساخته می‌شود
    تا با نصب‌های قبلی سازگار بماند.
    """
    valid = set(DEFAULT_MENU_ORDER)
    try:
        from database.db import get_setting
        raw = get_setting("menu_layout", "")
    except Exception:
        raw = ""

    if raw:
        rows = []
        seen = set()
        for part in raw.split("|"):
            row = [k.strip() for k in part.split(",") if k.strip() in valid and k.strip() not in seen]
            for k in row:
                seen.add(k)
            if row:
                rows.append(row[:MAX_PER_ROW])
        # هر کلید معتبری که در layout نبود، ته لیست به‌صورت تک‌ردیف اضافه شود
        for k in DEFAULT_MENU_ORDER:
            if k not in seen:
                rows.append([k])
        if rows:
            return rows

    # fallback: از ترتیب تخت، دوتا-دوتا
    flat = get_menu_order()
    return [flat[i:i + 2] for i in range(0, len(flat), 2)]


def save_menu_layout(rows):
    """چیدمان ردیف‌محور را ذخیره می‌کند."""
    try:
        from database.db import set_setting
        parts = [",".join(r) for r in rows if r]
        set_setting("menu_layout", "|".join(parts))
    except Exception:
        pass


# رنگ‌های مجاز تلگرام برای دکمه (Bot API 9.4+): primary=آبی، success=سبز، danger=قرمز
_VALID_COLORS = ("primary", "success", "danger")


def _color(key):
    try:
        from database.db import get_setting
        c = get_setting("btncolor_" + key, "")
        return c if c in _VALID_COLORS else None
    except Exception:
        return None


def _kb(key, default):
    """KeyboardButton با متن و رنگِ دلخواهِ تنظیم‌شده (بدون نیاز به ری‌استارت)."""
    text = _get(key, default)
    style = _color(key)
    if style:
        return KeyboardButton(text=text, style=style)
    return KeyboardButton(text=text)


def main_menu_keyboard_for(telegram_id: int):
    """
    منوی اصلی پویا:
    - دکمه پنل مدیریت فقط هد ادمین
    - دکمه آمار فروش فقط ساب‌ادمین
    - دعوت دوستان برای همه یوزرها (نه ادمین/ساب‌ادمین)
    - متن دکمه‌ها از تنظیمات هد ادمین
    """
    try:
        from config.settings import ADMIN_IDS
        from database.db import get_sub_admin
        is_head_admin = telegram_id in ADMIN_IDS
        is_sub_admin = (not is_head_admin) and bool(get_sub_admin(telegram_id))
    except Exception:
        is_head_admin = False
        is_sub_admin = False

    # عنوان‌های پیش‌فرض دکمه‌ها
    LABELS = {
        "btn_buy": "⚡ خرید کانفیگ", "btn_profile": "👤 پنل کاربری",
        "btn_wallet": "💳 کیف پول", "btn_subs": "📦 اشتراک‌های من",
        "btn_apps": "📲 دریافت برنامه‌ها",
        "btn_support": "🛟 پشتیبانی", "btn_faq": "❓ سوالات متداول",
        "btn_coop": "🤝 درخواست همکاری", "btn_guide": "📘 راهنمای اتصال",
        "btn_cfg_update": "🔄 دریافت کانفیگ آپدیت‌شده", "btn_addcfg": "➕ افزودن کانفیگ من",
    }

    keyboard = []

    # دکمه خرید همیشه اول و تنهاست
    if not _hidden("btn_buy"):
        keyboard.append([_kb("btn_buy", LABELS["btn_buy"])])

    # بقیه بر اساس چیدمان ردیف‌محور دلخواه ادمین
    for row_keys in get_menu_layout():
        row = [_kb(k, LABELS[k]) for k in row_keys if not _hidden(k)]
        if row:
            keyboard.append(row)

    # ردیف آخر: بر اساس نقش کاربر
    if is_head_admin:
        # هد ادمین: پنل مدیریت (دعوت دوستان ندارد)
        if not _hidden("btn_admin"):
            keyboard.append([_kb("btn_admin", "👑 پنل مدیریت")])
    elif is_sub_admin:
        # ساب‌ادمین: آمار فروش (دعوت دوستان ندارد)
        keyboard.append([_kb("btn_sa_stats", "📊 آمار فروش من")])
    else:
        # یوزر عادی: دعوت دوستان
        if not _hidden("btn_referral"):
            keyboard.append([_kb("btn_referral", "🎁 دعوت دوستان")])

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def is_glass_mode() -> bool:
    """آیا حالت دکمه‌های شیشه‌ای روشن است؟"""
    try:
        from database.db import get_setting
        return get_setting("ui_glass_mode", "") == "1"
    except Exception:
        return False


def glass_launcher_kb():
    """دکمهٔ ثابت پایین صفحه برای باز کردن منوی شیشه‌ای."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📋 منو")]],
        resize_keyboard=True,
    )


def main_menu_inline_for(telegram_id: int):
    """
    نسخهٔ شیشه‌ای (inline) منوی اصلی برای یوزر و ساب‌ادمین.
    هد‌ادمین شامل نمی‌شود (پنل مدیریت شیشه‌ای نمی‌شود).
    """
    try:
        from database.db import get_sub_admin
        is_sub_admin = bool(get_sub_admin(telegram_id))
    except Exception:
        is_sub_admin = False

    CALLBACKS = {
        "btn_buy": "menu:buy", "btn_profile": "menu:profile", "btn_wallet": "menu:wallet",
        "btn_subs": "menu:subs", "btn_apps": "menu:apps", "btn_support": "menu:support",
        "btn_faq": "menu:faq", "btn_coop": "menu:coop", "btn_guide": "menu:guide",
        "btn_cfg_update": "menu:cfg_update", "btn_addcfg": "menu:addcfg",
    }
    LABELS = {
        "btn_buy": "⚡ خرید کانفیگ", "btn_profile": "👤 پنل کاربری",
        "btn_wallet": "💳 کیف پول", "btn_subs": "📦 اشتراک‌های من",
        "btn_apps": "📲 دریافت برنامه‌ها",
        "btn_support": "🛟 پشتیبانی", "btn_faq": "❓ سوالات متداول",
        "btn_coop": "🤝 درخواست همکاری", "btn_guide": "📘 راهنمای اتصال",
        "btn_cfg_update": "🔄 دریافت کانفیگ آپدیت‌شده", "btn_addcfg": "➕ افزودن کانفیگ من",
    }

    rows = []
    if not _hidden("btn_buy"):
        rows.append([InlineKeyboardButton(text=_get("btn_buy", LABELS["btn_buy"]), callback_data="menu:buy")])

    for row_keys in get_menu_layout():
        row = [
            InlineKeyboardButton(text=_get(k, LABELS[k]), callback_data=CALLBACKS[k])
            for k in row_keys if not _hidden(k)
        ]
        if row:
            rows.append(row)

    if is_sub_admin:
        rows.append([InlineKeyboardButton(text=_get("btn_sa_stats", "📊 آمار فروش من"), callback_data="menu:sa_stats")])
    else:
        if not _hidden("btn_referral"):
            rows.append([InlineKeyboardButton(text=_get("btn_referral", "🎁 دعوت دوستان"), callback_data="menu:referral")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def main_menu_keyboard():
    """منوی ساده fallback"""
    keyboard = [
        [KeyboardButton(text="⚡ خرید کانفیگ")],
        [KeyboardButton(text="💳 کیف پول"), KeyboardButton(text="📦 اشتراک‌های من")],
        [KeyboardButton(text="🛟 پشتیبانی"), KeyboardButton(text="❓ سوالات متداول")],
        [KeyboardButton(text="🤝 درخواست همکاری"), KeyboardButton(text="🎁 دعوت دوستان")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def profile_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ خرید کانفیگ جدید", callback_data="shop_back:categories")],
    ])


def to_fa_number(value: int) -> str:
    return str(value)


def faq_questions_keyboard(faq_items: list):
    keyboard = []
    for item in faq_items:
        keyboard.append([InlineKeyboardButton(
            text=item["question"][:50], callback_data="faq:answer:" + str(item["id"])
        )])
    return InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None


def cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ لغو عملیات")]],
        resize_keyboard=True, one_time_keyboard=True
    )


def discount_decision_keyboard(plan_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎟 دارم کد تخفیف", callback_data="user_discount:have:" + str(plan_id))],
        [InlineKeyboardButton(text="⏭️ ادامه بدون کد", callback_data="user_discount:none:" + str(plan_id))],
        [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="shop_back:categories")],
    ])


def services_keyboard(services: list, category: str):
    keyboard = []
    for service in services:
        keyboard.append([InlineKeyboardButton(
            text="🔘 " + service["name"],
            callback_data="service:" + str(service["id"])
        )])
    keyboard.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="shop_back:categories")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def service_buy_keyboard(service_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 مشاهده پلن‌ها", callback_data="buy_service:" + str(service_id))],
        [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="shop_back:categories")],
    ])


def plans_keyboard(plans: list, service_id: int, telegram_id: int = None):
    keyboard = []
    for plan in plans:
        price = plan["price_toman"]
        if telegram_id:
            try:
                from database.sub_admin_pricing import get_price_for_user
                price = get_price_for_user(telegram_id, plan["id"])
            except Exception:
                pass
        keyboard.append([InlineKeyboardButton(
            text=plan["title"] + " — " + "{:,}".format(price) + " تومان",
            callback_data="select_plan:" + str(plan["id"])
        )])
    keyboard.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="shop_back:categories")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def payment_methods_keyboard(plan_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 پرداخت کارت‌به‌کارت",
                              callback_data="payment_currency:" + str(plan_id) + ":toman")],
        [InlineKeyboardButton(text="💰 پرداخت از کیف‌پول",
                              callback_data="payment_currency:" + str(plan_id) + ":wallet")],
    ])


def payment_methods_keyboard_with_discount(plan_id: int, discount_code: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 پرداخت کارت‌به‌کارت",
                              callback_data="payment_currency_discount:" + str(plan_id) + ":toman:" + discount_code)],
        [InlineKeyboardButton(text="💰 پرداخت از کیف‌پول",
                              callback_data="payment_currency_discount:" + str(plan_id) + ":wallet:" + discount_code)],
    ])


def payment_methods_for_order_keyboard(order_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 کارت‌به‌کارت",
                              callback_data="payment_method:" + str(order_id) + ":card")],
        [InlineKeyboardButton(text="💰 پرداخت از کیف‌پول",
                              callback_data="payment_method:" + str(order_id) + ":wallet")],
    ])


def toman_payment_keyboard(order_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 کارت‌به‌کارت",
                              callback_data="payment_method:" + str(order_id) + ":card")],
        [InlineKeyboardButton(text="💰 پرداخت از کیف‌پول",
                              callback_data="payment_method:" + str(order_id) + ":wallet")],
    ])


def starlink_volume_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="10 گیگابایت", callback_data="starlink_volume:10"),
         InlineKeyboardButton(text="20 گیگابایت", callback_data="starlink_volume:20")],
        [InlineKeyboardButton(text="30 گیگابایت", callback_data="starlink_volume:30"),
         InlineKeyboardButton(text="40 گیگابایت", callback_data="starlink_volume:40")],
        [InlineKeyboardButton(text="50 گیگابایت", callback_data="starlink_volume:50"),
         InlineKeyboardButton(text="60 گیگابایت", callback_data="starlink_volume:60")],
        [InlineKeyboardButton(text="70 گیگابایت", callback_data="starlink_volume:70"),
         InlineKeyboardButton(text="80 گیگابایت", callback_data="starlink_volume:80")],
        [InlineKeyboardButton(text="90 گیگابایت", callback_data="starlink_volume:90"),
         InlineKeyboardButton(text="100 گیگابایت", callback_data="starlink_volume:100")],
        [InlineKeyboardButton(text="✍️ حجم دلخواه", callback_data="starlink_volume:custom")],
    ])


def shop_category_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="استارلینک اختصاصی", callback_data="shop_category:starlink")],
    ])


def discount_code_keyboard(order_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ کد تخفیف دارم",
                              callback_data="discount:apply:" + str(order_id)),
         InlineKeyboardButton(text="⏭️ ادامه",
                              callback_data="payment_order:" + str(order_id) + ":toman")],
    ])
