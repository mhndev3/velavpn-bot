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
            "btn_renew":    ("♻️ تمدید اشتراک",      "♻️ تمدید اشتراک"),
            "btn_test":     ("🎁 دریافت اکانت تست",   "🎁 دریافت اکانت تست"),
            "btn_apps":     ("📲 دریافت برنامه‌ها",   "📲 دریافت برنامه‌ها"),
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
            "banner_apps":          ("بنر دریافت برنامه‌ها", ""),
            "banner_renew":         ("بنر تمدید اشتراک", ""),
            "banner_test":          ("بنر اکانت تست", ""),
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
            "subs_btn_delete":   ("دکمهٔ حذف کانفیگ", "🗑 حذف این کانفیگ"),
            "subs_del_confirm":  ("متن تأیید حذف", "⚠️ آیا مطمئنید می‌خواهید این کانفیگ را حذف کنید؟\nاین عمل قابل بازگشت نیست و کانفیگ از سرور هم پاک می‌شود."),
            "subs_del_yes":      ("دکمهٔ تأیید حذف", "✅ بله، حذف کن"),
            "subs_del_no":       ("دکمهٔ انصراف حذف", "❌ انصراف"),
            "subs_del_done":     ("پیام حذف موفق", "🗑 کانفیگ با موفقیت حذف شد."),
            "subs_list_title":   ("عنوان لیست — {title}{count}{hint}", "{title} ({count} مورد):\n\n{hint}"),
            "subs_item_fallback": ("نام جایگزین اشتراک", "اشتراک"),
            "subs_loading":      ("پیام در حال دریافت", "⏳ در حال دریافت اطلاعات..."),
            "subs_not_found":    ("خطای اشتراک پیدا نشد", "اشتراک پیدا نشد"),
            "subs_deleting":     ("پیام در حال حذف", "⏳ در حال حذف..."),
            "subs_file_note":    ("یادداشت کانفیگ فایلی", "📎 کانفیگ به‌صورت فایل ارسال شده — دکمه زیر را بزنید."),
            "subs_no_link":      ("خطای بدون لینک", "لینک کانفیگ موجود نیست"),
            "subs_qr_making":    ("پیام ساخت QR", "⏳ در حال ساخت QR..."),
            "subs_qr_caption":   ("کپشن QR — {order_id}", "📱 اشتراک #{order_id}"),
            "subs_link_only":    ("نمایش لینک بدون QR — {link}", "📱 لینک کانفیگ:\n\n<code>{link}</code>"),
            "subs_no_file":      ("خطای بدون فایل", "فایلی برای این اشتراک موجود نیست"),
            "subs_file_caption": ("کپشن فایل کانفیگ", "📎 کانفیگ شما"),
            "subs_file_failed":  ("خطای ارسال فایل", "❌ ارسال فایل ناموفق بود."),
            "subs_btn_back":     ("دکمهٔ بازگشت", "⬅️ بازگشت"),
        },
    },
    "apps": {
        "label": "📲 دریافت برنامه‌ها",
        "items": {
            "apps_title":        ("عنوان صفحه", "📲 دریافت برنامه‌ها"),
            "apps_hint":         ("راهنمای انتخاب سیستم‌عامل", "سیستم‌عامل خود را انتخاب کنید تا برنامه‌های پیشنهادی برای اتصال را دریافت کنید:"),
            "apps_plat_android": ("دکمهٔ اندروید", "🤖 اندروید"),
            "apps_plat_windows": ("دکمهٔ ویندوز", "🪟 ویندوز"),
            "apps_plat_ios":     ("دکمهٔ آیفون", "🍎 آیفون (iOS)"),
            "apps_plat_mac":     ("دکمهٔ مک", "💻 مک (macOS)"),
            "apps_list_title":   ("عنوان لیست برنامه‌ها", "📲 برنامه‌های پیشنهادی برای"),
            "apps_list_hint":    ("راهنمای زیر لیست", "روی هر برنامه بزنید تا به صفحهٔ دانلودش بروید:"),
            "apps_btn_back":     ("دکمهٔ بازگشت", "⬅️ بازگشت"),
        },
    },
    "buy": {
        "label": "🛒 خرید و فاکتور",
        "items": {
            "buy_name_title":   ("عنوان انتخاب نام", "🏷 <b>نام کانفیگت را انتخاب کن</b>"),
            "buy_name_hint":    ("راهنمای انتخاب نام", "یک نام دلخواه برای کانفیگت بفرست (فقط حروف انگلیسی، عدد، ـ یا -).\nمثلاً: <code>ali-vpn</code>\n\nیا برای ساخت خودکار، دکمهٔ زیر را بزن:"),
            "buy_btn_random_name": ("دکمهٔ ساخت نام رندوم", "🎲 ساخت نام رندوم"),
            "buy_name_made":    ("پیام نام ساخته شد", "🎲 نام ساخته شد"),
            "buy_name_show":    ("نمایش نام کانفیگ — {name}", "🏷 نام کانفیگ: <code>{name}</code>"),
            "buy_qty_title":    ("عنوان تعداد اکانت", "🔢 <b>چند اکانت می‌خواهی؟</b>"),
            "buy_qty_hint":     ("راهنمای تعداد", "تعداد اکانت موردنظرت را به عدد بفرست.\nمثلاً: <code>1</code> یا <code>10</code>"),
            "buy_qty_invalid":  ("خطای عدد نامعتبر", "❌ لطفاً یک عدد معتبر بفرست (مثلاً 1 تا 100)."),
            "buy_qty_toomany":  ("خطای تعداد زیاد", "❌ حداکثر ۱۰۰ اکانت در هر سفارش. عدد کمتری بفرست."),
            "buy_btn_back":     ("دکمهٔ بازگشت", "⬅️ بازگشت"),
        },
    },
    "payment": {
        "label": "💳 خرید و پرداخت",
        "items": {
            "pay_card_text":      ("متن پرداخت کارت‌به‌کارت — {order_id}{price}{card}", "💳 <b>پرداخت کارت‌به‌کارت</b>\n━━━━━━━━━━━━━━\n\n🧾 شماره سفارش: <code>{order_id}</code>\n💰 مبلغ: <b>{price} تومان</b>\n\n💳 اطلاعات کارت:\n<code>{card}</code>\n\nلطفاً مبلغ را واریز کرده و <b>رسید</b> (عکس یا شماره پیگیری) را اینجا ارسال کنید."),
            "pay_order_gone":     ("خطای سفارش پیدا نشد", "سفارش پیدا نشد."),
            "pay_method_invalid": ("خطای روش پرداخت نامعتبر", "روش پرداخت نامعتبر است."),
            "pay_order_pick":     ("انتخاب روش پرداخت — {order_id}{service}{plan}{price_block}", "💳 انتخاب روش پرداخت\n━━━━━━━━━━━━━━\n\nشماره سفارش: <code>{order_id}</code>\nسرویس: {service}\nپلن: {plan}\n{price_block}"),
            "pay_order_created":  ("سفارش ثبت شد — {order_id}{service}{plan}{dur}{price_block}", "🧾 سفارش ثبت شد\n━━━━━━━━━━━━━━\n\nشماره سفارش: <code>{order_id}</code>\nسرویس: {service}\nپلن: {plan}\nمدت: {dur}\n{price_block}"),
            "pay_order_created_disc": ("سفارش ثبت شد (با تخفیف) — {order_id}{service}{plan}{price_block}", "🧾 سفارش ثبت شد\n━━━━━━━━━━━━━━\n\nشماره سفارش: <code>{order_id}</code>\nسرویس: {service}\nپلن: {plan}\n{price_block}"),
            "pay_delivered":      ("پیام تحویل کانفیگ — {service}{plan}{server}{expires}", "✅ پرداخت تایید شد و کانفیگ آماده است!\n\nسرویس: {service}\nپلن: {plan}\nسرور: {server}\nانقضا: {expires}\n"),
            "pay_delivered_traffic": ("سطر حجم تحویل — {gb}", "حجم: {gb} GB\n"),
            "pay_delivered_link": ("سطر لینک تحویل — {type}{link}", "\n🔗 لینک {type}:\n<code>{link}</code>"),
            "pay_wallet_insufficient": ("خطای موجودی ناکافی — {need}{balance}{shortage}", "❌ موجودی کیف‌پول کافی نیست\n\nنیاز: {need} تومان\nموجودی: {balance} تومان\nکمبود: {shortage} تومان\n\nاز بخش «💳 کیف پول» شارژ کنید."),
            "pay_wallet_waiting": ("پرداخت کیف‌پول در انتظار تحویل — {service}{price}", "✅ پرداخت از کیف‌پول انجام شد\n\nسرویس: {service}\nمبلغ: {price} تومان\n\n⏳ کانفیگ به‌زودی توسط پشتیبانی ارسال می‌شود."),
            "pay_renew_failed":   ("خطای تمدید ناموفق", "❌ تمدید ناموفق بود. لطفاً با پشتیبانی تماس بگیرید."),
            "pay_receipt_saved":  ("پیام ثبت رسید", "✅ رسید شما ثبت شد.\n\nپرداخت برای بررسی به ادمین ارسال شد.\nبعد از تایید، کانفیگ برای شما ارسال می‌شه."),
            "pay_receipt_no_text": ("متن رسید بدون کپشن", "رسید بدون متن"),
            "btn_back_generic":  ("دکمهٔ بازگشت عمومی", "⬅️ بازگشت"),
            "pay_discount_ask":  ("متن درخواست کد تخفیف", "🎟 <b>اعمال کد تخفیف</b>\n━━━━━━━━━━━━━━\n\nلطفاً کد تخفیف خود را ارسال کنید تا مبلغ نهایی سفارش محاسبه شود."),
            "pay_method_title":  ("عنوان انتخاب روش پرداخت", "💳 <b>انتخاب روش پرداخت</b>"),
        },
    },
    "welcome": {
        "label": "👋 پیام خوش‌آمد",
        "items": {
            "txt_welcome": ("متن پیام خوش‌آمد (استفاده از {name} {id} {datetime})",
                            "سلام {name} 👋\n🆔 آیدی شما: {id}\n📅 تاریخ: {datetime}\n\nبه ربات فروش وی‌پی‌ان خوش اومدی 🚀\nاینجا میتونی به راحتی کانفیگ مورد نظرت رو تهیه کنی و آنلاین استفاده کنی 🔥\nاز منوی زیر گزینه مورد نظرت رو انتخاب کن 👇"),
        },
    },
    "renew": {
        "label": "♻️ تمدید اشتراک",
        "items": {
            "rnw_title":        ("عنوان صفحه", "♻️ تمدید اشتراک"),
            "rnw_pick_account": ("راهنمای انتخاب کانفیگ", "کدام کانفیگ را می‌خواهید شارژ/تمدید کنید؟"),
            "rnw_pick_duration":("راهنمای انتخاب مدت", "مدت تمدید را انتخاب کنید:"),
            "rnw_pick_volume":  ("راهنمای انتخاب حجم", "حجم موردنظر برای تمدید را انتخاب کنید:"),
            "rnw_empty":        ("متن نداشتن اکانت", "شما اکانتی برای تمدید ندارید.\nابتدا یک کانفیگ خریداری کنید."),
            "rnw_no_plans":     ("متن نبودن پلن", "برای سرور این اکانت پلنی فعال نیست."),
            "rnw_invoice_title":("عنوان فاکتور تمدید", "🧾 فاکتور تمدید"),
            "rnw_invoice_hint": ("راهنمای فاکتور", "حجم و مدت پس از پرداخت، به اکانت فعلی شما اضافه می‌شود.\nروش پرداخت را انتخاب کنید:"),
            "rnw_done_title":   ("عنوان پیام موفقیت", "✅ تمدید انجام شد"),
            "rnw_done_hint":    ("راهنمای پس از تمدید", "لینک کانفیگ شما تغییری نکرده و همان قبلی است. ✅"),
            "rnw_btn_back":     ("دکمهٔ بازگشت", "⬅️ بازگشت"),
        },
    },
    "test": {
        "label": "🎁 اکانت تست",
        "items": {
            "test_title":       ("عنوان صفحه", "🎁 دریافت اکانت تست"),
            "test_pick":        ("راهنمای انتخاب", "یکی از اکانت‌های تست زیر را انتخاب کنید:"),
            "test_disabled":    ("متن غیرفعال بودن", "⛔️ دریافت اکانت تست در حال حاضر غیرفعال است.\nلطفاً بعداً مراجعه کنید."),
            "test_disabled_short": ("هشدار کوتاه غیرفعال", "غیرفعال است"),
            "test_none":        ("متن نبودن اکانت تست", "فعلاً اکانت تستی تعریف نشده است."),
            "test_building":    ("متن در حال ساخت", "⏳ در حال ساخت اکانت تست..."),
            "test_ready_title": ("عنوان اکانت آماده", "✅ اکانت تست شما آماده است"),
            "test_failed":      ("متن خطای ساخت", "❌ ساخت اکانت تست ناموفق بود. لطفاً بعداً تلاش کنید."),
            "test_already":     ("متن دریافت قبلی", "شما قبلاً اکانت تست دریافت کرده‌اید. هر کاربر فقط یک‌بار می‌تواند اکانت تست بگیرد."),
            "test_btn_back":    ("دکمهٔ بازگشت", "⬅️ بازگشت"),
        },
    },
    "discount": {
        "label": "🎟 کد تخفیف",
        "items": {
            "disc_btn_have":      ("دکمهٔ «کد تخفیف دارم»", "🎟 کد تخفیف دارم"),
            "disc_btn_none":      ("دکمهٔ «ادامه بدون کد»", "⏭️ ادامه بدون کد تخفیف"),
            "disc_decision_hint": ("راهنمای صفحهٔ تصمیم", "اگر کد تخفیف داری، اعمالش کن؛ در غیر این صورت بدون کد ادامه بده:"),
            "disc_ask":           ("متن درخواست کد", "🎟 کد تخفیف خود را ارسال کنید:"),
            "disc_order_gone":    ("خطای سفارش پیدا نشد", "سفارش پیدا نشد. لطفاً دوباره از خرید شروع کنید."),
            "disc_retry":         ("متن تلاش دوباره", "می‌توانید دوباره کد را بفرستید یا /start را بزنید."),
            "disc_applied_title": ("عنوان اعمال موفق", "✅ کد تخفیف اعمال شد"),
            "disc_lbl_base":      ("برچسب قیمت پایه", "قیمت پایه:"),
            "disc_lbl_off":       ("برچسب تخفیف", "تخفیف:"),
            "disc_lbl_final":     ("برچسب مبلغ نهایی", "مبلغ نهایی:"),
            "disc_pay_title":     ("عنوان انتخاب پرداخت", "💳 روش پرداخت را انتخاب کنید:"),
        },
    },
    "shop": {
        "label": "🛍 فروشگاه و خرید",
        "items": {
            "shop_loc_title":     ("عنوان انتخاب لوکیشن", "<b>انتخاب لوکیشن</b>\n━━━━━━━━━━━━━━\n\nلوکیشن مورد نظر را انتخاب کنید:"),
            "shop_dur_title":     ("عنوان انتخاب مدت — {loc}", "<b>{loc}</b>\n━━━━━━━━━━━━━━\n\nمدت اشتراک را انتخاب کنید:"),
            "shop_vol_title":     ("عنوان انتخاب حجم — {loc} {dur}", "<b>{loc}</b>\nمدت: {dur}\n━━━━━━━━━━━━━━\n\nحجم مورد نظر را انتخاب کنید:"),
            "shop_btn_back":      ("دکمهٔ بازگشت خرید", "⬅️ بازگشت"),
            "shop_loc_fallback":  ("نام جایگزین لوکیشن", "لوکیشن"),
            "shop_vol_custom":    ("متن حجم دلخواه — {max}", "✍️ <b>وارد کردن حجم دلخواه</b>\n━━━━━━━━━━━━━━\n\nلطفاً حجم موردنظر را فقط به عدد وارد کنید.\n\nمثال: <code>2</code> یعنی سفارش ۲ گیگابایت\nمحدوده مجاز سفارش: ۱ تا {max} گیگابایت"),
            "shop_vol_numeric":   ("خطای حجم غیرعددی", "لطفاً فقط عدد حجم را ارسال کنید.\nمثال: <code>2</code> برای سفارش ۲ گیگابایت"),
            "shop_vol_invalid":   ("خطای حجم خارج از محدوده — {max}", "حجم انتخابی باید بین ۱ تا {max} گیگابایت باشد. لطفاً عدد معتبر وارد کنید."),
            "shop_invoice":       ("فاکتور ثبت سفارش — {name_line}{plan}{gb}{dur}{qty_block}{total}{hint}", "✅ سفارش ثبت شد\n━━━━━━━━━━━━━━\n\n{name_line}پلن: {plan}\nحجم: {gb}\nمدت: {dur}\n{qty_block}💰 مبلغ قابل پرداخت: {total} تومان\n\n{hint}"),
            "shop_invoice_name_line": ("سطر نام کانفیگ — {name}", "🏷 نام کانفیگ: {name}\n"),
            "shop_invoice_qty_block": ("بلوک تعداد فاکتور — {qty}{unit}", "🔢 تعداد: {qty} عدد\n💵 قیمت واحد: {unit} تومان\n"),
            "shop_plan_gone":     ("خطای پلن ناموجود", "این پلن دیگر موجود نیست."),
            "shop_plan_notfound": ("خطای پلن پیدا نشد", "پلن پیدا نشد."),
            "shop_plan_selected": ("متن پلن انتخاب‌شده — {service}{plan}{dur}{price_block}", "✅ پلن انتخاب شد\n━━━━━━━━━━━━━━\n\n🔐 سرویس: {service}\n💠 پلن: {plan}\n⏳ مدت اعتبار: {dur}\n{price_block}\n\nدر صورت داشتن کد تخفیف، آن را اعمال کنید. در غیر این صورت، پرداخت را ادامه دهید."),
            "shop_back_title":    ("عنوان بازگشت به فروشگاه", "⚡ خرید کانفیگ VIP\n━━━━━━━━━━━━━━\n\nلطفاً سرویس موردنظر خود را انتخاب کنید:"),
            "shop_cat_invalid":   ("خطای دستهٔ نامعتبر", "دسته‌بندی نامعتبر است."),
            "shop_cat_empty":     ("متن دستهٔ خالی — {title}", "{title}\n\nفعلاً پلنی برای این سرور فعال نیست. لطفاً کمی بعد دوباره بررسی کنید."),
            "shop_cat_services":  ("متن انتخاب سرویس — {title}", "{title}\n━━━━━━━━━━━━━━\n\nیکی از سرویس‌های فعال را انتخاب کنید. پس از ثبت سفارش، مسیر پرداخت و ارسال رسید نمایش داده می‌شود."),
            "shop_cat_v2ray":     ("نام دستهٔ V2Ray", "🟢 V2Ray VIP"),
            "shop_cat_l2tp":      ("نام دستهٔ L2TP", "🟠 L2TP نامحدود"),
            "shop_cat_openvpn":   ("نام دستهٔ OpenVPN", "🔵 OpenVPN تک‌کاربره"),
            "shop_cat_starlink":  ("نام دستهٔ استارلینک", "استارلینک اختصاصی"),
            "shop_type_empty":    ("متن نوع خالی — {title}", "{title}\n\nفعلاً سرویسی در این بخش ثبت نشده است."),
            "shop_type_pick":     ("متن انتخاب نوع — {title}", "{title}\n\nلطفاً سرویس مورد نظر را انتخاب کنید:"),
            "shop_svc_gone":      ("خطای سرویس پیدا نشد", "سرویس پیدا نشد."),
            "shop_svc_single":    ("برچسب تک‌کاربره", "تک‌کاربره"),
            "shop_svc_multi":     ("برچسب چندکاربره", "چندکاربره / سازمانی"),
            "shop_svc_detail":    ("جزئیات سرویس — {name}{type}{desc}", "✨ <b>{name}</b>\n━━━━━━━━━━━━━━\n\nنوع سرویس: {type}\n\n{desc}\n\nبرای مشاهده پلن‌ها و ثبت سفارش، دکمه زیر را انتخاب کنید."),
            "shop_svc_no_desc":   ("متن بدون توضیحات", "توضیحات این سرویس به‌زودی تکمیل می‌شود."),
            "shop_svc_no_plans":  ("خطای بدون پلن", "برای این سرویس هنوز پلنی ثبت نشده است."),
            "shop_vip_pick":      ("متن انتخاب پلن VIP", "💎 انتخاب پلن VIP\n━━━━━━━━━━━━━━\n\nپلن مناسب مصرف خود را انتخاب کنید. مبلغ هر پلن در مرحله بعد همراه با معادل USDT و TRX نمایش داده می‌شود."),
            "shop_sl_intro":      ("معرفی استارلینک — {price}{max}", "<b>Starlink اختصاصی WGV</b>\n━━━━━━━━━━━━━━\n\nقیمت هر گیگابایت: {price} تومان\nحجم قابل سفارش: ۱ تا {max} گیگابایت\n\nحجم مورد نظر را انتخاب کنید:"),
            "shop_sl_intro_short": ("معرفی کوتاه استارلینک — {price}", "قیمت هر گیگ: {price} تومان\nحجم را انتخاب کنید:"),
            "shop_sl_plan_title": ("عنوان پلن استارلینک — {gb}", "استارلینک {gb} گیگابایت | 1 ماهه | کاربر نامحدود"),
            "shop_sl_invoice":    ("فاکتور استارلینک — {order_id}{gb}{price_block}", "✅ سفارش استارلینک ثبت شد\n━━━━━━━━━━━━━━\n\n🧾 شماره سفارش: <code>{order_id}</code>\nسرویس: استارلینک اختصاصی\n📦 حجم: {gb} گیگابایت\n👥 تعداد کاربر: نامحدود\n⏳ اعتبار: 1 ماهه\n{price_block}\n\nروش پرداخت موردنظر را انتخاب کنید. کارت‌به‌کارت از طریق هماهنگی با ادمین انجام می‌شود و پرداخت ارزی با USDT یا TRX قابل ثبت است."),
            "shop_sl_missing":    ("خطای استارلینک غیرفعال", "سرویس استارلینک هنوز در دیتابیس فعال نیست. یک بار بات را ری‌استارت کنید تا داده‌های اولیه ساخته شود."),
        },
    },
    "guide": {
        "label": "📘 راهنمای اتصال",
        "items": {
            "guide_fallback":  ("متن پیش‌فرض راهنما", "📋 لیست راهنمای اتصال\n\nلیست راهنمای اتصال در این بخش نمایش داده می‌شود."),
            "guide_back_hint": ("راهنمای بازگشت", "برای بازگشت به منو دکمهٔ زیر را بزنید:"),
            "guide_btn_back":  ("دکمهٔ بازگشت", "⬅️ بازگشت"),
        },
    },
    "tracking": {
        "label": "🔎 پیگیری خرید",
        "items": {
            "track_empty":       ("متن بدون سفارش", "🔎 <b>پیگیری خرید</b>\n━━━━━━━━━━━━━━\n\nهنوز سفارشی برای شما ثبت نشده است. برای شروع، از بخش خرید کانفیگ سرویس موردنظر را انتخاب کنید."),
            "track_title":       ("عنوان لیست سفارش‌ها", "🔎 <b>آخرین سفارش‌های شما</b>\n━━━━━━━━━━━━━━\n\n"),
            "track_item":        ("قالب هر سفارش — {order_id}{service}{plan}{price}{status}{date}", "🧾 سفارش #{order_id}\nسرویس: {service}\nپلن: {plan}\nمبلغ نهایی: {price} تومان\nوضعیت: {status}\nتاریخ ثبت: {date}\n\n"),
            "track_st_pending":  ("وضعیت: در انتظار پرداخت", "در انتظار پرداخت"),
            "track_st_review":   ("وضعیت: در انتظار بررسی", "در انتظار بررسی ادمین"),
            "track_st_delivery": ("وضعیت: در انتظار تحویل", "در انتظار تحویل اشتراک"),
            "track_st_approved": ("وضعیت: تایید شده", "تایید شده"),
            "track_st_rejected": ("وضعیت: رد شده", "رد شده"),
        },
    },
    "account": {
        "label": "👤 حساب کاربری",
        "items": {
            "acct_title":       ("سربرگ پروفایل — {name}{id}{username}{active}{orders}", "👑 پروفایل کاربری شما\n━━━━━━━━━━━━━━\n\n👤 نام: {name}\n🆔 آیدی عددی: <code>{id}</code>\n🔗 یوزرنیم: @{username}\n\n🔐 کانفیگ‌های فعال: {active}\n🧾 سفارش‌های اخیر: {orders}\n\n"),
            "acct_no_username": ("متن بدون یوزرنیم", "ندارد"),
            "acct_subs_title":  ("عنوان اشتراک‌های فعال", "✨ اشتراک‌های فعال شما:\n\n"),
            "acct_sub_item":    ("قالب هر اشتراک — {service}{plan}{days}{expires}", "💠 {service}\nپلن: {plan}\nمدت: {days} روز\nپایان اعتبار: {expires}\n\n"),
            "acct_no_subs":     ("متن بدون اشتراک", "فعلاً کانفیگ فعالی ندارید.\nبرای شروع، از بخش خرید کانفیگ سرویس مناسب خودتان را انتخاب کنید.\n\n"),
            "acct_footer":      ("پاورقی پروفایل", "🛟 برای تمدید، تغییر پلن یا مشکل اتصال، از پشتیبانی سریع پیام بفرستید."),
        },
    },
    "faq": {
        "label": "❓ سوالات متداول",
        "items": {
            "faq_title":     ("عنوان لیست سوالات", "❓ <b>سوالات متداول WGV</b>\n━━━━━━━━━━━━━━\n\nپاسخ سوالات پرتکرار درباره خرید، پرداخت، تحویل کانفیگ و اتصال را از لیست زیر انتخاب کنید."),
            "faq_empty":     ("متن بدون سوال", "فعلاً سوالی ثبت نشده است."),
            "faq_not_found": ("خطای سوال پیدا نشد", "این سوال پیدا نشد."),
            "faq_answer":    ("قالب پاسخ — {question}{answer}", "💬 <b>پاسخ سوال</b>\n━━━━━━━━━━━━━━\n\n<b>{question}</b>\n\n{answer}"),
            "faq_btn_back":  ("دکمهٔ بازگشت به سوالات", "⬅️ بازگشت به سوالات"),
        },
    },
    "referral": {
        "label": "🎁 دعوت دوستان",
        "items": {
            "ref_title":      ("متن صفحهٔ دعوت — {code}{count}{commission}", "🎁 دعوت دوستان\n\nکد دعوت شما: <code>{code}</code>\n\n📊 آمار:\n👥 تعداد معرفی‌ها: {count}\n💰 کل کمیسیون: {commission} تومان\n\nدوستان رو دعوت کن و کمیسیون بگیر!\n\nلینک دعوت:\nhttps://t.me/?start=ref_{code}"),
            "ref_btn_copy":   ("دکمهٔ کپی کد", "📋 کپی کد دعوت"),
            "ref_btn_back":   ("دکمهٔ بازگشت", "⬅️ بازگشت"),
            "ref_info_alert": ("پیام نمایش کد — {code}", "کد دعوت شما: {code}\n\nاین کد رو به دوستانت بده تا وقتی ثبت‌نام می‌کنن به عنوان معرف ثبت بشی"),
            "refm_fallback":     ("متن پیش‌فرض صفحهٔ دعوت (منو)", "🎁 دعوت دوستان\n\nلینک دعوت اختصاصی خودتان را بفرستید. بعد از خرید موفق دوستتان، یک هدیه ویژه برای تمدید یا خرید بعدی شما ثبت می‌شود."),
            "refm_stats":        ("آمار دعوت — {link}{count}", "\n\n🔗 لینک دعوت اختصاصی شما:\n{link}\n\n👥 تعداد دعوت‌شده‌ها: {count}\n\n🎁 هدیه دعوت:\nبعد از خرید موفق فرد دعوت‌شده، پاداش شما در سوابق دعوت ثبت می‌شود و پشتیبانی برای اعمال هدیه راهنمایی‌تان می‌کند.\n\n"),
            "refm_rewards_title": ("عنوان پاداش‌ها", "آخرین پاداش‌های شما:\n\n"),
            "refm_reward_item":  ("قالب هر پاداش — {order_id}{days}", "سفارش #{order_id}\nهدیه ثبت‌شده: {days} روز اعتبار ویژه\n\n"),
        },
    },
    "coop": {
        "label": "🤝 درخواست همکاری",
        "items": {
            "coop_already":       ("پیام همکار فعلی", "✅ شما در حال حاضر همکار (ساب‌ادمین) هستید.\nبرای مشاهده پنل خود دکمه آمار فروش را بزنید."),
            "coop_ask":           ("متن درخواست همکاری", "🤝 درخواست همکاری\n\nیک پیام کوتاه درباره خودت و روش کارت بنویس.\nمثلاً: من در کانال X فعالم و می‌تونم ماهی Y تا بفروشم.\n\nدرخواستت به صورت تیکت برای مدیر ارسال می‌شه."),
            "coop_btn_back":      ("دکمهٔ بازگشت", "⬅️ بازگشت"),
            "coop_sent":          ("پیام ثبت درخواست — {ticket_id}", "✅ درخواست شما (تیکت #{ticket_id}) ارسال شد.\nمنتظر پاسخ مدیر باشید."),
            "coop_approved_user": ("پیام تأیید به کاربر", "🎉 درخواست همکاری شما تأیید شد!\nاکنون به عنوان همکار ثبت شدید."),
            "coop_rejected_user": ("پیام رد به کاربر", "متأسفانه درخواست همکاری شما در حال حاضر تأیید نشد."),
        },
    },
    "keyboards": {
        "label": "⌨️ دکمه‌های شیشه‌ای خرید",
        "items": {
            "paykb_card":       ("دکمهٔ کارت‌به‌کارت (کوتاه)", "💳 کارت‌به‌کارت"),
            "paykb_card_long":  ("دکمهٔ پرداخت کارت‌به‌کارت", "💳 پرداخت کارت‌به‌کارت"),
            "paykb_wallet":     ("دکمهٔ پرداخت از کیف‌پول", "💰 پرداخت از کیف‌پول"),
            "volkb_item":       ("قالب دکمهٔ حجم — {gb}", "{gb} گیگابایت"),
            "volkb_custom":     ("دکمهٔ حجم دلخواه", "✍️ حجم دلخواه"),
            "svckb_item":       ("قالب دکمهٔ سرویس — {name}", "🔘 {name}"),
            "svckb_view_plans": ("دکمهٔ مشاهده پلن‌ها", "💎 مشاهده پلن‌ها"),
            "plankb_item":      ("قالب دکمهٔ پلن — {title}{price}", "{title} — {price} تومان"),
            "disckb_have":      ("دکمهٔ کد تخفیف دارم (کوتاه)", "✏️ کد تخفیف دارم"),
            "disckb_skip":      ("دکمهٔ ادامه بدون کد (کوتاه)", "⏭️ ادامه"),
        },
    },
    "units": {
        "label": "📏 واحدها و برچسب‌های عمومی",
        "items": {
            "u_no_expiry":     ("برچسب بی‌انقضا", "بی‌انقضا"),
            "u_no_expiry_plain": ("برچسب بدون انقضا", "بدون انقضا"),
            "u_no_expiry_long": ("برچسب بدون انقضا (با ایموجی)", "♾ بدون انقضا"),
            "u_expired":       ("برچسب منقضی شده", "⛔️ منقضی شده"),
            "u_expiry_at":     ("برچسب تاریخ انقضا — {date}", "📅 انقضا: {date}"),
            "u_remaining_dh":  ("باقیمانده روز و ساعت — {days}{hours}", "⏳ باقیمانده: {days} روز و {hours} ساعت"),
            "u_remaining_h":   ("باقیمانده ساعت — {hours}", "⏳ باقیمانده: {hours} ساعت"),
            "u_dh":            ("روز و ساعت (بدون برچسب) — {days}{hours}", "{days} روز و {hours} ساعت"),
            "u_h":             ("ساعت (بدون برچسب) — {hours}", "{hours} ساعت"),
            "u_month_suffix":  ("پسوند ماهه", " ماهه"),
            "u_day_suffix":    ("پسوند روزه", " روزه"),
            "u_gig":           ("پسوند گیگ", " گیگ"),
            "u_unlimited":     ("برچسب نامحدود", "نامحدود"),
            "u_unlimited_long": ("برچسب نامحدود (با ایموجی)", "♾ نامحدود"),
            "u_toman":         ("پسوند تومان", " تومان"),
        },
    },
}

