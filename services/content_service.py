from database.db import get_connection


def get_content(key: str, default: str = "") -> str:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT content
    FROM content_pages
    WHERE key = ?
    """, (key,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return default

    return row[0]