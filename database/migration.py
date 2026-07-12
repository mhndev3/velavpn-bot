"""
migration.py — اضافه کردن ستون‌های جدید به جداول موجود
"""
from database.db import get_connection


def run_migrations():
    conn = get_connection()
    cursor = conn.cursor()

    migrations = [
        # plans: server_id و inbound_id
        "ALTER TABLE plans ADD COLUMN server_id INTEGER DEFAULT NULL",
        "ALTER TABLE plans ADD COLUMN inbound_id INTEGER DEFAULT 0",
        # xui_accounts: sub_id برای دریافت کانفیگ آپدیت‌شده
        "ALTER TABLE xui_accounts ADD COLUMN sub_id TEXT DEFAULT ''",
        # orders: نام دلخواه کانفیگ که مشتری موقع خرید انتخاب می‌کند
        "ALTER TABLE orders ADD COLUMN config_name TEXT DEFAULT ''",
        # orders: تعداد اکانت خریداری‌شده در یک سفارش
        "ALTER TABLE orders ADD COLUMN quantity INTEGER DEFAULT 1",
        # orders: تمدید — ایمیل و سرورِ اکانتی که این سفارش شارژش می‌کند
        "ALTER TABLE orders ADD COLUMN renew_email TEXT DEFAULT ''",
        "ALTER TABLE orders ADD COLUMN renew_server_id INTEGER DEFAULT 0",
        # xui_servers: دامنهٔ دستی برای ساخت لینک کانفیگ (مستقل از پنل)
        "ALTER TABLE xui_servers ADD COLUMN domain TEXT DEFAULT ''",
        # onboarding: شماره تلفن، نام کاربری دلخواه، پذیرش قوانین، تکمیل ثبت‌نام
        "ALTER TABLE users ADD COLUMN phone TEXT DEFAULT ''",
        "ALTER TABLE users ADD COLUMN custom_username TEXT DEFAULT ''",
        "ALTER TABLE users ADD COLUMN rules_accepted INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN onboarding_done INTEGER DEFAULT 0",
        # کانال‌های عضویت اجباری (قابل مدیریت توسط ادمین)
        """CREATE TABLE IF NOT EXISTS required_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            title TEXT,
            url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
    ]

    for sql in migrations:
        try:
            cursor.execute(sql)
        except Exception:
            pass  # ستون از قبل وجود داره

    conn.commit()
    conn.close()

    _seed_welcome_placeholders()


def _seed_welcome_placeholders():
    """
    متن پیام خوش‌آمد را در صورت نداشتن placeholder، به نسخهٔ جدید (با آیدی و
    تاریخ شمسی) ارتقا می‌دهد. Idempotent: اگر ادمین خودش متن را شخصی‌سازی کرده
    باشد (placeholder داشته باشد) دست نمی‌خورد.
    """
    new_text = (
        "سلام {name} 👋\n"
        "🆔 آیدی شما: {id}\n"
        "📅 تاریخ: {datetime}\n\n"
        "به ربات فروش وی‌پی‌ان خوش اومدی 🚀\n"
        "اینجا میتونی به راحتی کانفیگ مورد نظرت رو تهیه کنی و آنلاین استفاده کنی 🔥\n"
        "از منوی زیر گزینه مورد نظرت رو انتخاب کن 👇"
    )
    try:
        from database.db import get_setting, set_setting
        from services.content_media_service import get_content_page, update_content_page
        page = get_content_page("start_message") or {}
        cur = (page.get("content") or "") if page else ""
        # اگر placeholder ندارد (نسخهٔ قدیمی یا خالی)، ارتقا بده
        if "{id}" not in cur and "{datetime}" not in cur and "{name}" not in cur:
            update_content_page(
                "start_message",
                (page.get("title") if page else None) or "پیام خوش‌آمد",
                new_text,
                page.get("file_id") if page else None,
                page.get("file_type") if page else None,
            )
            set_setting("txt_welcome", new_text)
    except Exception:
        pass
