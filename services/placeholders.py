"""
placeholders.py — تبدیل تاریخ میلادی به شمسی (بدون کتابخانهٔ خارجی) و
جایگزینی placeholderها در متن‌های قابل‌ویرایش.

placeholderهای پشتیبانی‌شده:
  {id}        → آیدی عددی تلگرام کاربر
  {name}      → نام کامل کاربر
  {username}  → یوزرنیم (@...) یا رشتهٔ خالی
  {date}      → تاریخ شمسی امروز (مثلاً ۱۴۰۴/۰۴/۲۱)
  {time}      → ساعت (مثلاً ۱۴:۳۰)
  {datetime}  → تاریخ شمسی + ساعت
"""
from datetime import datetime, timezone, timedelta

# منطقهٔ زمانی ایران (UTC+3:30)
_IRAN_TZ = timezone(timedelta(hours=3, minutes=30))

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _to_fa_digits(s: str) -> str:
    return str(s).translate(_FA_DIGITS)


def gregorian_to_jalali(gy: int, gm: int, gd: int):
    """تبدیل تاریخ میلادی به شمسی (الگوریتم استاندارد، بدون وابستگی)."""
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621
    gy2 = gy + 1 if gm > 2 else gy
    days = (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) \
        + ((gy2 + 399) // 400) - 80 + gd + g_d_m[gm - 1]
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd


def now_jalali_parts():
    now = datetime.now(_IRAN_TZ)
    jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)
    return jy, jm, jd, now.hour, now.minute


def jalali_date_str() -> str:
    jy, jm, jd, _, _ = now_jalali_parts()
    return _to_fa_digits(f"{jy:04d}/{jm:02d}/{jd:02d}")


def jalali_time_str() -> str:
    _, _, _, hh, mm = now_jalali_parts()
    return _to_fa_digits(f"{hh:02d}:{mm:02d}")


def jalali_datetime_str() -> str:
    return f"{jalali_date_str()} - {jalali_time_str()}"


def apply_placeholders(text: str, user=None) -> str:
    """placeholderهای متن را با مقادیر واقعی جایگزین می‌کند."""
    if not text:
        return text
    uid = ""
    name = ""
    username = ""
    if user is not None:
        uid = str(getattr(user, "id", "") or "")
        name = getattr(user, "full_name", "") or ""
        un = getattr(user, "username", "") or ""
        username = ("@" + un) if un else ""
    repl = {
        "{id}": _to_fa_digits(uid),
        "{id_en}": uid,
        "{name}": name,
        "{username}": username,
        "{date}": jalali_date_str(),
        "{time}": jalali_time_str(),
        "{datetime}": jalali_datetime_str(),
    }
    out = text
    for k, v in repl.items():
        out = out.replace(k, v)
    return out
