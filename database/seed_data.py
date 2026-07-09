from database.db import get_connection, init_db

SERVICES = [
    {
        "category": "v2ray",
        "service_type": "single",
        "name": "V2Ray VIP یک‌ماهه",
        "description": (
            "🟢 انتخاب پیشنهادی برای استفاده روزانه، شبکه‌های اجتماعی، تماس تصویری، ترید و وب‌گردی.\n\n"
            "این سرویس برای اتصال سریع، پایدار و تحویل منظم کانفیگ آماده شده است."
        ),
        "plans": [
            ("۳ گیگابایت | اعتبار ۱ ماهه", 760000, 30),
            ("۵ گیگابایت | اعتبار ۱ ماهه", 1000000, 30),
            ("۱۰ گیگابایت | اعتبار ۱ ماهه", 1700000, 30),
            ("۲۰ گیگابایت | اعتبار ۱ ماهه", 3000000, 30),
        ],
    },
    {
        "category": "l2tp",
        "service_type": "bulk",
        "name": "L2TP نامحدود سازمانی",
        "description": (
            "🟠 مناسب شرکت‌ها، دفاتر، استفاده سازمانی و دستگاه‌های iPhone.\n\n"
            "بعد از تایید پرداخت، مشخصات اتصال شامل Server، Username، Password و Secret برای شما ارسال می‌شود."
        ),
        "plans": [
            ("۱MB نامحدود | اعتبار ۷ روزه", 2500000, 7),
            ("۲MB نامحدود | اعتبار ۷ روزه", 4500000, 7),
        ],
    },
    {
        "category": "starlink",
        "service_type": "custom_volume",
        "name": "Starlink اختصاصی حجم دلخواه",
        "description": (
            "سرویس اختصاصی با حجم دلخواه، اعتبار یک‌ماهه و تعداد کاربر نامحدود.\n\n"
            "در این سرویس شما حجم موردنیاز را از ۱ تا ۳۰ گیگابایت وارد می‌کنید و سفارش دقیقاً بر اساس همان مقدار ثبت می‌شود."
        ),
        "plans": [
            # پلن «حجم دلخواه» صفرقیمت حذف شد — پلن‌های استارلینک توسط هد‌ادمین اضافه می‌شوند.
        ],
    },
    {
        "category": "openvpn",
        "service_type": "single",
        "name": "OpenVPN تک‌کاربره",
        "description": (
            "🔵 مناسب کاربرانی که اتصال امن، سازگار و کلاسیک می‌خواهند.\n\n"
            "پس از تایید رسید، فایل یا متن کانفیگ OpenVPN همراه با راهنمای اتصال ارسال می‌شود."
        ),
        "plans": [
            ("۳ گیگابایت | تک‌کاربره", 1000000, 30),
            ("۵ گیگابایت | تک‌کاربره", 1500000, 30),
            ("۱۰ گیگابایت | تک‌کاربره", 2700000, 30),
            ("۲۰ گیگابایت | تک‌کاربره", 5100000, 30),
        ],
    },
]

