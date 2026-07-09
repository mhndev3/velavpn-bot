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
    """آمار روزانه (آخر N روز)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM daily_analytics
        ORDER BY date DESC LIMIT ?
        """,
        (days,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_revenue_chart_data(days: int = 30) -> dict:
    """داده‌های نمودار درآمد"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT date, total_revenue_toman FROM daily_analytics
        ORDER BY date DESC LIMIT ?
        """,
        (days,),
    )
    rows = cursor.fetchall()
    conn.close()
    
    data = {}
    for row in reversed(rows):
        data[row["date"]] = row["total_revenue_toman"]
    
    return data


def get_report_data(start_date: str, end_date: str) -> dict:
    """گزارش درآمد بین تاریخ‌ها"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        """
        SELECT 
            SUM(total_orders) as total_orders,
            SUM(total_revenue_toman) as total_revenue,
            AVG(total_revenue_toman) as avg_daily_revenue,
            MAX(total_revenue_toman) as max_daily_revenue,
            MIN(total_revenue_toman) as min_daily_revenue
        FROM daily_analytics
        WHERE date BETWEEN ? AND ?
        """,
        (start_date, end_date),
    )
    row = cursor.fetchone()
    conn.close()
    
    return {
        "total_orders": row["total_orders"] or 0,
        "total_revenue": row["total_revenue"] or 0,
        "avg_daily_revenue": int(row["avg_daily_revenue"] or 0),
        "max_daily_revenue": row["max_daily_revenue"] or 0,
        "min_daily_revenue": row["min_daily_revenue"] or 0,
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
