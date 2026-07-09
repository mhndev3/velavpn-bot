"""
سیستم بکاپ خودکار — هر ساعت
بکاپ از طریق SQLite online backup API انجام می‌شود تا زیر WAL سازگار و بدون قفل باشد.
"""
import shutil
import os
import sqlite3
from datetime import datetime
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent.parent / "bot.db"
BACKUP_DIR = Path(__file__).resolve().parent.parent / "backups"


def init_backup_dir():
    """ایجاد دایرکتوری بکاپ"""
    BACKUP_DIR.mkdir(exist_ok=True)


def backup_database():
    """بکاپ ایمن دیتابیس (سازگار با WAL، بدون قفل‌کردن دیتابیس اصلی)"""
    init_backup_dir()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"bot_{timestamp}.db"

    try:
        src = sqlite3.connect(str(DB_PATH), timeout=30)
        try:
            dst = sqlite3.connect(str(backup_file))
            try:
                src.backup(dst)   # online backup API — اتمیک و سازگار با WAL (فقط خواندن؛ نوشتن‌ها را قفل نمی‌کند)
            finally:
                dst.close()
        finally:
            src.close()
        cleanup_old_backups()
        return True
    except Exception:
        # fallback: کپی ساده (در بدترین حالت)
        try:
            shutil.copy2(DB_PATH, backup_file)
            cleanup_old_backups()
            return True
        except Exception:
            return False


def cleanup_old_backups(days: int = 30):
    """حذف بکاپ‌های قدیمی‌تر از N روز"""
    init_backup_dir()
    
    now = datetime.now()
    for backup_file in BACKUP_DIR.glob("bot_*.db"):
        file_age = (now - datetime.fromtimestamp(backup_file.stat().st_mtime)).days
        if file_age > days:
            try:
                backup_file.unlink()
                print(f"🗑 بکاپ قدیمی حذف: {backup_file.name}")
            except Exception as e:
                print(f"خطا در حذف {backup_file}: {e}")


def get_latest_backup() -> Path | None:
    """آخرین فایل بکاپ"""
    init_backup_dir()
    
    backups = sorted(BACKUP_DIR.glob("bot_*.db"), reverse=True)
    return backups[0] if backups else None


def restore_from_backup(backup_file: Path) -> bool:
    """بازگردانی از بکاپ"""
    try:
        shutil.copy2(backup_file, DB_PATH)
        print(f"✅ بازگردانی موفق از: {backup_file}")
        return True
    except Exception as e:
        print(f"❌ خطا در بازگردانی: {e}")
        return False


async def start_hourly_backup(bot):
    """بکاپ خودکار هر ۲۴ ساعت: دیتابیس بات + دیتابیس پنل‌های X-UI"""
    import asyncio
    from config.settings import ADMIN_IDS, DEVELOPER_ID

    while True:
        try:
            await asyncio.sleep(86400)  # ۲۴ ساعت
            await run_full_backup(bot)
        except Exception as e:
            print(f"خطا در بکاپ خودکار: {e}")
            await asyncio.sleep(60)  # ۱ دقیقه و دوباره سعی کن


async def run_full_backup(bot, notify_id: int | None = None) -> str:
    """
    یک دور کامل بکاپ: bot.db + دیتابیس همهٔ پنل‌های X-UI.
    فایل‌ها برای دولوپر (یا notify_id) ارسال می‌شوند. گزارش متنی برمی‌گرداند.
    """
    import asyncio
    from config.settings import ADMIN_IDS, DEVELOPER_ID
    from aiogram.types import FSInputFile

    if notify_id is None:
        notify_id = DEVELOPER_ID if DEVELOPER_ID else (ADMIN_IDS[0] if ADMIN_IDS else None)

    lines = ["🗄 <b>گزارش بکاپ</b>", "━━━━━━━━━━━━━━"]

    # ۱) دیتابیس خود بات
    bot_ok = await asyncio.to_thread(backup_database)
    lines.append(("✅" if bot_ok else "❌") + " دیتابیس بات (bot.db)")

    # ۲) دیتابیس پنل‌های X-UI
    panel_files = []
    try:
        from services.xui_backup import backup_all_panels
        results = await backup_all_panels()
        if not results:
            lines.append("ℹ️ سرور فعالی برای بکاپ نبود")
        for r in results:
            if r["ok"]:
                size_kb = round(r["size"] / 1024, 1)
                lines.append(f"✅ پنل «{r['label']}» — {size_kb} KB ({r['note']})")
                panel_files.append(r["path"])
            else:
                lines.append(f"❌ پنل «{r['label']}» — {r['note']}")
    except Exception as e:
        lines.append(f"❌ خطا در بکاپ پنل‌ها: {repr(e)[:60]}")

    report = "\n".join(lines)

    if notify_id:
        try:
            await bot.send_message(chat_id=notify_id, text=report)
        except Exception:
            pass
        # ارسال فایل‌ها
        try:
            latest = get_latest_backup()
            if bot_ok and latest:
                await bot.send_document(chat_id=notify_id,
                                        document=FSInputFile(str(latest)),
                                        caption="🤖 دیتابیس بات")
        except Exception:
            pass
        for p in panel_files:
            try:
                await bot.send_document(chat_id=notify_id,
                                        document=FSInputFile(p),
                                        caption="🖥 دیتابیس پنل X-UI")
            except Exception:
                pass

    return report
