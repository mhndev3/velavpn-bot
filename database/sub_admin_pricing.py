"""
سیستم تعرفه ساب‌ادمین
هد ادمین می‌تونه برای هر ساب‌ادمین قیمت متفاوت تعریف کنه
"""
from database.db import get_connection


def init_sub_admin_pricing():
    """جدول تعرفه‌ی ساب‌ادمین"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS sub_admin_pricing (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sub_admin_id INTEGER NOT NULL,
        plan_id INTEGER NOT NULL,
        override_price_toman INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(sub_admin_id, plan_id),
        FOREIGN KEY(plan_id) REFERENCES plans(id)
    );
    """)
    conn.commit()
    conn.close()


# ─── Pricing Management ──────────────────────────────────────
def set_sub_admin_price(sub_admin_id: int, plan_id: int, price_toman: int) -> bool:
    """قیمت اختصاصی برای ساب‌ادمین تعریف کن"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO sub_admin_pricing
        (sub_admin_id, plan_id, override_price_toman, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (sub_admin_id, plan_id, price_toman),
    )
    conn.commit()
    conn.close()
    return True


def get_sub_admin_price(sub_admin_id: int, plan_id: int) -> int | None:
    """قیمت اختصاصی ساب‌ادمین برای یک پلن"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT override_price_toman FROM sub_admin_pricing
        WHERE sub_admin_id = ? AND plan_id = ?
        """,
        (sub_admin_id, plan_id),
    )
    row = cursor.fetchone()
    conn.close()
    return row["override_price_toman"] if row else None


def get_price_for_user(telegram_id: int, plan_id: int) -> int:
    """قیمت نهایی برای یک کاربر (ساب‌ادمین قیمت خاص، کاربر عادی قیمت عادی)"""
    from database.db import get_sub_admin, get_plan

    plan = get_plan(plan_id)
    if not plan:
        return 0

    base_price = plan["price_toman"]
    sub_admin = get_sub_admin(telegram_id)

    if not sub_admin:
        # کاربر عادی
        return base_price

    # ساب‌ادمین — چک کن آیا قیمت اختصاصی داره
    override = get_sub_admin_price(sub_admin["id"], plan_id)
    if override is not None:
        return override

    return base_price


def get_all_sub_admin_pricing(sub_admin_id: int) -> list:
    """همه‌ی قیمت‌های اختصاصی یک ساب‌ادمین"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT sp.*, p.title, s.name AS service_name, p.price_toman AS default_price
        FROM sub_admin_pricing sp
        JOIN plans p ON p.id = sp.plan_id
        JOIN services s ON s.id = p.service_id
        WHERE sp.sub_admin_id = ?
        ORDER BY s.name, p.title
        """,
        (sub_admin_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def remove_sub_admin_price(sub_admin_id: int, plan_id: int) -> bool:
    """قیمت اختصاصی رو پاک کن (برگرد به قیمت عادی)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM sub_admin_pricing WHERE sub_admin_id = ? AND plan_id = ?",
        (sub_admin_id, plan_id),
    )
    conn.commit()
    conn.close()
    return True


def get_plan(plan_id: int):
    """دریافت پلن (از db.py)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT p.*, s.name AS service_name, s.category, s.service_type, s.server_id
        FROM plans p
        JOIN services s ON s.id = p.service_id
        WHERE p.id = ?
        """,
        (plan_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None
