from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from config.settings import ADMIN_REPORT_CHANNEL_ID, ADMIN_IDS
from handlers.btn_filter import Btn


async def notify_admins(bot, text: str, **kwargs):
    """پیام به همه‌ی ادمین‌ها — بجای کانال"""
    targets = [ADMIN_REPORT_CHANNEL_ID] if ADMIN_REPORT_CHANNEL_ID else ADMIN_IDS
    for admin_id in targets:
        try:
            await bot.send_message(chat_id=admin_id, text=text, **kwargs)
        except Exception:
            pass
from database.db import get_connection
from keyboards.admin_keyboards import ticket_admin_keyboard
from states.user_states import TicketStates
from services.content_media_service import send_content_page


router = Router()


def create_ticket(telegram_id: int, subject: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO tickets (
        telegram_id,
        subject,
        status
    )
    VALUES (?, ?, ?)
    """, (
        telegram_id,
        subject,
        "open"
    ))

    ticket_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return ticket_id


def save_ticket_message(
    ticket_id: int,
    sender_type: str,
    sender_id: int,
    message_text: str = None,
    file_id: str = None,
    file_type: str = None
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO ticket_messages (
        ticket_id,
        sender_type,
        sender_id,
        message_text,
        file_id,
        file_type
    )
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        ticket_id,
        sender_type,
        sender_id,
        message_text,
        file_id,
        file_type
    ))

    conn.commit()
    conn.close()


@router.message(Btn("btn_support", "🛟 پشتیبانی", "🛟 پشتیبانی سریع", "ارتباط با پشتیبانی"))
async def support_handler(message: Message, state: FSMContext):
    await state.clear()

    await send_content_page(
        message=message,
        key="support",
        fallback_text=(
            "🛟 پشتیبانی سریع WGV\n"
            "━━━━━━━━━━━━━━\n\n"
            "برای پیگیری خرید، مشکل اتصال، تمدید یا راهنمای نصب همینجا تیکت ثبت کنید.\n"
            "شماره سفارش، مدل دستگاه و اسکرین‌شات خطا را بفرستید تا بررسی دقیق‌تر انجام شود."
        )
    )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    await message.answer(
        "موضوع تیکت را کوتاه و واضح ارسال کنید؛ مثلاً: مشکل اتصال V2Ray یا پیگیری سفارش.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="u:menu")]
        ]),
    )

    await state.set_state(TicketStates.waiting_for_subject)


@router.message(TicketStates.waiting_for_subject)
async def ticket_subject_handler(message: Message, state: FSMContext):
    subject = message.text.strip() if message.text else ""

    if len(subject) < 2:
        await message.answer(
            "موضوع تیکت خیلی کوتاهه. یه عنوان درست بفرست."
        )
        return

    await state.update_data(subject=subject)

    await message.answer(
        "متن پیام خود را ارسال کنید.\n\n"
        "می‌توانید متن، عکس، ویدیو یا فایل بفرستید."
    )

    await state.set_state(TicketStates.waiting_for_message)


@router.message(TicketStates.waiting_for_message)
async def ticket_message_handler(message: Message, state: FSMContext):
    data = await state.get_data()

    subject = data.get("subject", "بدون موضوع")

    file_id = None
    file_type = None
    message_text = message.caption or message.text or "بدون متن"

    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"

    elif message.document:
        file_id = message.document.file_id
        file_type = "document"

    elif message.video:
        file_id = message.video.file_id
        file_type = "video"

    ticket_id = create_ticket(
        telegram_id=message.from_user.id,
        subject=subject
    )

    save_ticket_message(
        ticket_id=ticket_id,
        sender_type="user",
        sender_id=message.from_user.id,
        message_text=message_text,
        file_id=file_id,
        file_type=file_type
    )

    await message.answer(
        "✅ تیکت شما ثبت شد.\n\n"
        f"شماره تیکت: <code>{ticket_id}</code>\n"
        "پشتیبانی به‌زودی پاسخ می‌دهد."
    )

    await send_ticket_to_admin(
        message=message,
        ticket_id=ticket_id,
        subject=subject,
        message_text=message_text,
        file_id=file_id,
        file_type=file_type
    )

    await state.clear()


async def send_ticket_to_admin(
    message: Message,
    ticket_id: int,
    subject: str,
    message_text: str,
    file_id: str = None,
    file_type: str = None
):
    targets = [ADMIN_REPORT_CHANNEL_ID] if ADMIN_REPORT_CHANNEL_ID else ADMIN_IDS
    if not targets:
        return

    user = message.from_user

    caption = (
        "🎫 تیکت جدید\n\n"
        f"شماره تیکت: <code>{ticket_id}</code>\n"
        f"موضوع: {subject}\n\n"
        f"کاربر: {user.full_name}\n"
        f"آیدی عددی: <code>{user.id}</code>\n"
        f"یوزرنیم: @{user.username if user.username else 'ندارد'}\n\n"
        f"پیام:\n{message_text}"
    )

    keyboard = ticket_admin_keyboard(ticket_id)

    for target_id in targets:
        try:
            if file_type == "photo" and file_id:
                await message.bot.send_photo(chat_id=target_id, photo=file_id, caption=caption, reply_markup=keyboard)
            elif file_type == "document" and file_id:
                await message.bot.send_document(chat_id=target_id, document=file_id, caption=caption, reply_markup=keyboard)
            elif file_type == "video" and file_id:
                await message.bot.send_video(chat_id=target_id, video=file_id, caption=caption, reply_markup=keyboard)
            else:
                await message.bot.send_message(chat_id=target_id, text=caption, reply_markup=keyboard)
        except Exception:
            pass