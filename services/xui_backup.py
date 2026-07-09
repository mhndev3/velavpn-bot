"""
xui_backup.py — بکاپ گرفتن از دیتابیس پنل‌های X-UI.

پنل 3x-ui یک endpoint دارد که فایل خام x-ui.db را می‌دهد:
    GET /panel/api/server/getDb
با همان نشست لاگینِ موجود کار می‌کند؛ نیازی به SSH یا رمز جدید نیست.
"""
import asyncio
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

BACKUP_DIR = Path(__file__).resolve().parent.parent / "backups" / "xui"
_SQLITE_MAGIC = b"SQLite format 3"


def init_dir():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def _safe(name: str) -> str:
    keep = "-_."
    return "".join(ch if (ch.isalnum() or ch in keep) else "_" for ch in str(name))[:40] or "server"


def _verify_sqlite(data: bytes) -> tuple[bool, str]:
    """بررسی می‌کند فایل دانلودشده واقعاً یک دیتابیس سالم SQLite است."""
    if not data or not data.startswith(_SQLITE_MAGIC):
        return False, "فایل دریافتی دیتابیس SQLite نیست"
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            f.write(data)
            tmp = f.name
        conn = sqlite3.connect(tmp)
        try:
            ok = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if str(ok).lower() != "ok":
                return False, f"integrity_check: {ok}"
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()]
        finally:
            conn.close()
        if not tables:
            return False, "دیتابیس خالی است"
        return True, f"{len(tables)} جدول"
    except Exception as e:
        return False, repr(e)[:80]
    finally:
        if tmp:
            try:
                Path(tmp).unlink(missing_ok=True)
            except Exception:
                pass


async def fetch_panel_db(server: dict) -> bytes | None:
    """فایل x-ui.db یک سرور را دانلود می‌کند (None اگر نشد)."""
    from services.xui_service import XUIClient
    c = XUIClient(server)
    try:
        ok, _ = await c.login()
        if not ok:
            return None
        await c._refresh_csrf()
        s = await c._sess()
        r = await s.get(c.base_url + "/panel/api/server/getDb", headers=c._h_json())
        if r.status != 200:
            return None
        data = await r.read()
        return data if data.startswith(_SQLITE_MAGIC) else None
    except Exception:
        return None
    finally:
        try:
            await c.close()
        except Exception:
            pass


async def backup_all_panels() -> list[dict]:
    """
    از دیتابیس همهٔ سرورهای فعال بکاپ می‌گیرد.
    خروجی: لیستی از dict با کلیدهای label / ok / path / size / note
    """
    from database.db import get_active_servers
    init_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = []
    for srv in get_active_servers():
        label = srv.get("label") or f"srv{srv.get('id')}"
        entry = {"label": label, "ok": False, "path": None, "size": 0, "note": ""}
        data = await fetch_panel_db(srv)
        if not data:
            entry["note"] = "دانلود ناموفق (لاگین/دسترسی)"
            results.append(entry)
            continue
        ok, note = await asyncio.to_thread(_verify_sqlite, data)
        if not ok:
            entry["note"] = note
            results.append(entry)
            continue
        path = BACKUP_DIR / f"xui_{_safe(label)}_{ts}.db"
        try:
            await asyncio.to_thread(path.write_bytes, data)
        except Exception as e:
            entry["note"] = repr(e)[:60]
            results.append(entry)
            continue
        entry.update(ok=True, path=str(path), size=len(data), note=note)
        results.append(entry)
    cleanup_old(days=30)
    return results


def cleanup_old(days: int = 30):
    init_dir()
    now = datetime.now()
    for f in BACKUP_DIR.glob("xui_*.db"):
        try:
            age = (now - datetime.fromtimestamp(f.stat().st_mtime)).days
            if age > days:
                f.unlink()
        except Exception:
            pass
