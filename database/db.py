import sqlite3
from pathlib import Path
import queue as _queue

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "bot.db"

# ─── Connection Pool ─────────────────────────────────────────
# به‌جای ساخت/بستن کانکشن در هر عملیات (۲۰۰+ نقطه)، از یک استخر استفاده می‌کنیم.
# مزایا: سرعت بیشتر (بدون churn) و جلوگیری از قفل‌شدن دیتابیس؛ چون close()
# به‌جای بستن، هر تراکنشِ ناتمام را rollback می‌کند و کانکشن را برمی‌گرداند.
_POOL_MAX = 8
_pool = _queue.LifoQueue(maxsize=_POOL_MAX)


class _PooledConnection(sqlite3.Connection):
    def close(self):
        # تراکنش ناتمام را ببند تا قفلِ نوشتن باقی نماند
        try:
            if self.in_transaction:
                self.rollback()
        except Exception:
            try:
                sqlite3.Connection.close(self)
            except Exception:
                pass
            return
        # برگرداندن به استخر؛ اگر پر بود، واقعاً ببند
        try:
            _pool.put_nowait(self)
        except _queue.Full:
            try:
                sqlite3.Connection.close(self)
            except Exception:
                pass

    def _hard_close(self):
        try:
            sqlite3.Connection.close(self)
        except Exception:
            pass


def _new_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False,
                           factory=_PooledConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA wal_autocheckpoint=256")
    conn.execute("PRAGMA cache_size=-8000")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def get_connection():
    """یک کانکشن از استخر می‌دهد (یا می‌سازد). با conn.close() به استخر برمی‌گردد."""
    while True:
        try:
            conn = _pool.get_nowait()
        except _queue.Empty:
            return _new_connection()
        # بررسی سلامت کانکشنِ بازیافتی
        try:
            conn.execute("SELECT 1")
            return conn
        except Exception:
            conn._hard_close()
            continue


def checkpoint_wal():
    """
    WAL checkpoint در حالت PASSIVE — فایل WAL را جمع می‌کند بدون اینکه قفل انحصاری
    بگیرد یا با نوشتن‌های در حال اجرا بجنگد (برخلاف TRUNCATE). کاملاً بی‌خطر است.
    """
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        try:
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def _retry_on_locked(fn, tries: int = 5, delay: float = 0.2):
    """
    اجرای یک عملیات دیتابیس با تلاش مجدد در صورت قفل موقت.
    برای نوشتن‌های حساس تا مطمئن شویم زیر بار، «database is locked» کاربر را اذیت نکند.
    """
    import time as _t
    last = None
    for _ in range(tries):
        try:
            return fn()
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() or "busy" in str(e).lower():
                last = e
                _t.sleep(delay)
                continue
            raise
    if last:
        raise last


