"""
سیستم تیکت — ساپورت و مسائل کاربران
"""
from database.db import get_connection


def init_ticket_tables():
    """جداول تیکت"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS support_tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER NOT NULL,
        subject TEXT NOT NULL,
        description TEXT,
        status TEXT DEFAULT 'open',
        priority TEXT DEFAULT 'normal',
        assigned_to INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        closed_at TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS ticket_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER NOT NULL,
        sender_id INTEGER NOT NULL,
        sender_type TEXT NOT NULL,
        message_text TEXT,
        file_id TEXT,
        file_type TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(ticket_id) REFERENCES support_tickets(id)
    );
    """)
    conn.commit()
    conn.close()


# ─── Ticket Management ───────────────────────────────────────
def create_ticket(telegram_id: int, subject: str, description: str = "", priority: str = "normal") -> int:
    """ایجاد تیکت"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO support_tickets (telegram_id, subject, description, priority)
        VALUES (?, ?, ?, ?)
        """,
        (telegram_id, subject, description, priority),
    )
    ticket_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return ticket_id


def get_ticket(ticket_id: int) -> dict | None:
    """دریافت تیکت"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM support_tickets WHERE id = ?", (ticket_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_tickets(telegram_id: int, status: str = None) -> list:
    """تیکت‌های کاربر"""
    conn = get_connection()
    cursor = conn.cursor()
    if status:
        cursor.execute(
            "SELECT * FROM support_tickets WHERE telegram_id = ? AND status = ? ORDER BY id DESC",
            (telegram_id, status),
        )
    else:
        cursor.execute(
            "SELECT * FROM support_tickets WHERE telegram_id = ? ORDER BY id DESC",
            (telegram_id,),
        )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_open_tickets(limit: int = 20) -> list:
    """تیکت‌های باز (برای ادمین)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM support_tickets
        WHERE status IN ('open', 'pending')
        ORDER BY priority DESC, id DESC LIMIT ?
        """,
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_ticket_message(ticket_id: int, sender_id: int, sender_type: str, message_text: str = "", file_id: str = "", file_type: str = "") -> int:
    """اضافه کردن پیام به تیکت"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO ticket_messages (ticket_id, sender_id, sender_type, message_text, file_id, file_type)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (ticket_id, sender_id, sender_type, message_text, file_id, file_type),
    )
    message_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return message_id


def get_ticket_messages(ticket_id: int) -> list:
    """پیام‌های تیکت"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM ticket_messages WHERE ticket_id = ? ORDER BY created_at ASC",
        (ticket_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def close_ticket(ticket_id: int) -> bool:
    """بسته کردن تیکت"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE support_tickets SET status = 'closed', closed_at = CURRENT_TIMESTAMP WHERE id = ?",
        (ticket_id,),
    )
    conn.commit()
    conn.close()
    return True


def assign_ticket(ticket_id: int, admin_id: int) -> bool:
    """اختصاص تیکت به ادمین"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE support_tickets SET assigned_to = ?, status = 'pending' WHERE id = ?",
        (admin_id, ticket_id),
    )
    conn.commit()
    conn.close()
    return True
