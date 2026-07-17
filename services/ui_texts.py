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


class _SafeDict(dict):
    """جای placeholder ناشناخته را دست‌نخورده می‌گذارد تا format خطا ندهد."""
    def __missing__(self, k):
        return "{" + k + "}"


def TF(key: str, default: str = "", **kw) -> str:
    """
    مثل T ولی برای قالب‌های دارای placeholder مثل {price} یا {name}.
    اگر ادمین متن را طوری ویرایش کند که قالب خراب شود، به‌جای کرش،
    پیش‌فرض استفاده می‌شود (بات هرگز نمی‌شکند).
    """
    tpl = T(key, default)
    try:
        return tpl.format_map(_SafeDict(**kw))
    except Exception:
        try:
            return default.format_map(_SafeDict(**kw))
        except Exception:
            return default