# ─── Init ────────────────────────────────────────────────────
def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE NOT NULL,
        full_name TEXT,
        username TEXT,
        referrer_id INTEGER,
        is_banned INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS sub_admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE NOT NULL,
        full_name TEXT,
        username TEXT,
        added_by INTEGER NOT NULL,
        commission_percent INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        note TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS head_admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE NOT NULL,
        added_by INTEGER,
        note TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS xui_servers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        label TEXT NOT NULL,
        url TEXT NOT NULL,
        username TEXT NOT NULL,
        password TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        max_clients INTEGER DEFAULT 500,
        current_clients INTEGER DEFAULT 0,
        priority INTEGER DEFAULT 0,
        note TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS payment_gateways (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gateway_type TEXT NOT NULL,
        label TEXT NOT NULL,
        merchant_id TEXT,
        api_key TEXT,
        callback_url TEXT,
        is_active INTEGER DEFAULT 1,
        is_default INTEGER DEFAULT 0,
        extra_config TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        service_type TEXT DEFAULT 'single',
        name TEXT NOT NULL,
        description TEXT,
        server_id INTEGER,
        is_active INTEGER DEFAULT 1,
        FOREIGN KEY(server_id) REFERENCES xui_servers(id)
    );

    CREATE TABLE IF NOT EXISTS plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        service_id INTEGER,
        title TEXT NOT NULL,
        price_toman INTEGER NOT NULL,
        duration_days INTEGER NOT NULL,
        traffic_gb INTEGER DEFAULT 0,
        max_clients INTEGER DEFAULT 1,
        is_active INTEGER DEFAULT 1,
        FOREIGN KEY(service_id) REFERENCES services(id)
    );

    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER NOT NULL,
        plan_id INTEGER NOT NULL,
        service_name TEXT NOT NULL,
        plan_title TEXT NOT NULL,
        price_toman INTEGER NOT NULL,
        duration_days INTEGER NOT NULL,
        payment_method TEXT,
        payment_gateway_id INTEGER,
        gateway_ref_id TEXT,
        status TEXT DEFAULT 'pending',
        discount_code TEXT,
        discount_amount INTEGER DEFAULT 0,
        final_price_toman INTEGER,
        sub_admin_id INTEGER,
        referral_processed INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        telegram_id INTEGER NOT NULL,
        payment_method TEXT NOT NULL,
        receipt_type TEXT,
        receipt_text TEXT,
        file_id TEXT,
        gateway_ref_id TEXT,
        status TEXT DEFAULT 'waiting_admin_review',
        reviewed_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS xui_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER NOT NULL,
        order_id INTEGER NOT NULL UNIQUE,
        server_id INTEGER NOT NULL,
        xui_client_id TEXT,
        xui_inbound_id INTEGER,
        email TEXT,
        config_link TEXT,
        config_type TEXT,
        traffic_gb INTEGER DEFAULT 0,
        status TEXT DEFAULT 'active',
        expires_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(server_id) REFERENCES xui_servers(id)
    );

    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER NOT NULL,
        order_id INTEGER NOT NULL,
        service_name TEXT NOT NULL,
        plan_title TEXT NOT NULL,
        duration_days INTEGER NOT NULL,
        status TEXT DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP,
        delivery_text TEXT,
        delivery_file_id TEXT,
        delivery_file_type TEXT
    );

    CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inviter_id INTEGER NOT NULL,
        invited_id INTEGER NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS referral_rewards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inviter_id INTEGER NOT NULL,
        invited_id INTEGER NOT NULL,
        order_id INTEGER NOT NULL,
        reward_amount INTEGER DEFAULT 0,
        bonus_days INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS discount_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        discount_type TEXT NOT NULL,
        amount INTEGER NOT NULL,
        max_uses INTEGER DEFAULT 1,
        used_count INTEGER DEFAULT 0,
        expires_at TIMESTAMP,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS discount_usages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        discount_code_id INTEGER NOT NULL,
        telegram_id INTEGER NOT NULL,
        order_id INTEGER,
        used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER NOT NULL,
        subject TEXT,
        status TEXT DEFAULT 'open',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        closed_at TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS ticket_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER NOT NULL,
        sender_type TEXT NOT NULL,
        sender_id INTEGER NOT NULL,
        message_text TEXT,
        file_id TEXT,
        file_type TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS content_pages (
        key TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        file_id TEXT,
        file_type TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS faq_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        sort_order INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS bot_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS gateway_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        gateway_id INTEGER,
        ref_id TEXT,
        amount INTEGER,
        status TEXT,
        raw_response TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    _run_migrations(cursor)
    conn.commit()
    conn.close()


def _run_migrations(cursor):
    """اضافه کردن ستون‌های جدید بدون از دست دادن داده قدیمی"""
    new_cols = [
        ("users",    "is_banned",          "INTEGER DEFAULT 0"),
        ("orders",   "payment_gateway_id", "INTEGER"),
        ("orders",   "gateway_ref_id",     "TEXT"),
        ("orders",   "sub_admin_id",       "INTEGER"),
        ("payments", "gateway_ref_id",     "TEXT"),
        ("payments", "reviewed_by",        "INTEGER"),
        ("services", "server_id",          "INTEGER"),
        ("plans",    "traffic_gb",         "INTEGER DEFAULT 0"),
        ("plans",    "max_clients",        "INTEGER DEFAULT 1"),
        ("sub_admins", "commission_percent", "INTEGER DEFAULT 0"),
    ]
    for table, col, definition in new_cols:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
        except Exception:
            pass


# ─── Bot Settings (با کش حافظه‌ای برای مقیاس‌پذیری) ───────────
# تنظیمات خیلی زیاد خوانده می‌شوند (هر رندر منو ~۲۰ بار) ولی به‌ندرت تغییر می‌کنند.
# کل جدول را با TTL کوتاه کش می‌کنیم تا زیر بار ۳۰۰ کاربر، هزاران کوئری حذف شود.
import time as _time

_settings_cache = {}
_settings_cache_ts = 0.0
_SETTINGS_TTL = 5.0  # ثانیه — تغییرات ادمین حداکثر ظرف ۵ ثانیه اعمال می‌شوند


def _reload_settings_cache():
    global _settings_cache, _settings_cache_ts
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM bot_settings")
        _settings_cache = {row["key"]: row["value"] for row in cursor.fetchall()}
        _settings_cache_ts = _time.time()
    finally:
        conn.close()


def get_setting(key: str, default: str = "") -> str:
    if (_time.time() - _settings_cache_ts) > _SETTINGS_TTL:
        try:
            _reload_settings_cache()
        except Exception:
            pass
    val = _settings_cache.get(key)
    return val if val is not None else default


def set_setting(key: str, value: str):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO bot_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
        """, (key, value))
        conn.commit()
    finally:
        conn.close()
    # به‌روزرسانی فوری کش تا تغییر بلافاصله اعمال شود
    _settings_cache[key] = value


def get_all_settings() -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM bot_settings")
    rows = cursor.fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}


# ─── Users ───────────────────────────────────────────────────
def save_user(telegram_id: int, full_name: str, username: str):
    def _do():
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO users (telegram_id, full_name, username)
                VALUES (?, ?, ?)
            """, (telegram_id, full_name, username))
            cursor.execute("""
                UPDATE users SET full_name = ?, username = ? WHERE telegram_id = ?
            """, (full_name, username, telegram_id))
            conn.commit()
        finally:
            conn.close()
    _retry_on_locked(_do)


