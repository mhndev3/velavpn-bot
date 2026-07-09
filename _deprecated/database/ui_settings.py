"""
جدول تنظیمات UI/UX — هد ادمین نوشت‌ها، بنر‌ها، ایموجی رو مدیریت کنه
"""
from database.db import get_connection, get_setting, set_setting


def init_ui_settings():
    """ایجاد جدول تنظیمات UI"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS ui_settings (
        key TEXT PRIMARY KEY,
        label TEXT NOT NULL,
        value TEXT,
        type TEXT DEFAULT 'text',
        category TEXT DEFAULT 'general',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # تنظیمات پیش‌فرض
    defaults = [
        ('emoji_star', 'ایموجی ستاره', '⭐', 'emoji', 'emoji'),
        ('emoji_success', 'ایموجی موفقیت', '✅', 'emoji', 'emoji'),
        ('emoji_error', 'ایموجی خطا', '❌', 'emoji', 'emoji'),
        ('emoji_wallet', 'ایموجی کیف‌پول', '💳', 'emoji', 'emoji'),
        ('emoji_shop', 'ایموجی خرید', '⚡', 'emoji', 'emoji'),
        ('emoji_admin', 'ایموجی ادمین', '👑', 'emoji', 'emoji'),
        
        ('text_welcome', 'متن خوشامد', 'خوش‌آمدید!', 'text', 'text'),
        ('text_menu_title', 'عنوان منو', '📱 منوی اصلی:', 'text', 'text'),
        ('text_shop_title', 'عنوان فروشگاه', '⚡ خرید کانفیگ', 'text', 'text'),
        ('text_wallet_title', 'عنوان کیف‌پول', '💳 کیف‌پول شما', 'text', 'text'),
        
        ('banner_start', 'بنر صفحه‌ی شروع', 'به ربات خوش آمدید!', 'banner', 'banner'),
        ('banner_shop', 'بنر فروشگاه', 'بهترین سرویس‌های VPN', 'banner', 'banner'),
        ('banner_wallet', 'بنر کیف‌پول', 'سریع، ایمن، راحت', 'banner', 'banner'),
    ]
    
    for key, label, value, type_, category in defaults:
        cursor.execute(
            """
            INSERT OR IGNORE INTO ui_settings (key, label, value, type, category)
            VALUES (?, ?, ?, ?, ?)
            """,
            (key, label, value, type_, category),
        )
    
    conn.commit()
    conn.close()


# ─── UI Settings CRUD ────────────────────────────────────────
def get_ui_setting(key: str, default: str = "") -> str:
    """دریافت تنظیم UI"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM ui_settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else default


def set_ui_setting(key: str, value: str) -> bool:
    """تعریف/تغییر تنظیم UI"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE ui_settings SET value = ?, updated_at = CURRENT_TIMESTAMP
        WHERE key = ?
        """,
        (value, key),
    )
    conn.commit()
    conn.close()
    return True


def get_all_ui_settings_by_category(category: str) -> list:
    """دریافت تمام تنظیمات یک دسته‌بندی"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT key, label, value, type FROM ui_settings WHERE category = ? ORDER BY key",
        (category,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_ui_settings() -> dict:
    """دریافت تمام تنظیمات"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM ui_settings")
    rows = cursor.fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}