HIDEABLE_BUTTONS = ["btn_wallet", "btn_apps", "btn_renew", "btn_test", "btn_support", "btn_faq",
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
COLORABLE_BUTTONS = ["btn_buy", "btn_profile", "btn_wallet", "btn_subs", "btn_renew", "btn_test", "btn_apps", "btn_support", "btn_faq",
                     "btn_coop", "btn_guide", "btn_cfg_update", "btn_addcfg",
                     "btn_admin", "btn_sa_stats", "btn_referral"]
_BTN_LABELS = {
    "btn_buy": "⚡ خرید کانفیگ", "btn_profile": "👤 پنل کاربری",
    "btn_wallet": "💳 کیف پول", "btn_subs": "📦 اشتراک‌های من",
    "btn_renew": "♻️ تمدید اشتراک",
    "btn_test": "🎁 دریافت اکانت تست",
    "btn_apps": "📲 دریافت برنامه‌ها",
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
        # entityهای ذخیره‌شده (ایموجی پریمیوم) را هم بخوان تا با کلید مقصد کپی شوند
        from services.ui_render import get_ui_entities
        _ent_raw = get_setting(key + "__ent", "")

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
            # entityها را با کلید صفحهٔ محتوا هم ذخیره کن تا هنگام ارسال اعمال شوند
            set_setting(ckey + "__ent", _ent_raw)
            applied_note = "\n(روی متن واقعی ربات اعمال شد ✅)"
        elif key in TXT_TO_SETTING:
            skey = TXT_TO_SETTING[key]
            set_setting(skey, value)
            set_setting(skey + "__ent", _ent_raw)
            applied_note = "\n(اعمال شد ✅)"
    except Exception:
        pass

    await msg.answer(
        f"✅ ذخیره شد:\n<code>{value}</code>{applied_note}",
        reply_markup=back_kb,
    )
    # تشخیص ایموجی پریمیوم: به ادمین بگو چند entity و از چه نوعی دریافت شد
    try:
        ents = msg.entities or []
        ce = [e for e in ents if str(getattr(e, "type", "")).endswith("custom_emoji")]
        if ce:
            ids = ", ".join(str(getattr(e, "custom_emoji_id", "?")) for e in ce)
            await msg.answer(f"🔎 تشخیص: {len(ce)} ایموجی پریمیوم دریافت شد ✅\nID: <code>{ids}</code>")
        else:
            await msg.answer(
                "🔎 تشخیص: هیچ ایموجی پریمیومی در این متن دریافت نشد.\n"
                "اگر ایموجی پریمیوم گذاشته بودی و این پیام را می‌بینی، یعنی مشکل از "
                "دریافت آن است (نه نمایش)."
            )
    except Exception:
        pass


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