def get_user(telegram_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_count(table_name: str, where: str = None) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    q = f"SELECT COUNT(*) as cnt FROM {table_name}"
    if where:
        q += f" WHERE {where}"
    cursor.execute(q)
    row = cursor.fetchone()
    conn.close()
    return row["cnt"] if row else 0


def get_recent_users(limit: int = 10) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Sub Admins ──────────────────────────────────────────────
def get_sub_admin(telegram_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sub_admins WHERE telegram_id = ? AND is_active = 1", (telegram_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_sub_admins() -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sub_admins ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Head Admins (مدیریت از داخل بات) ────────────────────────
def get_head_admins() -> list:
    """لیست هد‌ادمین‌هایی که از داخل بات اضافه شده‌اند (به‌جز ADMIN_IDS ثابت)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM head_admins ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_head_admin(telegram_id: int, added_by: int = 0, note: str = "") -> bool:
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO head_admins (telegram_id, added_by, note) VALUES (?, ?, ?)",
            (int(telegram_id), added_by, note),
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def remove_head_admin(telegram_id: int) -> bool:
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM head_admins WHERE telegram_id = ?", (int(telegram_id),))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def is_head_admin_db(telegram_id: int) -> bool:
    """فقط جدول head_admins را چک می‌کند (بدون ADMIN_IDS) — برای __contains__ در settings."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM head_admins WHERE telegram_id = ? LIMIT 1", (int(telegram_id),))
        found = cursor.fetchone() is not None
        conn.close()
        return found
    except Exception:
        return False


def is_head_admin(telegram_id: int) -> bool:
    """هد‌ادمین = ADMIN_IDS ثابت یا جدول head_admins (از طریق __contains__ هوشمند)."""
    try:
        from config.settings import ADMIN_IDS
        return int(telegram_id) in ADMIN_IDS
    except Exception:
        return is_head_admin_db(telegram_id)


def add_sub_admin(telegram_id: int, full_name: str, username: str,
                  added_by: int, commission_percent: int = 0, note: str = "") -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO sub_admins
        (telegram_id, full_name, username, added_by, commission_percent, is_active, note)
        VALUES (?, ?, ?, ?, ?, 1, ?)
    """, (telegram_id, full_name, username, added_by, commission_percent, note))
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return row_id


def toggle_sub_admin(telegram_id: int) -> int:
    sa = get_sub_admin(telegram_id) or get_sub_admin_any(telegram_id)
    if not sa:
        return -1
    new_status = 0 if sa["is_active"] else 1
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE sub_admins SET is_active = ? WHERE telegram_id = ?",
                   (new_status, telegram_id))
    conn.commit()
    conn.close()
    return new_status


def get_sub_admin_any(telegram_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sub_admins WHERE telegram_id = ?", (telegram_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_sub_admin_sales(sub_admin_id: int) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) as total_orders,
               COALESCE(SUM(final_price_toman), 0) as total_revenue
        FROM orders
        WHERE sub_admin_id = ? AND status = 'approved'
    """, (sub_admin_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"total_orders": row["total_orders"], "total_revenue": row["total_revenue"]}
    return {"total_orders": 0, "total_revenue": 0}


def get_sub_admin_orders(sub_admin_id: int, limit: int = 20) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM orders WHERE sub_admin_id = ?
        ORDER BY created_at DESC LIMIT ?
    """, (sub_admin_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── XUI Servers ─────────────────────────────────────────────
def get_all_servers() -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM xui_servers ORDER BY priority DESC, id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_active_servers() -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM xui_servers WHERE is_active = 1
        ORDER BY priority DESC, current_clients ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_server(server_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM xui_servers WHERE id = ?", (server_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def add_server(label: str, url: str, username: str, password: str,
               max_clients: int = 500, priority: int = 0, note: str = "") -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO xui_servers (label, url, username, password, max_clients, priority, note)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (label, url, username, password, max_clients, priority, note))
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return row_id


def update_server(server_id: int, **kwargs):
    allowed = {"label", "url", "username", "password", "is_active",
               "max_clients", "priority", "note", "current_clients", "domain"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE xui_servers SET {set_clause} WHERE id = ?",
                   (*fields.values(), server_id))
    conn.commit()
    conn.close()


def toggle_server(server_id: int) -> int:
    server = get_server(server_id)
    if not server:
        return -1
    new_status = 0 if server["is_active"] else 1
    update_server(server_id, is_active=new_status)
    return new_status


def get_best_server() -> dict | None:
    servers = get_active_servers()
    available = [s for s in servers if s["current_clients"] < s["max_clients"]]
    return available[0] if available else None


def increment_server_clients(server_id: int, delta: int = 1):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE xui_servers SET current_clients = current_clients + ? WHERE id = ?
    """, (delta, server_id))
    conn.commit()
    conn.close()


