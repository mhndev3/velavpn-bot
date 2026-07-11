"""
تنظیمات UI کامل — هد ادمین می‌تونه همه متن‌ها، بنرها، دکمه‌ها رو تغییر بده
+ پنهان کردن دکمه‌ها
"""
from aiogram import Router, F
from aiogram.types import (
    CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from pathlib import Path

from config.settings import ADMIN_IDS
from database.db import get_setting, set_setting

router = Router()


class UIState(StatesGroup):
    edit_value = State()


def _btn(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


SETTINGS_TREE = {
    "buttons": {
        "label": "🔘 متن دکمه‌ها",
        "items": {
            "btn_buy":      ("⚡ خرید کانفیگ",      "⚡ خرید کانفیگ"),
            "btn_profile":  ("👤 پنل کاربری",        "👤 پنل کاربری"),
            "btn_wallet":   ("💳 کیف پول",           "💳 کیف پول"),
            "btn_subs":     ("📦 اشتراک‌های من",     "📦 اشتراک‌های من"),
            "btn_support":  ("🛟 پشتیبانی",          "🛟 پشتیبانی"),
            "btn_faq":      ("❓ سوالات متداول",      "❓ سوالات متداول"),
            "btn_coop":     ("🤝 درخواست همکاری",     "🤝 درخواست همکاری"),
            "btn_guide":    ("📘 راهنمای اتصال",     "📘 راهنمای اتصال"),
            "btn_cfg_update": ("🔄 دریافت کانفیگ آپدیت‌شده", "🔄 دریافت کانفیگ آپدیت‌شده"),
            "btn_addcfg":   ("➕ افزودن کانفیگ من",    "➕ افزودن کانفیگ من"),
            "btn_admin":    ("👑 پنل مدیریت",        "👑 پنل مدیریت"),
            "btn_sa_stats": ("📊 آمار فروش من",      "📊 آمار فروش من"),
        },
    },
    "texts": {
        "label": "📝 متن‌های صفحات",
        "items": {
            "txt_welcome":   ("متن خوشامد",        "🎉 خوش آمدید!"),
            "txt_menu":      ("عنوان منو",          "📱 منوی اصلی:"),
            "txt_support":   ("متن پشتیبانی",       "🛟 برای کمک تیکت ثبت کنید."),
            "txt_guide":     ("متن راهنما",         "📘 راهنمای اتصال به VPN"),
            "txt_card_info": ("شماره کارت",         "شماره کارت تنظیم نشده"),
        },
    },
    "banners": {
        "label": "🎨 بنرها",
        "items": {
            "banner_start_message": ("بنر منوی اصلی", ""),
            "banner_shop":          ("بنر فروشگاه",   ""),
            "banner_pricing":       ("بنر تعرفه",     ""),
            "banner_payment":       ("بنر پرداخت",    ""),
            "banner_support":       ("بنر پشتیبانی",  ""),
            "banner_faq":           ("بنر سوالات",    ""),
            "banner_subs":          ("بنر کانفیگ‌های من", ""),
            "banner_profile":       ("بنر پنل کاربری", ""),
        },
    },
    "emojis": {
        "label": "😀 ایموجی‌ها",
        "items": {
            "emoji_success": ("موفقیت", "✅"),
            "emoji_error":   ("خطا",    "❌"),
            "emoji_wait":    ("انتظار", "⏳"),
            "emoji_money":   ("پول",    "💰"),
            "emoji_star":    ("ستاره",  "⭐"),
            "emoji_box":     ("باکس پلن", "📦"),
        },
    },
    "onboarding": {
        "label": "🚪 ثبت‌نام (کانال/قوانین/شماره/نام)",
        "items": {
            "onb_join_text":     ("متن عضویت کانال", "🔒 برای استفاده از ربات، ابتدا باید در کانال‌های ما عضو شوید.\n\nپس از عضویت در همهٔ کانال‌ها، روی «عضو شدم» بزنید."),
            "onb_join_btn":      ("دکمهٔ عضو شدم", "✅ عضو شدم"),
            "onb_notjoined":     ("هشدار عضو نشدن", "❌ هنوز در همهٔ کانال‌ها عضو نشده‌اید."),
            "onb_rules_text":    ("متن قوانین", "📜 قوانین استفاده از خدمات ما\n\n۱- به اطلاعیه‌هایی که داخل کانال گذاشته می‌شود حتماً توجه کنید.\n۲- در صورتی که اطلاعیه‌ای در مورد قطعی در کانال گذاشته نشده به اکانت پشتیبانی پیام دهید.\n۳- سرویس‌ها را از طریق پیامک ارسال نکنید؛ برای ارسال می‌توانید از طریق ایمیل ارسال کنید."),
            "onb_rules_btn":     ("دکمهٔ پذیرش قوانین", "✅ قوانین را می‌پذیرم"),
            "onb_phone_text":    ("متن درخواست شماره", "📱 شماره موبایل خود را با دکمهٔ زیر به اشتراک بگذارید تا ثبت‌نام شما تأیید شود و بتوانید از ربات استفاده کنید."),
            "onb_phone_btn":     ("دکمهٔ ارسال شماره", "📱 ارسال شماره تلفن"),
            "onb_username_text": ("متن درخواست نام کاربری", "👤 لطفاً یک نام کاربری برای حساب خود انتخاب کنید و ارسال کنید."),
            "onb_done_text":     ("متن پایان ثبت‌نام", "✅ ثبت‌نام شما کامل شد! خوش آمدید."),
        },
    },
    "profile": {
        "label": "👤 پنل کاربری",
        "items": {
            "profile_title":         ("عنوان پروفایل", "👤 پنل کاربری"),
            "profile_lbl_username":  ("برچسب نام کاربری", "🏷 نام کاربری:"),
            "profile_lbl_id":        ("برچسب آیدی عددی", "🆔 آیدی عددی:"),
            "profile_lbl_phone":     ("برچسب شماره تلفن", "📱 شماره تلفن:"),
            "profile_lbl_purchases": ("برچسب تعداد خریدها", "🛒 تعداد خریدها:"),
            "profile_footer":        ("متن پایین پروفایل (اختیاری)", ""),
            "profile_btn_back":      ("دکمهٔ بازگشت", "⬅️ بازگشت"),
        },
    },
    "subs": {
        "label": "📦 کانفیگ‌های من",
        "items": {
            "subs_title":        ("عنوان لیست", "📦 اشتراک‌های فعال شما"),
            "subs_hint":         ("راهنمای زیر لیست", "برای مشاهده جزئیات، حجم و کانفیگ، انتخاب کنید:"),
            "subs_empty":        ("متن نداشتن اشتراک", "📦 شما هنوز اشتراک فعالی ندارید.\n\nبرای خرید گزینه «⚡ خرید کانفیگ» را بزنید."),
            "subs_lbl_name":     ("برچسب نام سرویس", "🏷 نام سرویس:"),
            "subs_lbl_service":  ("برچسب سرویس (حجم)", "📦 سرویس:"),
            "subs_lbl_plan":     ("برچسب پلن (مدت)", "💠 پلن:"),
            "subs_lbl_location": ("برچسب لوکیشن", "🌍 لوکیشن:"),
            "subs_lbl_remain":   ("برچسب زمان باقی مونده", "📅 زمان باقی مونده:"),
            "subs_lbl_gb":       ("برچسب باقی مانده حجم", "📥 باقی مانده حجم:"),
            "subs_lbl_percent":  ("برچسب درصد مصرف شده", "📊 درصد مصرف شده:"),
            "subs_lbl_link":     ("برچسب لینک کانفیگ", "🔗 لینک کانفیگ:"),
            "subs_emoji_item":   ("ایموجی دکمه‌های لیست", "📦"),
            "subs_btn_qr":       ("دکمهٔ دریافت QR", "📱 دریافت QR Code"),
            "subs_btn_file":     ("دکمهٔ دریافت فایل", "📎 دریافت مجدد فایل کانفیگ"),
            "subs_btn_refresh":  ("دکمهٔ بروزرسانی", "🔄 بروزرسانی وضعیت"),
            "subs_btn_back":     ("دکمهٔ بازگشت", "⬅️ بازگشت"),
        },
    },
}

HIDEABLE_BUTTONS = ["btn_wallet", "btn_support", "btn_faq",
                    "btn_coop", "btn_guide", "btn_cfg_update", "btn_addcfg"]

# نگاشت متن‌های UI به منبعی که ربات واقعاً از آن می‌خواند (content_pages)
TXT_TO_CONTENT = {
    "txt_welcome": "start_message",
    "txt_support": "support",
    "txt_guide":   "channels_list",
}
# متنی که به تنظیمِ واقعیِ دیگری می‌رود
TXT_TO_SETTING = {
    "txt_card_info": "card_info",
}


def get_ui(key: str) -> str:
    for cat in SETTINGS_TREE.values():
        if key in cat["items"]:
            return get_setting(key, cat["items"][key][1])
    return get_setting(key, "")


def is_hidden(key: str) -> bool:
    return get_setting(f"hide_{key}", "") == "1"


def ui_home_kb():
    rows = [[_btn(cat["label"], f"ui:cat:{k}")] for k, cat in SETTINGS_TREE.items()]
    rows.append([_btn("🎨 رنگ دکمه‌ها", "ui:colors")])
    rows.append([_btn("↕️ چیدمان دکمه‌ها", "ui:order")])
    rows.append([_btn("🙈 پنهان کردن دکمه‌ها", "ui:hide_menu")])
    rows.append([_btn("💾 دانلود دیتابیس", "ui:download_db")])
    rows.append([_btn("🔄 بازنشانی همه", "ui:reset_all")])
    rows.append([_btn("⬅️ بازگشت", "ha:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# رنگ دکمه‌ها (Bot API 9.4+): تلگرام فقط این ۴ حالت را دارد
COLOR_CHOICES = [
    ("", "⚪️ پیش‌فرض"),
    ("primary", "🔵 آبی"),
    ("success", "🟢 سبز"),
    ("danger", "🔴 قرمز"),
]
COLOR_NAME = {"": "پیش‌فرض", "primary": "🔵 آبی", "success": "🟢 سبز", "danger": "🔴 قرمز"}
COLORABLE_BUTTONS = ["btn_buy", "btn_profile", "btn_wallet", "btn_subs", "btn_support", "btn_faq",
                     "btn_coop", "btn_guide", "btn_cfg_update", "btn_addcfg",
                     "btn_admin", "btn_sa_stats", "btn_referral"]
_BTN_LABELS = {
    "btn_buy": "⚡ خرید کانفیگ", "btn_profile": "👤 پنل کاربری",
    "btn_wallet": "💳 کیف پول", "btn_subs": "📦 اشتراک‌های من",
    "btn_support": "🛟 پشتیبانی", "btn_faq": "❓ سوالات متداول", "btn_coop": "🤝 درخواست همکاری",
    "btn_guide": "📘 راهنمای اتصال", "btn_cfg_update": "🔄 دریافت کانفیگ آپدیت‌شده",
    "btn_addcfg": "➕ افزودن کانفیگ من", "btn_admin": "👑 پنل مدیریت",
    "btn_sa_stats": "📊 آمار فروش من", "btn_referral": "🎁 دعوت دوستان",
}


def ui_colors_kb():
    rows = []
    for key in COLORABLE_BUTTONS:
        cur = get_setting("btncolor_" + key, "")
        badge = {"": "⚪️", "primary": "🔵", "success": "🟢", "danger": "🔴"}.get(cur, "⚪️")
        rows.append([_btn(f"{badge} {_BTN_LABELS.get(key, key)}", f"ui:colorbtn:{key}")])
    rows.append([_btn("⬅️ بازگشت", "ui:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ui_colorbtn_kb(key):
    rows = []
    cur = get_setting("btncolor_" + key, "")
    for val, label in COLOR_CHOICES:
        mark = " ✅" if val == cur else ""
        rows.append([_btn(label + mark, f"ui:setcolor:{key}:{val or 'default'}")])
    rows.append([_btn("⬅️ بازگشت", "ui:colors")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ui_cat_kb(cat_key: str):
    cat = SETTINGS_TREE.get(cat_key, {})
    rows = []
    for key, (label, default) in cat.get("items", {}).items():
        cur = get_setting(key, default)
        short = cur[:25] + "…" if len(cur) > 25 else cur
        rows.append([_btn(f"{label}: {short}", f"ui:edit:{cat_key}:{key}")])
    rows.append([_btn("⬅️ بازگشت", "ui:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ui_hide_menu_kb():
    rows = []
    for key in HIDEABLE_BUTTONS:
        items = SETTINGS_TREE["buttons"]["items"]
        label = items[key][0] if key in items else key
        hidden = is_hidden(key)
        ico = "🙈" if hidden else "👁"
        rows.append([_btn(f"{ico} {label}", f"ui:toggle_hide:{key}")])
    rows.append([_btn("⬅️ بازگشت", "ui:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── Handlers ────────────────────────────────────────────────
@router.callback_query(F.data == "ui:home")
async def ui_home_cb(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("دسترسی ندارید", show_alert=True)
    await cb.message.edit_text(
        "🎨 تنظیمات UI/UX\n\nمتن‌ها، بنرها، دکمه‌ها و ایموجی‌ها:",
        reply_markup=ui_home_kb()
    )
    await cb.answer()


@router.callback_query(F.data.startswith("ui:cat:"))
async def ui_cat_cb(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    cat_key = cb.data.split(":")[2]
    cat = SETTINGS_TREE.get(cat_key)
    if not cat:
        return await cb.answer("دسته پیدا نشد", show_alert=True)
    await cb.message.edit_text(
        f"{cat['label']}\n\nگزینه رو انتخاب کن:",
        reply_markup=ui_cat_kb(cat_key)
    )
    await cb.answer()


@router.callback_query(F.data.startswith("ui:edit:"))
async def ui_edit_cb(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    parts = cb.data.split(":")
    cat_key, key = parts[2], parts[3]
    cat = SETTINGS_TREE.get(cat_key, {})
    label, default = cat.get("items", {}).get(key, (key, ""))
    current = get_setting(key, default)
    await state.update_data(ui_key=key, ui_cat=cat_key, ui_default=default)
    if cat_key == "banners":
        await cb.message.edit_text(
            f"🎨 {label}\n\n"
            f"یک «عکس» بفرست تا به‌عنوان این بنر تنظیم شود.\n"
            f"(برای حذف بنر و بازگشت به حالت پیش‌فرض: <code>reset</code>)"
        )
    else:
        await cb.message.edit_text(
            f"✏️ {label}\n\n"
            f"مقدار فعلی:\n<code>{current}</code>\n\n"
            f"مقدار جدید بفرست\n"
            f"(برای بازنشانی: <code>reset</code>)"
        )
    await state.set_state(UIState.edit_value)
    await cb.answer()


@router.message(UIState.edit_value)
async def ui_save_cb(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    key = data.get("ui_key")
    default = data.get("ui_default", "")
    cat_key = data.get("ui_cat", "")
    is_banner = cat_key == "banners" or (key or "").startswith("banner_")

    back_kb = InlineKeyboardMarkup(inline_keyboard=[[_btn("⬅️ بازگشت", f"ui:cat:{cat_key}")]])

    # ── بنر: عکس بگیر و file_id ذخیره کن ──
    if is_banner:
        if msg.photo:
            file_id = msg.photo[-1].file_id
            set_setting(key, file_id)
            await state.clear()
            return await msg.answer("✅ بنر ذخیره و اعمال شد.", reply_markup=back_kb)
        txt = (msg.text or "").strip().lower()
        if txt == "reset":
            set_setting(key, "")
            await state.clear()
            return await msg.answer("✅ بنر حذف شد (بازگشت به پیش‌فرض).", reply_markup=back_kb)
        # نه عکس نه reset → دوباره بخواه، state را نگه دار
        return await msg.answer("📷 لطفاً یک «عکس» بفرست، یا برای حذف بنر بنویس: reset")

    # ── متن/دکمه/ایموجی ──
    raw_text = msg.text or ""
    text = raw_text.strip()
    if not text:
        return await msg.answer("لطفاً یک «متن» بفرست (یا برای بازنشانی بنویس: reset).")
    await state.clear()
    from services.ui_render import save_ui_text
    if text.lower() == "reset":
        value = default
        save_ui_text(key, value, None)  # هم متن هم entityها پاک/پیش‌فرض می‌شوند
    else:
        # متنِ خام را نگه می‌داریم تا offsetهای entity (ایموجی پریمیوم) درست بمانند
        value = raw_text
        save_ui_text(key, value, msg.entities)

    # اعمال واقعی متن روی منبعی که ربات از آن می‌خواند
    applied_note = ""
    try:
        if key in TXT_TO_CONTENT:
            from services.content_media_service import get_content_page, update_content_page
            ckey = TXT_TO_CONTENT[key]
            page = get_content_page(ckey) or {}
            update_content_page(
                ckey,
                page.get("title") or key,
                value,
                page.get("file_id"),
                page.get("file_type"),
            )
            applied_note = "\n(روی متن واقعی ربات اعمال شد ✅)"
        elif key in TXT_TO_SETTING:
            set_setting(TXT_TO_SETTING[key], value)
            applied_note = "\n(اعمال شد ✅)"
    except Exception:
        pass

    await msg.answer(
        f"✅ ذخیره شد:\n<code>{value}</code>{applied_note}",
        reply_markup=back_kb,
    )


@router.callback_query(F.data == "ui:hide_menu")
async def ui_hide_menu_cb(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    await cb.message.edit_text(
        "🙈 پنهان/نمایش دکمه‌ها\n\n"
        "🙈 = پنهان  👁 = نمایش\n\n"
        "روی هر دکمه کلیک کن تا وضعیتش تغییر کنه:",
        reply_markup=ui_hide_menu_kb()
    )
    await cb.answer()


@router.callback_query(F.data.startswith("ui:toggle_hide:"))
async def ui_toggle_hide(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    key = cb.data.split(":")[2]
    current = get_setting(f"hide_{key}", "")
    new_val = "0" if current == "1" else "1"
    set_setting(f"hide_{key}", new_val)
    status = "پنهان شد 🙈" if new_val == "1" else "نمایش داده می‌شه 👁"
    await cb.answer(status, show_alert=True)
    await cb.message.edit_reply_markup(reply_markup=ui_hide_menu_kb())


@router.callback_query(F.data == "ui:colors")
async def ui_colors_cb(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    await cb.message.edit_text(
        "🎨 رنگ دکمه‌ها\n\n"
        "تلگرام ۴ حالت دارد: ⚪️ پیش‌فرض / 🔵 آبی / 🟢 سبز / 🔴 قرمز.\n"
        "دکمه‌ای که می‌خواهی رنگش را عوض کنی انتخاب کن:",
        reply_markup=ui_colors_kb()
    )
    await cb.answer()


@router.callback_query(F.data.startswith("ui:colorbtn:"))
async def ui_colorbtn_cb(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    key = cb.data.split(":")[2]
    await cb.message.edit_text(
        f"🎨 رنگ دکمهٔ «{_BTN_LABELS.get(key, key)}»\n\n"
        "رنگ را انتخاب کن (بدون ری‌استارت اعمال می‌شود؛ دفعهٔ بعد که منو باز شود رنگ جدید دیده می‌شود):",
        reply_markup=ui_colorbtn_kb(key)
    )
    await cb.answer()


@router.callback_query(F.data.startswith("ui:setcolor:"))
async def ui_setcolor_cb(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    parts = cb.data.split(":")
    key, val = parts[2], parts[3]
    color = "" if val == "default" else val
    set_setting("btncolor_" + key, color)
    await cb.answer("✅ رنگ اعمال شد: " + COLOR_NAME.get(color, "پیش‌فرض"))
    await cb.message.edit_reply_markup(reply_markup=ui_colorbtn_kb(key))


@router.callback_query(F.data == "ui:reset_all")
async def ui_reset_all_cb(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    for cat in SETTINGS_TREE.values():
        for key, (_, default) in cat["items"].items():
            set_setting(key, default)
    for key in HIDEABLE_BUTTONS:
        set_setting(f"hide_{key}", "0")
    for key in COLORABLE_BUTTONS:
        set_setting("btncolor_" + key, "")
    await cb.answer("✅ همه تنظیمات به پیش‌فرض برگشت", show_alert=True)
    await cb.message.edit_text("🎨 تنظیمات UI\n\n✅ بازنشانی کامل شد:", reply_markup=ui_home_kb())


@router.callback_query(F.data == "ui:download_db")
async def ui_download_db_cb(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("دسترسی ندارید", show_alert=True)
    db_path = Path(__file__).resolve().parent.parent / "bot.db"
    if not db_path.exists():
        return await cb.answer("فایل دیتابیس پیدا نشد", show_alert=True)
    await cb.answer("⏳ در حال ارسال...", show_alert=False)
    from datetime import datetime
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    await cb.bot.send_document(
        chat_id=cb.from_user.id,
        document=FSInputFile(str(db_path), filename=f"backup_{stamp}.db"),
        caption=f"💾 بکاپ دیتابیس\n📅 {stamp}"
    )


# ─── چیدمان دکمه‌ها (ردیف‌محور: بالا/پایین + چپ/راست + ادغام/جدا) ───
_ORDER_TITLE = (
    "🎨 چیدمان دکمه‌های منو\n"
    "━━━━━━━━━━━━━━\n\n"
    "هر ردیف با شماره مشخص شده. زیر هر دکمه، "
    "دکمه‌های آبی برای جابه‌جایی همان دکمه هستند:\n\n"
    "⬆️ = یک ردیف بالاتر برود\n"
    "⬇️ = یک ردیف پایین‌تر برود\n"
    "⬅️ ➡️ = چپ و راست در همان ردیف\n"
    "➕ کنار = بغلِ دکمهٔ بعدی بچسبد\n"
    "✂️ تنها = از بغلی‌اش جدا شود\n\n"
    "🔒 «خرید کانفیگ» همیشه اولِ منوست.\n"
    "✅ هر تغییر، همان لحظه روی منوی کاربر اعمال می‌شود."
)


def _row_label(key):
    from keyboards.user_keyboards import DEFAULT_MENU_ORDER
    lbl = get_ui(key) or _BTN_LABELS.get(key, key)
    if len(lbl) > 18:
        lbl = lbl[:18] + "…"
    return lbl


def ui_order_kb():
    """صفحهٔ چیدمان — طرح واضح: هر دکمه در یک خط، کنترل‌ها زیرش با برچسب."""
    from keyboards.user_keyboards import get_menu_layout, MAX_PER_ROW
    layout = get_menu_layout()
    rows = []
    nrows = len(layout)

    # شماره‌های فارسی ردیف
    circ = ["1\u20e3", "2\u20e3", "3\u20e3", "4\u20e3", "5\u20e3",
            "6\u20e3", "7\u20e3", "8\u20e3", "9\u20e3", "\U0001f51f"]

    for ri, row in enumerate(layout):
        num = circ[ri] if ri < len(circ) else f"({ri+1})"
        # سرِ ردیف: شماره + نام دکمه‌های داخل این ردیف
        names = "  +  ".join(_row_label(k) for k in row)
        rows.append([_btn(f"{num}  {names}", "uiord:noop")])

        # برای هر دکمهٔ داخل ردیف، یک خط کنترلِ برچسب‌دار
        for ci, key in enumerate(row):
            short = _row_label(key)
            multi = len(row) > 1

            move = []
            if ri > 0:
                move.append(_btn("⬆️ بالا", f"uiord:up:{key}"))
            if ri < nrows - 1:
                move.append(_btn("⬇️ پایین", f"uiord:down:{key}"))
            if move:
                if multi:
                    rows.append([_btn("👉 " + short, "uiord:noop"), *move])
                else:
                    rows.append(move)

            side = []
            if multi and ci > 0:
                side.append(_btn("⬅️ چپ", f"uiord:left:{key}"))
            if multi and ci < len(row) - 1:
                side.append(_btn("➡️ راست", f"uiord:right:{key}"))
            if multi:
                side.append(_btn("✂️ جدا کن", f"uiord:split:{key}"))
            elif ri < nrows - 1 and len(layout[ri + 1]) < MAX_PER_ROW:
                side.append(_btn("➕ بچسبان به بعدی", f"uiord:merge:{key}"))
            if side:
                rows.append(side)

        # جداکنندهٔ بین ردیف‌ها
        if ri < nrows - 1:
            rows.append([_btn("┈┈┈┈┈┈┈┈┈┈", "uiord:noop")])

    rows.append([_btn("🔄 بازگشت به چیدمان پیش‌فرض", "uiord:reset")])
    rows.append([_btn("⬅️ بازگشت به تنظیمات", "ui:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _rerender_order(cb, toast=None):
    try:
        await cb.message.edit_text(_ORDER_TITLE, reply_markup=ui_order_kb())
    except Exception:
        pass
    await cb.answer(toast or "")


def _find(layout, key):
    for ri, row in enumerate(layout):
        if key in row:
            return ri, row.index(key)
    return None, None


@router.callback_query(F.data == "ui:order")
async def ui_order_cb(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    await cb.message.edit_text(_ORDER_TITLE, reply_markup=ui_order_kb())
    await cb.answer()


@router.callback_query(F.data == "uiord:noop")
async def ui_order_noop(cb: CallbackQuery):
    await cb.answer()


@router.callback_query(F.data.startswith("uiord:up:"))
async def ui_order_up(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    from keyboards.user_keyboards import get_menu_layout, save_menu_layout
    key = cb.data.split(":", 2)[2]
    layout = get_menu_layout()
    ri, ci = _find(layout, key)
    if ri is not None and ri > 0:
        layout[ri - 1], layout[ri] = layout[ri], layout[ri - 1]
        save_menu_layout(layout)
    await _rerender_order(cb, "⬆️ ردیف بالا رفت")


@router.callback_query(F.data.startswith("uiord:down:"))
async def ui_order_down(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    from keyboards.user_keyboards import get_menu_layout, save_menu_layout
    key = cb.data.split(":", 2)[2]
    layout = get_menu_layout()
    ri, ci = _find(layout, key)
    if ri is not None and ri < len(layout) - 1:
        layout[ri + 1], layout[ri] = layout[ri], layout[ri + 1]
        save_menu_layout(layout)
    await _rerender_order(cb, "⬇️ ردیف پایین رفت")


@router.callback_query(F.data.startswith("uiord:left:"))
async def ui_order_left(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    from keyboards.user_keyboards import get_menu_layout, save_menu_layout
    key = cb.data.split(":", 2)[2]
    layout = get_menu_layout()
    ri, ci = _find(layout, key)
    if ri is not None and ci > 0:
        layout[ri][ci - 1], layout[ri][ci] = layout[ri][ci], layout[ri][ci - 1]
        save_menu_layout(layout)
    await _rerender_order(cb, "◀️ جابه‌جا شد")


@router.callback_query(F.data.startswith("uiord:right:"))
async def ui_order_right(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    from keyboards.user_keyboards import get_menu_layout, save_menu_layout
    key = cb.data.split(":", 2)[2]
    layout = get_menu_layout()
    ri, ci = _find(layout, key)
    if ri is not None and ci < len(layout[ri]) - 1:
        layout[ri][ci + 1], layout[ri][ci] = layout[ri][ci], layout[ri][ci + 1]
        save_menu_layout(layout)
    await _rerender_order(cb, "▶️ جابه‌جا شد")


@router.callback_query(F.data.startswith("uiord:merge:"))
async def ui_order_merge(cb: CallbackQuery):
    """این دکمه (که تنها در ردیف خودش است) با ردیف بعد هم‌ردیف می‌شود."""
    if cb.from_user.id not in ADMIN_IDS:
        return
    from keyboards.user_keyboards import get_menu_layout, save_menu_layout, MAX_PER_ROW
    key = cb.data.split(":", 2)[2]
    layout = get_menu_layout()
    ri, ci = _find(layout, key)
    if ri is not None and ri < len(layout) - 1 and len(layout[ri + 1]) < MAX_PER_ROW:
        # دکمه را از ردیف خودش بردار و ابتدای ردیف بعد بگذار
        layout[ri].remove(key)
        layout[ri + 1].insert(0, key)
        layout = [r for r in layout if r]
        save_menu_layout(layout)
    await _rerender_order(cb, "🔗 هم‌ردیف شد")


@router.callback_query(F.data.startswith("uiord:split:"))
async def ui_order_split(cb: CallbackQuery):
    """این دکمه از ردیفِ مشترک جدا و به ردیف تازهٔ خودش می‌رود."""
    if cb.from_user.id not in ADMIN_IDS:
        return
    from keyboards.user_keyboards import get_menu_layout, save_menu_layout
    key = cb.data.split(":", 2)[2]
    layout = get_menu_layout()
    ri, ci = _find(layout, key)
    if ri is not None and len(layout[ri]) > 1:
        layout[ri].remove(key)
        layout.insert(ri + 1, [key])
        save_menu_layout(layout)
    await _rerender_order(cb, "✂️ جدا شد")


@router.callback_query(F.data == "uiord:reset")
async def ui_order_reset(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    set_setting("menu_layout", "")
    await _rerender_order(cb, "🔄 چیدمان پیش‌فرض شد")
