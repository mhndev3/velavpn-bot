"""
سیستم آنالیتیکس — آمار و نمودار درآمد
"""
from datetime import datetime, timedelta
from database.db import get_connection


def init_analytics_tables():
    """جداول آنالیتیکس"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS daily_analytics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL UNIQUE,
        total_orders INTEGER DEFAULT 0,
        total_revenue_toman INTEGER DEFAULT 0,
        total_users INTEGER DEFAULT 0,
        new_users INTEGER DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS order_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        telegram_id INTEGER NOT NULL,
        amount_toman INTEGER NOT NULL,
        service_name TEXT,
        status TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()


# ─── Analytics ──────────────────────────────────────────────
def log_order(order_id: int, telegram_id: int, amount_toman: int, service_name: str, status: str = "pending"):
    """ثبت سفارش در لاگ‌های آنالیتیکس"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO order_logs (order_id, telegram_id, amount_toman, service_name, status)
        VALUES (?, ?, ?, ?, ?)
        """,
        (order_id, telegram_id, amount_toman, service_name, status),
    )
    conn.commit()
    conn.close()


def update_daily_analytics():
    """به‌روز رسانی آمار روزانه‌ی امروز"""
    from database.db import get_count
    from database.wallet import get_wallet_charges
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # تعداد سفارش‌های امروز
    total_orders = get_count("orders", f"DATE(created_at) = '{today}'")
    
    # درآمد امروز
    cursor.execute(
        f"SELECT COALESCE(SUM(final_price_toman), 0) as revenue FROM orders WHERE DATE(created_at) = '{today}' AND status = 'approved'"
    )
    total_revenue = cursor.fetchone()["revenue"]
    
    # کل کاربران
    total_users = get_count("users")
    
    # کاربران جدید امروز
    new_users = get_count("users", f"DATE(created_at) = '{today}'")
    
    cursor.execute(
        """
        INSERT INTO daily_analytics (date, total_orders, total_revenue_toman, total_users, new_users)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            total_orders = excluded.total_orders,
            total_revenue_toman = excluded.total_revenue_toman,
            total_users = excluded.total_users,
            new_users = excluded.new_users,
            updated_at = CURRENT_TIMESTAMP
        """,
        (today, total_orders, total_revenue, total_users, new_users),
    )
    conn.commit()
    conn.close()


def get_daily_analytics(days: int = 7) -> list:
    """
    آمار روزانه (آخر N روز) — مستقیم از جدول‌های زنده محاسبه می‌شود.

    قبلاً از جدول کشِ daily_analytics خوانده می‌شد که چون update_daily_analytics
    هیچ‌جا صدا زده نمی‌شد همیشه خالی بود و همهٔ گزارش‌ها صفر نشان می‌دادند.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT DATE(created_at) AS date,
               COUNT(*) AS total_orders,
               COALESCE(SUM(CASE WHEN status = 'approved'
                    THEN COALESCE(final_price_toman, price_toman, 0) ELSE 0 END), 0)
                    AS total_revenue_toman
        FROM orders
        WHERE created_at IS NOT NULL AND created_at != ''
        GROUP BY DATE(created_at)
        ORDER BY date DESC
        LIMIT ?
        """,
        (days,),
    )
    rows = [dict(r) for r in cursor.fetchall()]

    # کاربران جدید هر روز
    cursor.execute(
        """
        SELECT DATE(created_at) AS date, COUNT(*) AS new_users
        FROM users
        WHERE created_at IS NOT NULL AND created_at != ''
        GROUP BY DATE(created_at)
        """
    )
    new_by_date = {r["date"]: r["new_users"] for r in cursor.fetchall()}

    cursor.execute("SELECT COUNT(*) AS c FROM users")
    total_users = cursor.fetchone()["c"]
    conn.close()

    for r in rows:
        r["new_users"] = new_by_date.get(r["date"], 0)
        r["total_users"] = total_users
    return rows


def get_revenue_chart_data(days: int = 30) -> dict:
    """داده‌های نمودار درآمد — زنده از جدول سفارش‌ها."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT DATE(created_at) AS date,
               COALESCE(SUM(COALESCE(final_price_toman, price_toman, 0)), 0) AS revenue
        FROM orders
        WHERE status = 'approved' AND created_at IS NOT NULL AND created_at != ''
        GROUP BY DATE(created_at)
        ORDER BY date DESC
        LIMIT ?
        """,
        (days,),
    )
    rows = cursor.fetchall()
    conn.close()

    data = {}
    for row in reversed(rows):
        data[row["date"]] = row["revenue"]
    return data


def get_report_data(start_date: str, end_date: str) -> dict:
    """گزارش درآمد بین دو تاریخ — زنده از جدول سفارش‌ها."""
    conn = get_connection()
    cursor = conn.cursor()

    # جمع کل در بازه
    cursor.execute(
        """
        SELECT COUNT(*) AS total_orders,
               COALESCE(SUM(CASE WHEN status = 'approved'
                    THEN COALESCE(final_price_toman, price_toman, 0) ELSE 0 END), 0)
                    AS total_revenue,
               COALESCE(SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END), 0)
                    AS approved_orders
        FROM orders
        WHERE DATE(created_at) BETWEEN ? AND ?
        """,
        (start_date, end_date),
    )
    tot = cursor.fetchone()

    # درآمد روزانه برای میانگین/بیشینه/کمینه
    cursor.execute(
        """
        SELECT DATE(created_at) AS d,
               COALESCE(SUM(COALESCE(final_price_toman, price_toman, 0)), 0) AS rev
        FROM orders
        WHERE status = 'approved' AND DATE(created_at) BETWEEN ? AND ?
        GROUP BY DATE(created_at)
        """,
        (start_date, end_date),
    )
    daily = [r["rev"] for r in cursor.fetchall()]

    # کاربران جدید در بازه
    cursor.execute(
        "SELECT COUNT(*) AS c FROM users WHERE DATE(created_at) BETWEEN ? AND ?",
        (start_date, end_date),
    )
    new_users = cursor.fetchone()["c"]
    conn.close()

    return {
        "total_orders": tot["total_orders"] or 0,
        "approved_orders": tot["approved_orders"] or 0,
        "total_revenue": tot["total_revenue"] or 0,
        "new_users": new_users or 0,
        "avg_daily_revenue": int(sum(daily) / len(daily)) if daily else 0,
        "max_daily_revenue": max(daily) if daily else 0,
        "min_daily_revenue": min(daily) if daily else 0,
    }


def get_weekly_report() -> dict:
    """گزارش هفتگی"""
    today = datetime.now()
    week_start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    week_end = today.strftime("%Y-%m-%d")
    return get_report_data(week_start, week_end)


def get_monthly_report() -> dict:
    """گزارش ماهانه"""
    today = datetime.now()
    month_start = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    month_end = today.strftime("%Y-%m-%d")
    return get_report_data(month_start, month_end)
