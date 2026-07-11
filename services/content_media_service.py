from database.db import get_connection
from services.banner_service import send_banner
import time as _time


def rows_to_dicts(cursor, rows):
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


# کش صفحات محتوا (پرخوانش، کم‌تغییر) — کاهش کوئری زیر بار سنگین
_content_cache = {}          # key -> (data|None, ts)
_CONTENT_TTL = 10.0


def get_content_page(key: str):
    hit = _content_cache.get(key)
    if hit and (_time.time() - hit[1]) < _CONTENT_TTL:
        return hit[0]

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT
        key,
        title,
        content,
        file_id,
        file_type,
        updated_at
    FROM content_pages
    WHERE key = ?
    """, (key,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        _content_cache[key] = (None, _time.time())
        return None
    data = rows_to_dicts(cursor, [row])[0]
    conn.close()
    _content_cache[key] = (data, _time.time())
    return data


def update_content_page(
    key: str,
    title: str,
    content: str,
    file_id=None,
    file_type=None
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT OR REPLACE INTO content_pages (
        key,
        title,
        content,
        file_id,
        file_type,
        updated_at
    )
    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (
        key,
        title,
        content,
        file_id,
        file_type
    ))

    conn.commit()
    conn.close()
    # باطل‌کردن کش تا تغییر ادمین بلافاصله دیده شود
    _content_cache.pop(key, None)


async def send_content_page(
    message,
    key: str,
    fallback_text: str,
    user=None
):
    page = get_content_page(key)
    text = fallback_text

    # entityهای ذخیره‌شده (ایموجی پریمیوم) برای این کلید
    from services.ui_render import get_ui_entities
    ents = get_ui_entities(key)
    ent_kw = {"entities": ents, "parse_mode": None} if ents else {}
    cap_kw = {"caption_entities": ents, "parse_mode": None} if ents else {}

    if page:
        text = page.get("content") or fallback_text
        file_id = page.get("file_id")
        file_type = page.get("file_type")

        # جایگزینی placeholderها (آیدی، تاریخ شمسی، ساعت و ...)
        try:
            from services.placeholders import apply_placeholders
            text = apply_placeholders(text, user)
        except Exception:
            pass

        try:
            if file_id and file_type == "photo":
                await message.answer_photo(photo=file_id, caption=text, **cap_kw)
                return

            if file_id and file_type == "video":
                await message.answer_video(video=file_id, caption=text, **cap_kw)
                return

            if file_id and file_type == "document":
                await message.answer_document(document=file_id, caption=text, **cap_kw)
                return
        except Exception:
            pass

    # اطمینان از اعمال placeholder روی متن نهایی (حالت fallback هم)
    try:
        from services.placeholders import apply_placeholders
        text = apply_placeholders(text, user)
    except Exception:
        pass

    banner_sent = await send_banner(message, key, caption=text)
    if not banner_sent:
        await message.answer(text, **ent_kw)