# ─── Payment Gateways ────────────────────────────────────────
def get_all_gateways() -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM payment_gateways ORDER BY is_default DESC, id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_active_gateways() -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM payment_gateways WHERE is_active = 1
        ORDER BY is_default DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_default_gateway() -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM payment_gateways WHERE is_active = 1 AND is_default = 1 LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_gateway(gateway_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM payment_gateways WHERE id = ?", (gateway_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def add_gateway(gateway_type: str, label: str, merchant_id: str = "",
                api_key: str = "", callback_url: str = "",
                extra_config: str = "") -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO payment_gateways
        (gateway_type, label, merchant_id, api_key, callback_url, extra_config)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (gateway_type, label, merchant_id, api_key, callback_url, extra_config))
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return row_id


def set_default_gateway(gateway_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE payment_gateways SET is_default = 0")
    cursor.execute("UPDATE payment_gateways SET is_default = 1 WHERE id = ?", (gateway_id,))
    conn.commit()
    conn.close()


def toggle_gateway(gateway_id: int) -> int:
    gw = get_gateway(gateway_id)
    if not gw:
        return -1
    new_status = 0 if gw["is_active"] else 1
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE payment_gateways SET is_active = ? WHERE id = ?",
                   (new_status, gateway_id))
    conn.commit()
    conn.close()
    return new_status


