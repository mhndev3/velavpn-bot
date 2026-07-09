import os

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database.db import get_connection
from services.content_media_service import send_content_page
from services.referral_service import (
    get_referral_count,
    get_referral_rewards,
)
from config.settings import STARLINK_PRICE_PER_GB, STARLINK_MAX_VOLUME_GB
from keyboards.user_keyboards import (
    profile_keyboard,
    faq_questions_keyboard,
)
from services.banner_service import send_banner
from handlers.btn_filter import Btn


router = Router()


BOT_USERNAME = os.getenv("BOT_USERNAME", "YOUR_BOT_USERNAME")


def rows_to_dicts(cursor, rows):
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def get_user_subscriptions(telegram_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM subscriptions
    WHERE telegram_id = ?
    ORDER BY id DESC
    """, (telegram_id,))

    rows = cursor.fetchall()
    data = rows_to_dicts(cursor, rows)

    conn.close()
    return data


def get_user_orders(telegram_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM orders
    WHERE telegram_id = ?
    ORDER BY id DESC
    LIMIT 5
    """, (telegram_id,))

    rows = cursor.fetchall()
    data = rows_to_dicts(cursor, rows)

    conn.close()
    return data


def get_active_faqs():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM faq_items
    WHERE is_active = 1
    ORDER BY sort_order ASC, id ASC
    """)

    rows = cursor.fetchall()
    data = rows_to_dicts(cursor, rows)

    conn.close()
    return data


def get_faq_by_id(faq_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM faq_items
    WHERE id = ? AND is_active = 1
    """, (faq_id,))

    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    data = rows_to_dicts(cursor, [row])[0]

    conn.close()
    return data


@router.message(Btn("btn_guide", "📘 راهنمای اتصال", "راهنمای اتصال"))
async def channels_list_handler(message: Message):
    await send_content_page(
        message=message,
        key="channels_list",
        fallback_text=(
            "📋 لیست راهنمای اتصال\n\n"
            "لیست راهنمای اتصال در این بخش نمایش داده می‌شود."
        )
    )
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    await message.answer(
        "برای بازگشت به منو دکمهٔ زیر را بزنید:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="u:menu")]
        ]),
    )


@router.message(F.text.in_(["پیگیری خرید", "🔎 پیگیری خرید"]))
async def track_purchase_handler(message: Message):
    orders = get_user_orders(message.from_user.id)

    if not orders:
        await send_banner(
            message,
            "tracking",
            caption=(
                "🔎 <b>پیگیری خرید</b>\n"
                "━━━━━━━━━━━━━━\n\n"
                "هنوز سفارشی برای شما ثبت نشده است. برای شروع، از بخش خرید کانفیگ سرویس موردنظر را انتخاب کنید."
            )
        )
        return

    text = "🔎 <b>آخرین سفارش‌های شما</b>\n━━━━━━━━━━━━━━\n\n"

    for order in orders:
        status = order["status"]

        if status == "pending":
            status_fa = "در انتظار پرداخت"
        elif status == "waiting_admin_review":
            status_fa = "در انتظار بررسی ادمین"
        elif status == "waiting_delivery":
            status_fa = "در انتظار تحویل اشتراک"
        elif status == "approved":
            status_fa = "تایید شده"
        elif status == "rejected":
            status_fa = "رد شده"
        else:
            status_fa = status

        final_price = (
            order["final_price_toman"] or
            order["price_toman"]
        )

        text += (
            f"🧾 سفارش #{order['id']}\n"
            f"سرویس: {order['service_name']}\n"
            f"پلن: {order['plan_title']}\n"
            f"مبلغ نهایی: {final_price:,} تومان\n"
            f"وضعیت: {status_fa}\n"
            f"تاریخ ثبت: {order['created_at']}\n\n"
        )

    await send_banner(message, "tracking", caption=text)