CONTENT_PAGES = {
    "start_message": (
        "پیام شروع",
        "👑 <b>به WGV خوش آمدید</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "اینجا می‌توانید سرویس مناسب خود را با چند مرحله ساده انتخاب و سفارش ثبت کنید.\n\n"
        "✅ کانفیگ اختصاصی پس از تایید رسید\n"
        "✅ پشتیبانی برای راه‌اندازی و اتصال\n"
        "✅ امکان انتخاب بین V2Ray، L2TP، OpenVPN و Starlink\n\n"
        "برای شروع، از منوی پایین گزینه خرید کانفیگ را انتخاب کنید."
    ),
    "pricing": (
        "تعرفه سرویس‌ها",
        "💎 <b>تعرفه سرویس‌های WGV</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "🟢 <b>V2Ray VIP | اعتبار ۱ ماهه</b>\n"
        "• 3GB  →  760,000 تومان\n"
        "• 5GB  →  1,000,000 تومان\n"
        "• 10GB →  1,700,000 تومان\n"
        "• 20GB →  3,000,000 تومان\n\n"
        "🟠 <b>L2TP نامحدود | اعتبار ۷ روزه</b>\n"
        "• 1MB → 2,500,000 تومان\n"
        "• 2MB → 4,500,000 تومان\n\n"
        "🔵 <b>OpenVPN تک‌کاربره | اعتبار ۱ ماهه</b>\n"
        "• 3GB  → 1,000,000 تومان\n"
        "• 5GB  → 1,500,000 تومان\n"
        "• 10GB → 2,700,000 تومان\n"
        "• 20GB → 5,100,000 تومان\n\n"
        "<b>Starlink اختصاصی | اعتبار ۱ ماهه</b>\n"
        "• حجم دلخواه از ۱ تا ۳۰ گیگابایت\n"
        "• تعداد کاربر نامحدود\n"
        "• محاسبه قیمت بر اساس حجم انتخابی\n\n"
        "برای ثبت سفارش، از بخش خرید کانفیگ سرویس موردنظر را انتخاب کنید."
    ),
    "channels_list": (
        "راهنمای اتصال",
        "📘 <b>راهنمای اتصال سریع</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "🟢 <b>V2Ray & Starlink</b>\n"
        "لینک، QR یا مشخصات دریافتی را داخل برنامه‌های پیشنهادی پشتیبانی وارد کنید. برای V2Ray معمولاً v2rayNG، V2Box، Streisand یا Shadowrocket پیشنهاد می‌شود.\n\n"
        "🔵 <b>OpenVPN</b>\n"
        "فایل .ovpn را داخل OpenVPN Connect ایمپورت کنید و سپس اتصال را فعال کنید.\n\n"
        "🟠 <b>L2TP</b>\n"
        "مشخصات Server، Username، Password و Secret را در تنظیمات VPN دستگاه وارد کنید.\n\n"
        "در صورت نیاز به راهنمایی، از بخش پشتیبانی سریع پیام بفرستید."
    ),
    "faq": (
        "سوالات متداول",
        "❓ <b>سوالات متداول</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "در این بخش پاسخ سوال‌های پرتکرار درباره خرید، پرداخت، تحویل کانفیگ و اتصال قرار دارد."
    ),
    "support": (
        "پشتیبانی سریع",
        "🛟 <b>پشتیبانی سریع WGV</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "برای پیگیری خرید، ارسال مشکل اتصال، تمدید سرویس یا دریافت راهنمای نصب، پیام خود را همینجا ثبت کنید.\n\n"
        "برای بررسی سریع‌تر، لطفاً این موارد را ارسال کنید:\n"
        "• شماره سفارش\n"
        "• نوع سرویس\n"
        "• مدل دستگاه\n"
        "• تصویر خطا یا رسید پرداخت، در صورت وجود"
    ),
    "referral": (
        "دعوت دوستان",
        "🎁 <b>دعوت دوستان</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "لینک دعوت اختصاصی خود را برای دوستانتان ارسال کنید.\n"
        "پس از خرید موفق فرد دعوت‌شده، پاداش شما در سوابق دعوت ثبت می‌شود و قابل پیگیری خواهد بود."
    ),
}

FAQS = [
    ("بعد از پرداخت، کانفیگ چطور تحویل داده می‌شود؟", "بعد از ارسال رسید و تایید ادمین، کانفیگ به صورت لینک، QR، متن یا فایل برای شما ارسال می‌شود."),
    ("روش‌های پرداخت چیست؟", "برای همه سرویس‌ها، پرداخت ارزی USDT و TRX فعال است. پرداخت کارت‌به‌کارت هم با هماهنگی مستقیم ادمین انجام می‌شود تا اطلاعات پرداخت دقیق و امن ارسال شود."),
    ("V2Ray بهتر است یا OpenVPN؟", "برای استفاده روزانه و سرعت بالا معمولاً V2Ray پیشنهاد می‌شود. اگر فایل کلاسیک و سازگاری بیشتر می‌خواهید، OpenVPN انتخاب خوبی است."),
    ("L2TP مناسب چه کسانی است؟", "L2TP برای شرکت‌ها، دفاتر و کاربران iPhone مناسب است؛ مخصوصاً زمانی که راه‌اندازی ساده و اتصال پایدار نیاز دارید."),
    ("حجم Starlink را چطور انتخاب کنم؟", "در بخش Starlink روی وارد کردن حجم دلخواه بزنید و فقط عدد حجم را به گیگابایت ارسال کنید. عدد مجاز بین ۱ تا ۳۰ است."),
    ("اگر وصل نشدم چه کار کنم؟", "از بخش پشتیبانی سریع تیکت ثبت کنید و مدل دستگاه، نوع سرویس، برنامه مورد استفاده و تصویر خطا را ارسال کنید."),
    ("امکان تمدید سرویس وجود دارد؟", "بله. می‌توانید سرویس جدید ثبت کنید یا برای هماهنگی تمدید از بخش پشتیبانی پیام دهید."),
]


def upsert_service(cursor, item):
    cursor.execute("""
    SELECT id FROM services WHERE category = ? AND service_type = ? AND name = ?
    """, (item["category"], item["service_type"], item["name"]))
    row = cursor.fetchone()
    if row:
        service_id = row[0]
        cursor.execute("""
        UPDATE services SET description = ? WHERE id = ?
        """, (item["description"], service_id))
    else:
        cursor.execute("""
        INSERT INTO services (category, service_type, name, description, is_active)
        VALUES (?, ?, ?, ?, 1)
        """, (item["category"], item["service_type"], item["name"], item["description"]))
        service_id = cursor.lastrowid
    return service_id


