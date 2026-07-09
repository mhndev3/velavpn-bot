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
