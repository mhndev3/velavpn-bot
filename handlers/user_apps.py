"""
user_apps.py — بخش «دریافت برنامه‌ها» (اپ‌های V2Ray).

کاربر پلتفرمش را انتخاب می‌کند (اندروید/ویندوز/iOS/مک) و لیست اپ‌های آن پلتفرم
با دکمه‌های دانلود مستقیم نمایش داده می‌شود.

همه‌چیز از پنل ادمین قابل‌ویرایش است:
- متن‌ها و برچسب دکمه‌ها از طریق T() و کلیدهای SETTINGS_TREE
- خودِ لیست اپ‌ها و لینک‌ها در setting «apps_data» به‌صورت JSON ذخیره می‌شود
  و از هندلر head_admin مدیریت می‌شود (افزودن/حذف/ویرایش).
"""
import json

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database.db import get_setting, save_user
from handlers.btn_filter import Btn
from services.ui_texts import T

router = Router()


# پلتفرم‌ها: (کلید، برچسب پیش‌فرض)
PLATFORMS = [
    ("android", "🤖 اندروید"),
    ("windows", "🪟 ویندوز"),
    ("ios",     "🍎 آیفون (iOS)"),
    ("mac",     "💻 مک (macOS)"),
]

# دادهٔ پیش‌فرض اپ‌ها (اگر ادمین چیزی ذخیره نکرده باشد).
# هر آیتم: name نام اپ، url لینک دانلود
DEFAULT_APPS = {
    "android": [
        {"name": "v2rayNG", "url": "https://github.com/2dust/v2rayNG/releases"},
        {"name": "Hiddify", "url": "https://github.com/hiddify/hiddify-next/releases"},
        {"name": "NekoBox", "url": "https://github.com/MatsuriDayo/NekoBoxForAndroid/releases"},
    ],
    "windows": [
        {"name": "v2rayN", "url": "https://github.com/2dust/v2rayN/releases"},
        {"name": "Hiddify", "url": "https://github.com/hiddify/hiddify-next/releases"},
        {"name": "NekoRay", "url": "https://github.com/MatsuriDayo/nekoray/releases"},
    ],
    "ios": [
        {"name": "Streisand", "url": "https://apps.apple.com/app/streisand/id6450534064"},
        {"name": "Shadowrocket", "url": "https://apps.apple.com/app/shadowrocket/id932747118"},
        {"name": "V2Box", "url": "https://apps.apple.com/app/v2box-v2ray-client/id6446814690"},
    ],
    "mac": [
        {"name": "V2Box", "url": "https://apps.apple.com/app/v2box-v2ray-client/id6446814690"},
        {"name": "Hiddify", "url": "https://github.com/hiddify/hiddify-next/releases"},
    ],
}


def get_apps_data() -> dict:
    """دادهٔ اپ‌ها را از تنظیمات می‌خواند؛ اگر نبود، پیش‌فرض را برمی‌گرداند."""
    raw = get_setting("apps_data", "")
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return DEFAULT_APPS


def _platform_label(pkey: str, default: str) -> str:
    return T("apps_plat_" + pkey, default)


def _apps_home_kb() -> InlineKeyboardMarkup:
    rows = []
    for pkey, plabel in PLATFORMS:
        rows.append([InlineKeyboardButton(
            text=_platform_label(pkey, plabel),
            callback_data="apps:plat:" + pkey,
        )])
    rows.append([InlineKeyboardButton(text=T("apps_btn_back", "⬅️ بازگشت"), callback_data="u:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _apps_list_kb(pkey: str) -> InlineKeyboardMarkup:
    data = get_apps_data()
    apps = data.get(pkey, [])
    rows = []
    for app in apps:
        name = (app.get("name") or "").strip()
        url = (app.get("url") or "").strip()
        if name and url:
            rows.append([InlineKeyboardButton(text="⬇️ " + name, url=url)])
    rows.append([InlineKeyboardButton(text=T("apps_btn_back", "⬅️ بازگشت"), callback_data="apps:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def apps_entry(msg: Message):
    """ورود به بخش دریافت برنامه‌ها (از دکمهٔ منو)."""
    save_user(msg.from_user.id, msg.from_user.full_name, msg.from_user.username)
    text = T("apps_title", "📲 دریافت برنامه‌ها") + "\n\n" + \
        T("apps_hint", "سیستم‌عامل خود را انتخاب کنید تا برنامه‌های پیشنهادی برای اتصال را دریافت کنید:")
    kb = _apps_home_kb()
    sent = False
    try:
        from services.banner_service import send_banner
        sent = await send_banner(msg, "apps", caption=text, reply_markup=kb)
    except Exception:
        sent = False
    if not sent:
        await msg.answer(text, reply_markup=kb)


@router.message(Btn("btn_apps", "📲 دریافت برنامه‌ها"))
async def apps_entry_msg(msg: Message):
    await apps_entry(msg)


@router.callback_query(F.data == "apps:home")
async def apps_home_cb(cb: CallbackQuery):
    text = T("apps_title", "📲 دریافت برنامه‌ها") + "\n\n" + \
        T("apps_hint", "سیستم‌عامل خود را انتخاب کنید تا برنامه‌های پیشنهادی برای اتصال را دریافت کنید:")
    kb = _apps_home_kb()
    try:
        if cb.message.photo or cb.message.caption is not None:
            raise ValueError("photo")
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data.startswith("apps:plat:"))
async def apps_platform_cb(cb: CallbackQuery):
    pkey = cb.data.split(":", 2)[2]
    plabel = dict((k, v) for k, v in PLATFORMS).get(pkey, pkey)
    data = get_apps_data()
    apps = data.get(pkey, [])
    if not apps:
        await cb.answer(T("apps_empty", "فعلاً برنامه‌ای برای این سیستم‌عامل ثبت نشده."), show_alert=True)
        return
    header = T("apps_list_title", "📲 برنامه‌های پیشنهادی برای") + " " + _platform_label(pkey, plabel)
    hint = T("apps_list_hint", "روی هر برنامه بزنید تا به صفحهٔ دانلودش بروید:")
    text = header + "\n\n" + hint
    kb = _apps_list_kb(pkey)
    try:
        if cb.message.photo or cb.message.caption is not None:
            raise ValueError("photo")
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer()