def delete_gateway(gateway_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM payment_gateways WHERE id = ?", (gateway_id,))
    conn.commit()
    conn.close()


def log_gateway(order_id: int, gateway_id: int, ref_id: str,
                amount: int, status: str, raw_response: str = ""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO gateway_logs (order_id, gateway_id, ref_id, amount, status, raw_response)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (order_id, gateway_id, ref_id, amount, status, raw_response))
    conn.commit()
    conn.close()


# ─── XUI Accounts ────────────────────────────────────────────
def save_xui_account(telegram_id: int, order_id: int, server_id: int,
                     xui_client_id: str, xui_inbound_id: int, email: str,
                     config_link: str, config_type: str,
                     traffic_gb: int, expires_at: str,
                     sub_id: str = "") -> int:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO xui_accounts
            (telegram_id, order_id, server_id, xui_client_id, xui_inbound_id,
             email, config_link, config_type, traffic_gb, expires_at, sub_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
        """, (telegram_id, order_id, server_id, xui_client_id, xui_inbound_id,
              email, config_link, config_type, traffic_gb, expires_at, sub_id))
        row_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()
    # مهم: increment در کانکشن جدا و بعد از commit/close تا self-deadlock رخ ندهد
    try:
        increment_server_clients(server_id, 1)
    except Exception:
        pass
    return row_id


def get_xui_account_by_order(order_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM xui_accounts WHERE order_id = ?", (order_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_xui_accounts(telegram_id: int) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT xa.*, s.label AS server_label
        FROM xui_accounts xa
        LEFT JOIN xui_servers s ON s.id = xa.server_id
        WHERE xa.telegram_id = ? AND xa.status = 'active'
        ORDER BY xa.created_at DESC
    """, (telegram_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Services & Plans ────────────────────────────────────────
def get_services(active_only: bool = True) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    where = "WHERE is_active = 1" if active_only else ""
    cursor.execute(f"SELECT * FROM services {where} ORDER BY category, id")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_service(service_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM services WHERE id = ?", (service_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_services_by_category(category: str) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM services WHERE category = ? AND is_active = 1 ORDER BY id
    """, (category,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_plans_for_service(service_id: int, active_only: bool = True) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    where = "AND is_active = 1" if active_only else ""
    cursor.execute(f"""
        SELECT * FROM plans WHERE service_id = ? {where} ORDER BY duration_days, price_toman
    """, (service_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_plan(plan_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, s.name AS service_name, s.category, s.service_type, s.server_id
        FROM plans p
        JOIN services s ON s.id = p.service_id
        WHERE p.id = ?
    """, (plan_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


# ─── Orders ──────────────────────────────────────────────────
def get_order(order_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_order_status(order_id: int, status: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()
    conn.close()


def get_recent_orders(limit: int = 10) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_pending_payments(limit: int = 20) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, o.service_name, o.plan_title, o.price_toman,
               o.final_price_toman, o.discount_code, o.discount_amount
        FROM payments p
        JOIN orders o ON o.id = p.order_id
        WHERE p.status = 'waiting_admin_review'
        ORDER BY p.id DESC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Payments ────────────────────────────────────────────────
def update_payment_status(payment_id: int, status: str, reviewed_by: int = None):
    conn = get_connection()
    cursor = conn.cursor()
    if reviewed_by:
        cursor.execute("""
            UPDATE payments SET status = ?, reviewed_by = ? WHERE id = ?
        """, (status, reviewed_by, payment_id))
    else:
        cursor.execute("UPDATE payments SET status = ? WHERE id = ?",
                       (status, payment_id))
    conn.commit()
    conn.close()


# ─── Subscriptions ───────────────────────────────────────────
def get_active_subscriptions(limit: int = 20) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM subscriptions WHERE status = 'active'
        ORDER BY id DESC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_subscriptions(telegram_id: int) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM subscriptions WHERE telegram_id = ? AND status = 'active'
        ORDER BY created_at DESC
    """, (telegram_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_subscription_by_order(telegram_id: int, order_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM subscriptions WHERE order_id = ? AND telegram_id = ?
        ORDER BY id DESC LIMIT 1
    """, (order_id, telegram_id))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


# --- required channels + onboarding helpers ---
def get_required_channels():
    conn = get_connection(); cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM required_channels ORDER BY id"); rows = cur.fetchall()
    except Exception:
        rows = []
    conn.close(); return [dict(r) for r in rows]


def add_required_channel(chat_id, title="", url=""):
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("INSERT INTO required_channels (chat_id, title, url) VALUES (?, ?, ?)", (str(chat_id), title or "", url or ""))
        conn.commit(); conn.close(); return True
    except Exception:
        return False


def remove_required_channel(channel_id):
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("DELETE FROM required_channels WHERE id = ?", (int(channel_id),))
        conn.commit(); conn.close(); return True
    except Exception:
        return False


def get_user(telegram_id):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    row = cur.fetchone(); conn.close(); return dict(row) if row else None


def set_user_field(telegram_id, field, value):
    if field not in ("phone", "custom_username", "rules_accepted", "onboarding_done"):
        return False
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("UPDATE users SET " + field + " = ? WHERE telegram_id = ?", (value, telegram_id))
        conn.commit(); conn.close(); return True
    except Exception:
        return False


def is_onboarding_done(telegram_id):
    u = get_user(telegram_id)
    return bool(u and u.get("onboarding_done"))


# ─── اکانت تست: ثبت و بررسی محدودیت (ضدسوءاستفاده) ──────────
def has_received_test_account(telegram_id):
    """آیا این کاربر قبلاً اکانت تست دریافت کرده است؟"""
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM test_account_log WHERE telegram_id = ?", (telegram_id,))
        n = cur.fetchone()[0]; conn.close()
        return n > 0
    except Exception:
        return False


def count_test_accounts(telegram_id):
    """تعداد اکانت‌های تستی که این کاربر گرفته."""
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM test_account_log WHERE telegram_id = ?", (telegram_id,))
        n = cur.fetchone()[0]; conn.close()
        return int(n)
    except Exception:
        return 0


def log_test_account(telegram_id, email, server_id, inbound_id, traffic_gb, duration_hours):
    """ثبت یک اکانت تستِ دریافت‌شده."""
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute(
            "INSERT INTO test_account_log (telegram_id, email, server_id, inbound_id, traffic_gb, duration_hours) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (telegram_id, email, server_id, inbound_id, traffic_gb, duration_hours),
        )
        conn.commit(); conn.close(); return True
    except Exception:
        return False
