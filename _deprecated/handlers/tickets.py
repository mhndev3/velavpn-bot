"""
سیستم تیکت — ساپورت
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from database.db import get_connection

router = Router()


class TicketStates(StatesGroup):
    waiting_subject = State()
    waiting_message = State()


def _btn(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


@router.message(F.text == "🛟 پشتیبانی سریع")
async def support_start(msg: Message, state: FSMContext):
    """شروع تیکت جدید"""
    await state.clear()
    await msg.answer("📝 موضوع تیکت رو بفرست:")
    await state.set_state(TicketStates.waiting_subject)


@router.message(TicketStates.waiting_subject)
async def ticket_subject(msg: Message, state: FSMContext):
    await state.update_data(subject=msg.text.strip())
    await msg.answer("📨 پیام رو بفرست:")
    await state.set_state(TicketStates.waiting_message)


@router.message(TicketStates.waiting_message)
async def ticket_message(msg: Message, state: FSMContext):
    """ذخیره تیکت"""
    data = await state.get_data()
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tickets (telegram_id, subject, status) VALUES (?, ?, 'open')",
        (msg.from_user.id, data["subject"]),
    )
    ticket_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO ticket_messages (ticket_id, sender_type, sender_id, message_text) VALUES (?, 'user', ?, ?)",
        (ticket_id, msg.from_user.id, msg.text.strip()),
    )
    conn.commit()
    conn.close()
    
    await msg.answer(f"✅ تیکت ثبت شد\nشماره تیکت: #{ticket_id}\n\nتیم ساپورت بر روی آن است.")
    await state.clear()
