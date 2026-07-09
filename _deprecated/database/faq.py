"""
FAQ — سوالات متداول (مدیریت هد ادمین)
"""
from database.db import get_connection


def init_faq_tables():
    """جداول FAQ"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS faq_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        category TEXT DEFAULT 'general',
        sort_order INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()


# ─── FAQ Management ─────────────────────────────────────────
def create_faq(question: str, answer: str, category: str = "general", sort_order: int = 0) -> int:
    """ایجاد سوال"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO faq_items (question, answer, category, sort_order)
        VALUES (?, ?, ?, ?)
        """,
        (question, answer, category, sort_order),
    )
    faq_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return faq_id


def get_all_faqs(active_only: bool = True) -> list:
    """تمام سوالات"""
    conn = get_connection()
    cursor = conn.cursor()
    if active_only:
        cursor.execute(
            "SELECT * FROM faq_items WHERE is_active = 1 ORDER BY sort_order, id ASC"
        )
    else:
        cursor.execute("SELECT * FROM faq_items ORDER BY sort_order, id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_faqs_by_category(category: str, active_only: bool = True) -> list:
    """سوالات یک دسته"""
    conn = get_connection()
    cursor = conn.cursor()
    if active_only:
        cursor.execute(
            "SELECT * FROM faq_items WHERE category = ? AND is_active = 1 ORDER BY sort_order",
            (category,),
        )
    else:
        cursor.execute(
            "SELECT * FROM faq_items WHERE category = ? ORDER BY sort_order",
            (category,),
        )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_faq(faq_id: int) -> dict | None:
    """دریافت یک سوال"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM faq_items WHERE id = ?", (faq_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_faq(faq_id: int, question: str = None, answer: str = None, category: str = None, sort_order: int = None) -> bool:
    """تغییر سوال"""
    updates = []
    params = []
    
    if question:
        updates.append("question = ?")
        params.append(question)
    if answer:
        updates.append("answer = ?")
        params.append(answer)
    if category:
        updates.append("category = ?")
        params.append(category)
    if sort_order is not None:
        updates.append("sort_order = ?")
        params.append(sort_order)
    
    if not updates:
        return False
    
    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(faq_id)
    
    conn = get_connection()
    cursor = conn.cursor()
    query = f"UPDATE faq_items SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, params)
    conn.commit()
    conn.close()
    return True


def toggle_faq(faq_id: int) -> int:
    """فعال/غیرفعال سوال"""
    faq = get_faq(faq_id)
    if not faq:
        return -1
    
    new_status = 0 if faq["is_active"] else 1
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE faq_items SET is_active = ? WHERE id = ?", (new_status, faq_id))
    conn.commit()
    conn.close()
    return new_status


def delete_faq(faq_id: int) -> bool:
    """حذف سوال"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM faq_items WHERE id = ?", (faq_id,))
    conn.commit()
    conn.close()
    return True


def get_faq_categories() -> list:
    """دسته‌های FAQ"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT category FROM faq_items WHERE is_active = 1 ORDER BY category")
    rows = cursor.fetchall()
    conn.close()
    return [row["category"] for row in rows]