@router.message(F.text.in_(["حساب کاربری", "👤 حساب کاربری"]))
async def profile_handler(message: Message):
    user = message.from_user

    subscriptions = get_user_subscriptions(user.id)
    orders = get_user_orders(user.id)

    active_subs = [
        sub for sub in subscriptions
        if sub["status"] == "active"
    ]

    text = (
        "👑 پروفایل کاربری شما\n"
        "━━━━━━━━━━━━━━\n\n"
        f"👤 نام: {user.full_name}\n"
        f"🆔 آیدی عددی: <code>{user.id}</code>\n"
        f"🔗 یوزرنیم: @{user.username if user.username else 'ندارد'}\n\n"
        f"🔐 کانفیگ‌های فعال: {len(active_subs)}\n"
        f"🧾 سفارش‌های اخیر: {len(orders)}\n\n"
    )

    if active_subs:
        text += "✨ اشتراک‌های فعال شما:\n\n"

        for sub in active_subs[:5]:
            text += (
                f"💠 {sub['service_name']}\n"
                f"پلن: {sub['plan_title']}\n"
                f"مدت: {sub['duration_days']} روز\n"
                f"پایان اعتبار: {sub['expires_at']}\n\n"
            )
    else:
        text += (
            "فعلاً کانفیگ فعالی ندارید.\n"
            "برای شروع، از بخش خرید کانفیگ سرویس مناسب خودتان را انتخاب کنید.\n\n"
        )

    text += "🛟 برای تمدید، تغییر پلن یا مشکل اتصال، از پشتیبانی سریع پیام بفرستید."

    await send_banner(
        message,
        "profile",
        caption=text,
        reply_markup=profile_keyboard()
    )


@router.message(Btn("btn_referral", "🎁 دعوت دوستان", "دعوت دوستان"))
async def referral_handler(message: Message):
    user_id = message.from_user.id

    referral_count = get_referral_count(user_id)

    rewards = get_referral_rewards(
        user_id,
        limit=5
    )

    referral_link = (
        f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    )

    await send_content_page(
        message=message,
        key="referral",
        fallback_text=(
            "🎁 دعوت دوستان\n\n"
            "لینک دعوت اختصاصی خودتان را بفرستید. بعد از خرید موفق دوستتان، یک هدیه ویژه برای تمدید یا خرید بعدی شما ثبت می‌شود."
        )
    )

    text = (
        f"\n\n🔗 لینک دعوت اختصاصی شما:\n"
        f"{referral_link}\n\n"
        f"👥 تعداد دعوت‌شده‌ها: {referral_count}\n\n"
        "🎁 هدیه دعوت:\n"
        "بعد از خرید موفق فرد دعوت‌شده، پاداش شما در سوابق دعوت ثبت می‌شود و پشتیبانی برای اعمال هدیه راهنمایی‌تان می‌کند.\n\n"
    )

    if rewards:
        text += "آخرین پاداش‌های شما:\n\n"

        for reward in rewards:
            text += (
                f"سفارش #{reward['order_id']}\n"
                f"هدیه ثبت‌شده: {reward['bonus_days']} روز اعتبار ویژه\n\n"
            )

    await message.answer(text)


async def send_faq_list(message_or_callback):
    faqs = get_active_faqs()

    text = (
        "❓ <b>سوالات متداول WGV</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "پاسخ سوالات پرتکرار درباره خرید، پرداخت، تحویل کانفیگ و اتصال را از لیست زیر انتخاب کنید."
    )

    if not faqs:
        if isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.message.edit_text("فعلاً سوالی ثبت نشده است.")
            await message_or_callback.answer()
        else:
            await message_or_callback.answer("فعلاً سوالی ثبت نشده است.")
        return

    if isinstance(message_or_callback, CallbackQuery):
        try:
            await message_or_callback.message.edit_caption(caption=text, reply_markup=faq_questions_keyboard(faqs))
        except Exception:
            await message_or_callback.message.edit_text(text, reply_markup=faq_questions_keyboard(faqs))
        await message_or_callback.answer()
    else:
        await send_banner(message_or_callback, "faq", caption=text, reply_markup=faq_questions_keyboard(faqs))


@router.message(Btn("btn_faq", "❓ سوالات متداول", "سوالات متداول"))
async def faq_handler(message: Message):
    await send_faq_list(message)


@router.callback_query(F.data == "faq:list")
async def faq_list_callback(callback: CallbackQuery):
    await send_faq_list(callback)


@router.callback_query(F.data.startswith("faq:answer:"))
async def faq_answer_handler(callback: CallbackQuery):
    faq_id = int(callback.data.split(":")[2])
    faq = get_faq_by_id(faq_id)

    if not faq:
        await callback.answer("این سوال پیدا نشد.", show_alert=True)
        return

    text = (
        "💬 <b>پاسخ سوال</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        f"<b>{faq['question']}</b>\n\n"
        f"{faq['answer']}"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ بازگشت به سوالات", callback_data="faq:list")]
    ])

    try:
        await callback.message.edit_caption(caption=text, reply_markup=keyboard)
    except Exception:
        try:
            await callback.message.edit_text(text, reply_markup=keyboard)
        except Exception:
            await callback.message.answer(text, reply_markup=keyboard)

    await callback.answer()
