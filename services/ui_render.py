"""
ui_render.py — رندر متن‌های قابل‌ویرایش با پشتیبانی از ایموجی پریمیوم (custom emoji).

ایدهٔ کار:
- وقتی هد‌ادمین یک متن را (که ممکن است ایموجی پریمیوم داشته باشد) برای بات می‌فرستد،
  تلگرام کنار متن، entityها را هم می‌فرستد (شامل custom_emoji_id هر ایموجی پریمیوم).
- ما هم خودِ متن و هم این entityها را ذخیره می‌کنیم (به‌صورت JSON).
- موقع نمایش به کاربر، متن را با همان entityها می‌فرستیم → ایموجی پریمیوم انیمیشنی
  برای همهٔ کاربران دیده می‌شود (به‌شرط پریمیوم بودنِ اکانت بات).

اگر متنی entity نداشته باشد، مثل قبل با parse_mode=HTML فرستاده می‌شود (سازگاری کامل).
"""
import json
from aiogram.types import MessageEntity
from database.db import get_setting, set_setting


def save_ui_text(key: str, text: str, entities=None):
    """متن و entityهای آن (از پیام ادمین) را ذخیره می‌کند."""
    set_setting(key, text or "")
    if entities:
        data = []
        for e in entities:
            item = {"type": _etype(e.type), "offset": e.offset, "length": e.length}
            cid = getattr(e, "custom_emoji_id", None)
            if cid:
                item["custom_emoji_id"] = str(cid)
            url = getattr(e, "url", None)
            if url:
                item["url"] = url
            lang = getattr(e, "language", None)
            if lang:
                item["language"] = lang
            data.append(item)
        set_setting(key + "__ent", json.dumps(data, ensure_ascii=False))
    else:
        set_setting(key + "__ent", "")


def _etype(t):
    # نوع entity ممکن است enum یا رشته باشد
    return getattr(t, "value", None) or str(t)


def get_ui_text(key: str, default: str = "") -> str:
    v = get_setting(key, default)
    return v if (v is not None and v != "") else default


def get_ui_entities(key: str):
    raw = get_setting(key + "__ent", "")
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    ents = []
    for d in data:
        try:
            kwargs = {"type": d["type"], "offset": int(d["offset"]), "length": int(d["length"])}
            if d.get("custom_emoji_id"):
                kwargs["custom_emoji_id"] = str(d["custom_emoji_id"])
            if d.get("url"):
                kwargs["url"] = d["url"]
            if d.get("language"):
                kwargs["language"] = d["language"]
            ents.append(MessageEntity(**kwargs))
        except Exception:
            continue
    return ents or None


async def answer_ui(message, key: str, default: str = "", reply_markup=None, **kwargs):
    """متن قابل‌ویرایش را با ایموجی پریمیوم/فرمت ذخیره‌شده می‌فرستد."""
    text = get_ui_text(key, default)
    ents = get_ui_entities(key)
    if ents:
        return await message.answer(text, entities=ents, parse_mode=None,
                                    reply_markup=reply_markup, **kwargs)
    return await message.answer(text, reply_markup=reply_markup, **kwargs)


async def answer_photo_ui(message, photo, key: str, default: str = "", reply_markup=None, **kwargs):
    """عکس + کپشنِ قابل‌ویرایش با ایموجی پریمیوم."""
    caption = get_ui_text(key, default)
    ents = get_ui_entities(key)
    if ents:
        return await message.answer_photo(photo, caption=caption, caption_entities=ents,
                                          parse_mode=None, reply_markup=reply_markup, **kwargs)
    return await message.answer_photo(photo, caption=caption, reply_markup=reply_markup, **kwargs)
