from pathlib import Path

from aiogram.types import FSInputFile


BASE_DIR = Path(__file__).resolve().parent.parent
BANNERS_DIR = BASE_DIR / "assets" / "banners"


BANNER_FILES = {
    "start_message": "main_menu.png",
    "shop": "shop.png",
    "pricing": "pricing.png",
    "channels_list": "guide.png",
    "support": "support.png",
    "faq": "faq.png",
    "referral": "referral.png",
    "profile": "profile.png",
    "tracking": "tracking.png",
    "payment": "payment.png",
    "v2ray": "v2ray.png",
    "l2tp": "l2tp.png",
    "openvpn": "openvpn.png",
    "starlink": "starlink.png",
}


def banner_path(key: str):
    filename = BANNER_FILES.get(key)
    if not filename:
        return None

    path = BANNERS_DIR / filename
    if not path.exists():
        return None

    return path


async def send_banner(message, key: str, caption: str = None, reply_markup=None):
    # اولویت با بنر آپلودشده توسط ادمین (file_id ذخیره‌شده در تنظیمات)
    try:
        from database.db import get_setting
        override = (get_setting("banner_" + key, "") or "").strip()
    except Exception:
        override = ""
    if override:
        try:
            await message.answer_photo(
                photo=override, caption=caption, reply_markup=reply_markup
            )
            return True
        except Exception:
            pass  # اگر file_id نامعتبر بود، برگرد به فایل استاتیک

    path = banner_path(key)
    if not path:
        return False

    await message.answer_photo(
        photo=FSInputFile(path),
        caption=caption,
        reply_markup=reply_markup
    )
    return True
