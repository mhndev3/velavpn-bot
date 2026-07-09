import os
from dotenv import load_dotenv


load_dotenv()


def env_text(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    if value is None:
        return default
    return value.replace("\\n", "\n").strip()


def env_int(name: str, default: int = 0) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except Exception:
        return default


def env_float(name: str, default: float = 0.0) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        return float(raw)
    except Exception:
        return default


BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

_ADMIN_IDS_STATIC = [
    int(admin_id.strip())
    for admin_id in os.getenv("ADMIN_IDS", "").split(",")
    if admin_id.strip().isdigit()
]


class _AdminIDs:
    """
    لیست هوشمند هد‌ادمین‌ها: `x in ADMIN_IDS` هم لیست ثابت (.env) و هم جدول
    head_admins دیتابیس را چک می‌کند. این‌طوری همهٔ گیت‌های موجود بدون تغییر،
    هد‌ادمین‌هایی که از داخل بات اضافه شده‌اند را هم می‌پذیرند.
    تکرار (iterate) و اندیس فقط روی لیست ثابت است (برای نوتیفیکیشن‌ها).
    """
    def __init__(self, static_ids):
        self._static = list(static_ids)

    def __contains__(self, uid):
        try:
            uid = int(uid)
        except Exception:
            return False
        if uid in self._static:
            return True
        try:
            from database.db import is_head_admin_db
            return is_head_admin_db(uid)
        except Exception:
            return False

    def __iter__(self):
        return iter(self._static)

    def __len__(self):
        return len(self._static)

    def __getitem__(self, i):
        return self._static[i]

    def __bool__(self):
        return bool(self._static)


ADMIN_IDS = _AdminIDs(_ADMIN_IDS_STATIC)

# آیدی عددی دولوپر (فقط این شخص به پنل Death Note دسترسی دارد).
# در .env مقدار DEVELOPER_ID را بگذار؛ اگر خالی باشد Death Note غیرفعال است.
DEVELOPER_ID = env_int("DEVELOPER_ID", 0)

ADMIN_REPORT_CHANNEL_ID_RAW = os.getenv("ADMIN_REPORT_CHANNEL_ID", "").strip()
ADMIN_REPORT_CHANNEL_ID = (
    int(ADMIN_REPORT_CHANNEL_ID_RAW)
    if ADMIN_REPORT_CHANNEL_ID_RAW.lstrip("-").isdigit()
    else (ADMIN_IDS[0] if ADMIN_IDS else None)
)

STARLINK_ADMIN_REPORT_CHANNEL_ID_RAW = os.getenv("STARLINK_ADMIN_REPORT_CHANNEL_ID", "").strip()
STARLINK_ADMIN_REPORT_CHANNEL_ID = (
    int(STARLINK_ADMIN_REPORT_CHANNEL_ID_RAW)
    if STARLINK_ADMIN_REPORT_CHANNEL_ID_RAW.lstrip("-").isdigit()
    else (ADMIN_IDS[0] if ADMIN_IDS else None)
)

STARLINK_PRICE_PER_GB = env_int("STARLINK_PRICE_PER_GB", 500000)
USDT_TOMAN_RATE = env_float("USDT_TOMAN_RATE", 92000)
TRX_TOMAN_RATE = env_float("TRX_TOMAN_RATE", 7500)

ADMIN_PAYMENT_USERNAME = os.getenv("ADMIN_PAYMENT_USERNAME", "@WGVA_021").strip()
if ADMIN_PAYMENT_USERNAME and not ADMIN_PAYMENT_USERNAME.startswith("@"): 
    ADMIN_PAYMENT_USERNAME = "@" + ADMIN_PAYMENT_USERNAME

STARLINK_MAX_VOLUME_GB = env_int("STARLINK_MAX_VOLUME_GB", 1000)

STARLINK_CARD_PAYMENT_TEXT = env_text(
    "STARLINK_CARD_PAYMENT_TEXT",
    (
        "💳 پرداخت کارت‌به‌کارت با هماهنگی ادمین\n\n"
        "برای پرداخت کارت‌به‌کارت این سرویس، لطفاً به ادمین پرداخت پیام دهید و شماره سفارش را ارسال کنید.\n\n"
        f"ادمین پرداخت: {ADMIN_PAYMENT_USERNAME}\n\n"
        "پس از تایید پرداخت، کانفیگ اختصاصی شما ارسال می‌شود."
    )
)



USE_PROXY = os.getenv("USE_PROXY", "False").lower() == "true"
PROXY_TYPE = os.getenv("PROXY_TYPE", "socks5").strip()
PROXY_HOST = os.getenv("PROXY_HOST", "127.0.0.1").strip()
PROXY_PORT = env_int("PROXY_PORT", 10808)
PROXY_USERNAME = os.getenv("PROXY_USERNAME", "").strip()
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD", "").strip()


CARD_PAYMENT_TEXT = env_text(
    "CARD_PAYMENT_TEXT",
    (
        "💳 پرداخت کارت‌به‌کارت با هماهنگی ادمین\n\n"
        "برای پرداخت کارت‌به‌کارت، لطفاً به ادمین پیام دهید و شماره سفارش خود را ارسال کنید.\n\n"
        f"ادمین پرداخت: {ADMIN_PAYMENT_USERNAME}\n\n"
        "پس از تایید پرداخت، کانفیگ اختصاصی شما ارسال می‌شود."
    )
)

CRYPTO_PAYMENT_TEXT = env_text(
    "CRYPTO_PAYMENT_TEXT",
    (
        "🪙 پرداخت ارزی USDT / TRX\n\n"
        "USDT TRC20:\n"
        "YOUR_USDT_TRC20_ADDRESS\n\n"
        "TRX TRC20:\n"
        "YOUR_TRX_TRC20_ADDRESS\n\n"
        "پس از پرداخت، TXID و در صورت امکان تصویر رسید را همینجا ارسال کنید."
    )
)


print("========== BOT SETTINGS ==========")
print(f"BOT_TOKEN Loaded: {'YES' if BOT_TOKEN else 'NO'}")
print(f"Proxy Enabled: {USE_PROXY}")
print(f"ADMIN_REPORT_CHANNEL_ID: {ADMIN_REPORT_CHANNEL_ID}")
print(f"STARLINK_ADMIN_REPORT_CHANNEL_ID: {STARLINK_ADMIN_REPORT_CHANNEL_ID}")
print(f"STARLINK_PRICE_PER_GB: {STARLINK_PRICE_PER_GB}")
print(f"USDT_TOMAN_RATE: {USDT_TOMAN_RATE}")
print(f"TRX_TOMAN_RATE: {TRX_TOMAN_RATE}")
print("==================================")
