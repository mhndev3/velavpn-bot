"""
سیستم بنرها و متن‌های داینامیک — هد ادمین کنترل می‌کنه
"""
from database.db import get_connection, get_setting, set_setting


def init_ui_tables():
    """جداول UI"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS ui_banners (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        emoji TEXT DEFAULT '📌',
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS ui_texts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT UNIQUE NOT NULL,
        label TEXT NOT NULL,
        value TEXT NOT NULL,
        emoji TEXT DEFAULT '📝',
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS ui_themes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        primary_color TEXT DEFAULT '🟢',
        secondary_color TEXT DEFAULT '🟠',
        success_emoji TEXT DEFAULT '✅',
        error_emoji TEXT DEFAULT '❌',
        warning_emoji TEXT DEFAULT '⚠️',
        info_emoji TEXT DEFAULT 'ℹ️',
        is_active INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()


# ─── Banners ──────────────────────────────────────────────────
def create_banner(name: str, title: str, description: str = "", emoji: str = "📌") -> int:
    """بنر جدید"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO ui_banners (name, title, description, emoji)
        VALUES (?, ?, ?, ?)
        """,
        (name, title, description, emoji),
    )
    banner_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return banner_id


def get_banner(name: str) -> dict | None:
    """دریافت بنر"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ui_banners WHERE name = ? AND is_active = 1", (name,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_banners() -> list:
    """تمام بنرها"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ui_banners ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_banner(name: str, **kwargs):
    """آپدیت بنر"""
    allowed = {"title", "description", "emoji", "is_active"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE ui_banners SET {set_clause} WHERE name = ?", (*fields.values(), name))
    conn.commit()
    conn.close()


# ─── UI Texts ─────────────────────────────────────────────────
def set_ui_text(key: str, label: str, value: str, emoji: str = "📝", description: str = "") -> bool:
    """تنظیم متن UI"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO ui_texts (key, label, value, emoji, description)
        VALUES (?, ?, ?, ?, ?)
        """,
        (key, label, value, emoji, description),
    )
    conn.commit()
    conn.close()
    return True


def get_ui_text(key: str, default: str = "") -> str:
    """دریافت متن UI"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM ui_texts WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else default


def get_all_ui_texts() -> list:
    """تمام متن‌های UI"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ui_texts ORDER BY key")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Themes ───────────────────────────────────────────────────
def create_theme(name: str, colors: dict) -> int:
    """تم جدید"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO ui_themes (name, primary_color, secondary_color, 
                               success_emoji, error_emoji, warning_emoji, info_emoji)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            colors.get("primary", "🟢"),
            colors.get("secondary", "🟠"),
            colors.get("success", "✅"),
            colors.get("error", "❌"),
            colors.get("warning", "⚠️"),
            colors.get("info", "ℹ️"),
        ),
    )
    theme_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return theme_id


def get_active_theme() -> dict | None:
    """دریافت تم فعال"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ui_themes WHERE is_active = 1 LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_themes() -> list:
    """تمام تم‌ها"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ui_themes ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def set_active_theme(theme_id: int) -> bool:
    """تنظیم تم فعال"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE ui_themes SET is_active = 0")
    cursor.execute("UPDATE ui_themes SET is_active = 1 WHERE id = ?", (theme_id,))
    conn.commit()
    conn.close()
    return True
