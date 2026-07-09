from pathlib import Path
from datetime import datetime
import shutil


BASE_DIR = Path(__file__).resolve().parent

DB_PATH = BASE_DIR / "bot.db"

BACKUP_DIR = BASE_DIR / "backups"


def main():
    if not DB_PATH.exists():
        print("Database file not found.")
        return

    BACKUP_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    backup_path = BACKUP_DIR / f"bot_backup_{timestamp}.db"

    shutil.copy2(DB_PATH, backup_path)

    print("================================")
    print("Database backup created.")
    print(f"Backup file: {backup_path}")
    print("================================")


if __name__ == "__main__":
    main()