def upsert_plan(cursor, service_id, title, price, duration):
    # فقط اگه پلن وجود نداره بساز — is_active رو دست نزن
    cursor.execute("SELECT id FROM plans WHERE service_id = ? AND title = ?", (service_id, title))
    row = cursor.fetchone()
    if not row:
        cursor.execute("""
        INSERT INTO plans (service_id, title, price_toman, duration_days, is_active)
        VALUES (?, ?, ?, ?, 1)
        """, (service_id, title, price, duration))


def _table_has_rows(cursor, table):
    try:
        cursor.execute(f"SELECT 1 FROM {table} LIMIT 1")
        return cursor.fetchone() is not None
    except Exception:
        return False


def _get_flag(cursor, key):
    try:
        cursor.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
        r = cursor.fetchone()
        return r[0] if r else None
    except Exception:
        return None


def _set_flag(cursor, key, value="1"):
    cursor.execute("""
        INSERT INTO bot_settings (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
    """, (key, value))


def _ensure_starlink_service(cursor):
    cursor.execute("SELECT id FROM services WHERE category='starlink' AND is_active=1 ORDER BY id LIMIT 1")
    if cursor.fetchone():
        return
    cursor.execute("""
        INSERT INTO services (category, service_type, name, description, is_active)
        VALUES ('starlink', 'custom_volume', 'استارلینک اختصاصی', 'سرویس استارلینک اختصاصی', 1)
    """)


def _cleanup_free_starlink_plan(cursor):
    """حذف یک‌بارهٔ پلن تستی «حجم دلخخواه» با قیمت صفر."""
    cursor.execute("DELETE FROM plans WHERE price_toman = 0 AND title LIKE '%حجم دلخواه%'")


def seed_default_vpn_shop():
    """
    Seed یک‌بار-اجرا و غیرمخرب:
    - اجرای اول (دیتابیس خالی): همه سرویس/پلن/صفحات/FAQ ساخته می‌شود و فلگ ست می‌شود.
    - اجراهای بعدی: هیچ‌چیزِ ادمین بازنویسی نمی‌شود؛ فقط ردیف‌های گمشده اضافه می‌شوند.
    این یعنی تغییراتِ پنل ادمین با ری‌استارت برنمی‌گردند.
    """
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # غیرفعال‌کردن دسته‌های ناشناخته (idempotent و بی‌ضرر)
        cursor.execute("""
            UPDATE services SET is_active = 0
            WHERE category NOT IN ('v2ray', 'l2tp', 'openvpn', 'starlink')
        """)

        already_seeded = (_get_flag(cursor, "initial_seed_done") == "1") or _table_has_rows(cursor, "plans")

        if not already_seeded:
            # ── اجرای اولیه — seed کامل ──
            for item in SERVICES:
                service_id = upsert_service(cursor, item)
                for title, price, duration in item["plans"]:
                    upsert_plan(cursor, service_id, title, price, duration)
            cursor.execute("DELETE FROM content_pages WHERE key = 'reviews'")
            for key, (title, content) in CONTENT_PAGES.items():
                cursor.execute("""
                    INSERT OR REPLACE INTO content_pages (key, title, content, file_id, file_type, updated_at)
                    VALUES (?, ?, ?, NULL, NULL, CURRENT_TIMESTAMP)
                """, (key, title, content))
            cursor.execute("DELETE FROM faq_items")
            for idx, (question, answer) in enumerate(FAQS, start=1):
                cursor.execute("""
                    INSERT INTO faq_items (question, answer, sort_order, is_active)
                    VALUES (?, ?, ?, 1)
                """, (question, answer, idx))
            _set_flag(cursor, "initial_seed_done", "1")
        else:
            # ── اجراهای بعدی — غیرمخرب (تغییرات ادمین حفظ می‌شود) ──
            _set_flag(cursor, "initial_seed_done", "1")
            _ensure_starlink_service(cursor)
            for key, (title, content) in CONTENT_PAGES.items():
                cursor.execute(
                    "INSERT OR IGNORE INTO content_pages (key, title, content) VALUES (?, ?, ?)",
                    (key, title, content),
                )
            if not _table_has_rows(cursor, "faq_items"):
                for idx, (question, answer) in enumerate(FAQS, start=1):
                    cursor.execute("""
                        INSERT INTO faq_items (question, answer, sort_order, is_active)
                        VALUES (?, ?, ?, 1)
                    """, (question, answer, idx))

        # پاکسازی یک‌بارهٔ پلن «حجم دلخواه» صفرقیمت
        if _get_flag(cursor, "cleanup_freeplan_done") != "1":
            _cleanup_free_starlink_plan(cursor)
            _set_flag(cursor, "cleanup_freeplan_done", "1")

        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    seed_default_vpn_shop()
    print("✅ VPN services, plans, content pages and FAQ seeded successfully.")
