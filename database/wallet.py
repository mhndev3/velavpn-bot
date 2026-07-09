"""
database/wallet.py — FIX: database locked
همه عملیات approve_wallet_charge در یک connection انجام می‌شه
"""
from datetime import datetime
from database.db import get_connection


def init_wallet_tables():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS wallets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE NOT NULL,
        balance_toman INTEGER DEFAULT 0,
        total_charged_toman INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS wallet_charges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER NOT NULL,
        amount_toman INTEGER NOT NULL,
        payment_method TEXT NOT NULL,
        receipt_type TEXT,
        receipt_text TEXT,
        file_id TEXT,
        status TEXT DEFAULT 'waiting_admin_review',
        approved_by INTEGER,
        approved_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS wallet_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        amount_toman INTEGER NOT NULL,
        description TEXT,
        order_id INTEGER,
        charge_id INTEGER,
        balance_after INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()


def get_wallet(telegram_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM wallets WHERE telegram_id = ?", (telegram_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_or_create_wallet(telegram_id: int) -> dict:
    wallet = get_wallet(telegram_id)
    if wallet:
        return wallet
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO wallets (telegram_id, balance_toman) VALUES (?, 0)", (telegram_id,))
    conn.commit()
    conn.close()
    return get_wallet(telegram_id)


def add_to_wallet(telegram_id: int, amount_toman: int, description: str = "", conn=None) -> bool:
    """
    پول به کیف پول اضافه کن.
    اگه conn پاس داده بشه از همون connection استفاده می‌کنه (برای جلوگیری از database locked)
    """
    close_after = False
    if conn is None:
        conn = get_connection()
        close_after = True

    cursor = conn.cursor()
    cursor.execute("SELECT balance_toman FROM wallets WHERE telegram_id = ?", (telegram_id,))
    row = cursor.fetchone()
    current = row["balance_toman"] if row else 0
    new_balance = current + amount_toman

    cursor.execute(
        "INSERT OR IGNORE INTO wallets (telegram_id, balance_toman) VALUES (?, 0)",
        (telegram_id,)
    )
    cursor.execute(
        "UPDATE wallets SET balance_toman = ?, updated_at = CURRENT_TIMESTAMP WHERE telegram_id = ?",
        (new_balance, telegram_id),
    )
    cursor.execute(
        "INSERT INTO wallet_transactions (telegram_id, type, amount_toman, description, balance_after) VALUES (?, ?, ?, ?, ?)",
        (telegram_id, "charge", amount_toman, description or "شارژ کیف پول", new_balance),
    )

    if close_after:
        conn.commit()
        conn.close()
    return True


def deduct_from_wallet(telegram_id: int, amount_toman: int, order_id: int = None) -> bool:
    wallet = get_wallet(telegram_id)
    if not wallet or wallet["balance_toman"] < amount_toman:
        return False
    new_balance = wallet["balance_toman"] - amount_toman
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE wallets SET balance_toman = ?, updated_at = CURRENT_TIMESTAMP WHERE telegram_id = ?",
        (new_balance, telegram_id),
    )
    cursor.execute(
        "INSERT INTO wallet_transactions (telegram_id, type, amount_toman, description, order_id, balance_after) VALUES (?, ?, ?, ?, ?, ?)",
        (telegram_id, "purchase", amount_toman, "خرید", order_id, new_balance),
    )
    conn.commit()
    conn.close()
    return True


def create_wallet_charge(
    telegram_id: int, amount_toman: int, payment_method: str,
    receipt_type: str = "text", receipt_text: str = "", file_id: str = "",
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO wallet_charges
        (telegram_id, amount_toman, payment_method, receipt_type, receipt_text, file_id, status)
        VALUES (?, ?, ?, ?, ?, ?, 'waiting_admin_review')""",
        (telegram_id, amount_toman, payment_method, receipt_type, receipt_text, file_id),
    )
    charge_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return charge_id


def get_wallet_charge(charge_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM wallet_charges WHERE id = ?", (charge_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_pending_wallet_charges(limit: int = 20) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM wallet_charges WHERE status = 'waiting_admin_review' ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def approve_wallet_charge(charge_id: int, approved_by: int) -> bool:
    """
    FIX: همه عملیات در یک connection — database locked نمی‌شه
    """
    charge = get_wallet_charge(charge_id)
    if not charge:
        return False

    conn = get_connection()
    try:
        cursor = conn.cursor()

        # 1. وضعیت شارژ رو تغییر بده
        cursor.execute(
            "UPDATE wallet_charges SET status='approved', approved_by=?, approved_at=CURRENT_TIMESTAMP WHERE id=?",
            (approved_by, charge_id),
        )

        # 2. موجودی کیف‌پول رو اضافه کن (همون connection)
        add_to_wallet(
            charge["telegram_id"],
            charge["amount_toman"],
            "شارژ تایید شده #" + str(charge_id),
            conn=conn,  # ← همون connection، lock نمی‌شه
        )

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        return False
    finally:
        conn.close()


def reject_wallet_charge(charge_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE wallet_charges SET status='rejected' WHERE id=?", (charge_id,))
    conn.commit()
    conn.close()
    return True


def get_user_wallet_charges(telegram_id: int, limit: int = 10) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM wallet_charges WHERE telegram_id=? ORDER BY id DESC LIMIT ?",
        (telegram_id, limit),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_wallet_transactions(telegram_id: int, limit: int = 20) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM wallet_transactions WHERE telegram_id=? ORDER BY id DESC LIMIT ?",
        (telegram_id, limit),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
