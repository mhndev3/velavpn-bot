"""
ui_texts.py — خواندن متن‌های سادهٔ قابل‌ویرایش سمت کاربر/ساب‌ادمین از تنظیمات.
T(key, default): اگر کلید در bot_settings ست نشده باشد، مقدار پیش‌فرض برمی‌گردد
(پس هرگز بات را نمی‌شکند). برای متن‌هایی که ایموجی پریمیوم/entity دارند از
services/ui_render.answer_ui استفاده کنید.
"""
from database.db import get_setting


def T(key: str, default: str = "") -> str:
    val = get_setting(key, default)
    if val is None or val == "":
        return default
    return val
