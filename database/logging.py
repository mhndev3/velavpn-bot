"""
سیستم لاگ‌گیری تفصیلی
"""
from database.db import get_connection
from datetime import datetime


def init_logging_tables():
    """جداول لاگ‌گیری"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS action_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT NOT NULL,
        details TEXT,
        ip_address TEXT,
        status TEXT DEFAULT 'success',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS error_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        error_type TEXT NOT NULL,
        error_message TEXT,
        traceback TEXT,
        user_id INTEGER,
        context TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS server_monitoring (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        server_id INTEGER NOT NULL,
        is_online INTEGER DEFAULT 1,
        response_time_ms INTEGER,
        last_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        consecutive_failures INTEGER DEFAULT 0
    );
    """)
    conn.commit()
    conn.close()


# ─── Action Logging ─────────────────────────────────────────
def log_action(user_id: int, action: str, details: str = "", ip_address: str = "", status: str = "success"):
    """ثبت عملیات"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO action_logs (user_id, action, details, ip_address, status)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, action, details, ip_address, status),
    )
    conn.commit()
    conn.close()


def log_error(error_type: str, error_message: str, traceback_text: str = "", user_id: int = None, context: str = ""):
    """ثبت خطا"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO error_logs (error_type, error_message, traceback, user_id, context)
        VALUES (?, ?, ?, ?, ?)
        """,
        (error_type, error_message, traceback_text, user_id, context),
    )
    conn.commit()
    conn.close()


def get_recent_logs(limit: int = 100) -> list:
    """آخرین لاگ‌ها"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM action_logs ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_errors(limit: int = 50) -> list:
    """آخرین خطاها"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM error_logs ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Server Monitoring ──────────────────────────────────────
def update_server_status(server_id: int, is_online: int, response_time_ms: int = 0):
    """به‌روز رسانی وضعیت سرور"""
    conn = get_connection()
    cursor = conn.cursor()
    
    if is_online:
        consecutive_failures = 0
    else:
        # اگر آفلاین، شمارنده‌ی ناموفق را افزایش بده
        cursor.execute(
            "SELECT consecutive_failures FROM server_monitoring WHERE server_id = ? ORDER BY id DESC LIMIT 1",
            (server_id,),
        )
        row = cursor.fetchone()
        consecutive_failures = (row["consecutive_failures"] if row else 0) + 1
    
    cursor.execute(
        """
        INSERT INTO server_monitoring (server_id, is_online, response_time_ms, consecutive_failures)
        VALUES (?, ?, ?, ?)
        """,
        (server_id, is_online, response_time_ms, consecutive_failures),
    )
    conn.commit()
    conn.close()
    
    # اگر 3 بار مرتب‌ناموفق، ادمین رو خبر بده
    if consecutive_failures >= 3:
        log_action(
            user_id=None,
            action="server_down_alert",
            details=f"سرور {server_id} قطع شد ({consecutive_failures} بار)",
            status="alert",
        )


def get_server_status(server_id: int) -> dict | None:
    """وضعیت فعلی سرور"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM server_monitoring
        WHERE server_id = ?
        ORDER BY id DESC LIMIT 1
        """,
        (server_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None
