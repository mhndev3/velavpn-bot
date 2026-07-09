"""
سیستم رفرال کامل — دعوت، کمیسیون خودکار
"""
from database.db import get_connection


def init_referral_tables():
    """جداول رفرال"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER NOT NULL,
        referred_id INTEGER NOT NULL UNIQUE,
        referral_code TEXT UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS referral_commissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER NOT NULL,
        order_id INTEGER NOT NULL,
        commission_toman INTEGER NOT NULL,
        commission_percent INTEGER NOT NULL,
        status TEXT DEFAULT 'pending',
        approved_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()


# ─── Referral Management ─────────────────────────────────────
def get_or_create_referral_code(telegram_id: int) -> str:
    """کد رفرال یا ایجاد"""
    import uuid
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT referral_code FROM referrals WHERE referrer_id = ? LIMIT 1",
        (telegram_id,),
    )
    row = cursor.fetchone()
    if row:
        conn.close()
        return row["referral_code"]
    
    # ایجاد کد جدید
    code = str(uuid.uuid4())[:8].upper()
    cursor.execute(
        "INSERT OR IGNORE INTO referrals (referrer_id, referral_code) VALUES (?, ?)",
        (telegram_id, code),
    )
    conn.commit()
    conn.close()
    return code


def add_referral(referrer_id: int, referred_id: int) -> bool:
    """اضافه کردن رفرال"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR IGNORE INTO referrals (referrer_id, referred_id, referral_code) VALUES (?, ?, ?)",
            (referrer_id, referred_id, get_or_create_referral_code(referrer_id)),
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        conn.close()
        return False


def get_referrer(referred_id: int) -> dict | None:
    """دریافت معرّف"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT referrer_id FROM referrals WHERE referred_id = ?", (referred_id,))
    row = cursor.fetchone()
    conn.close()
    return {"referrer_id": row["referrer_id"]} if row else None


def get_referral_stats(referrer_id: int) -> dict:
    """آمار رفرال"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # تعداد معرّفی‌ها
    cursor.execute(
        "SELECT COUNT(*) as count FROM referrals WHERE referrer_id = ?",
        (referrer_id,),
    )
    referred_count = cursor.fetchone()["count"]
    
    # کل کمیسیون‌ها
    cursor.execute(
        "SELECT COALESCE(SUM(commission_toman), 0) as total FROM referral_commissions WHERE referrer_id = ? AND status = 'approved'",
        (referrer_id,),
    )
    total_commission = cursor.fetchone()["total"]
    
    conn.close()
    return {
        "referred_count": referred_count,
        "total_commission": total_commission,
    }


def add_referral_commission(referrer_id: int, order_id: int, commission_toman: int, commission_percent: int) -> int:
    """اضافه کردن کمیسیون"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO referral_commissions
        (referrer_id, order_id, commission_toman, commission_percent)
        VALUES (?, ?, ?, ?)
        """,
        (referrer_id, order_id, commission_toman, commission_percent),
    )
    commission_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return commission_id


def approve_referral_commission(commission_id: int) -> bool:
    """تایید و واریز کمیسیون"""
    from database.wallet import add_to_wallet
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT referrer_id, commission_toman FROM referral_commissions WHERE id = ?",
        (commission_id,),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
    
    # تایید کمیسیون
    cursor.execute(
        "UPDATE referral_commissions SET status = 'approved', approved_at = CURRENT_TIMESTAMP WHERE id = ?",
        (commission_id,),
    )
    conn.commit()
    conn.close()
    
    # واریز به کیف‌پول
    add_to_wallet(row["referrer_id"], row["commission_toman"], f"کمیسیون رفرال (سفارش #{commission_id})")
    return True


def get_pending_referral_commissions(limit: int = 20) -> list:
    """کمیسیون‌های منتظر تایید"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT rc.*, r.referral_code
        FROM referral_commissions rc
        JOIN referrals r ON r.referrer_id = rc.referrer_id
        WHERE rc.status = 'pending'
        ORDER BY rc.id DESC LIMIT ?
        """,
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
