from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from config.settings import ADMIN_IDS
from database.db import get_connection
from keyboards.admin_keyboards import admin_tickets_keyboard, admin_back_keyboard, ticket_admin_keyboard
from states.user_states import AdminTicketStates


router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def rows_to_dicts(cursor, rows):
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def get_open_tickets(limit: int = 20):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT *
    FROM tickets
    WHERE status = 'open'
    ORDER BY id DESC
    LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    tickets = rows_to_dicts(cursor, rows)
    conn.close()
    return tickets


def get_ticket(ticket_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    ticket = rows_to_dicts(cursor, [row])[0]
    conn.close()
    return ticket


def get_ticket_messages(ticket_id: int, limit: int = 10):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT *
    FROM ticket_messages
    WHERE ticket_id = ?
    ORDER BY id ASC
    LIMIT ?
    """, (ticket_id, limit))
    rows = cursor.fetchall()
    messages = rows_to_dicts(cursor, rows)
    conn.close()
    return messages


def save_admin_ticket_message(ticket_id: int, admin_id: int, text: str):
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
    ) VALUES (?, 'admin', ?, ?, NULL, NULL)
    """, (ticket_id, admin_id, text))
    conn.commit()
    conn.close()


def close_ticket(ticket_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE tickets
    SET status = 'closed', closed_at = CURRENT_TIMESTAMP
    WHERE id = ?
    """, (ticket_id,))
    conn.commit()
    conn.close()


def ticket_list_keyboard(tickets: list):
    keyboard = []
    for ticket in tickets:
        keyboard.append([
            InlineKeyboardButton(
                text=f"🎫 #{ticket['id']} | {ticket['subject'][:28]}",
                callback_data=f"admin_ticket:view:{ticket['id']}"
            )
        ])
    keyboard.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.callback_query(F.data == "admin:tickets")
async def admin_tickets_home(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    await state.clear()
    await callback.message.edit_text(
        "🎫 پنل تیکت‌های پشتیبانی\n\n"
        "برای مشاهده و پاسخ‌دادن به تیکت‌های باز، گزینه زیر را انتخاب کنید.",
        reply_markup=admin_tickets_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_ticket:list_open")
async def admin_ticket_list_open(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    tickets = get_open_tickets()
    if not tickets:
        await callback.message.edit_text(
            "🎫 تیکت باز وجود ندارد.",
            reply_markup=admin_tickets_keyboard()
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "📋 تیکت‌های باز\n\n"
        "یکی از تیکت‌ها را برای مشاهده، پاسخ یا بستن انتخاب کنید:",
        reply_markup=ticket_list_keyboard(tickets)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_ticket:view:"))
async def admin_ticket_view(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[2])
    ticket = get_ticket(ticket_id)
    if not ticket:
        await callback.answer("تیکت پیدا نشد.", show_alert=True)
        return

    messages = get_ticket_messages(ticket_id)
    history = ""
    for item in messages[-5:]:
        sender = "کاربر" if item["sender_type"] == "user" else "ادمین"
        history += f"{sender}: {item['message_text'] or 'بدون متن'}\n\n"

    text = (
        f"🎫 تیکت #{ticket_id}\n"
        "━━━━━━━━━━━━━━\n\n"
        f"کاربر: <code>{ticket['telegram_id']}</code>\n"
        f"موضوع: {ticket['subject']}\n"
        f"وضعیت: {'باز' if ticket['status'] == 'open' else 'بسته'}\n\n"
        "آخرین پیام‌ها:\n"
        f"{history or 'پیامی ثبت نشده است.'}"
    )

    await callback.message.edit_text(text, reply_markup=ticket_admin_keyboard(ticket_id))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_ticket:reply:"))
async def admin_ticket_reply_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[2])
    ticket = get_ticket(ticket_id)
    if not ticket or ticket["status"] != "open":
        await callback.answer("این تیکت باز نیست یا پیدا نشد.", show_alert=True)
        return

    await state.update_data(reply_ticket_id=ticket_id)
    await callback.message.answer(
        f"✍️ پاسخ تیکت #{ticket_id}\n\n"
        "متن پاسخ را ارسال کنید. پاسخ مستقیم برای کاربر فرستاده می‌شود."
    )
    await state.set_state(AdminTicketStates.waiting_for_reply)
    await callback.answer()


@router.message(AdminTicketStates.waiting_for_reply)
async def admin_ticket_reply_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return

    data = await state.get_data()
    ticket_id = data.get("reply_ticket_id")
    ticket = get_ticket(int(ticket_id)) if ticket_id else None

    if not ticket:
        await message.answer("تیکت پیدا نشد.")
        await state.clear()
        return

    reply_text = message.text or message.caption or ""
    if len(reply_text.strip()) < 2:
        await message.answer("متن پاسخ خیلی کوتاه است.")
        return

    save_admin_ticket_message(
        ticket_id=int(ticket_id),
        admin_id=message.from_user.id,
        text=reply_text.strip()
    )

    await message.bot.send_message(
        chat_id=ticket["telegram_id"],
        text=(
            f"🛟 پاسخ پشتیبانی WGV برای تیکت #{ticket_id}\n"
            "━━━━━━━━━━━━━━\n\n"
            f"{reply_text.strip()}\n\n"
            "در صورت نیاز می‌توانید دوباره از بخش پشتیبانی سریع پیام ارسال کنید."
        )
    )

    await message.answer(
        f"✅ پاسخ برای کاربر ارسال شد.\n\nتیکت #{ticket_id}",
        reply_markup=admin_back_keyboard()
    )
    await state.clear()


@router.callback_query(F.data.startswith("admin_ticket:close:"))
async def admin_ticket_close(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[2])
    ticket = get_ticket(ticket_id)
    if not ticket:
        await callback.answer("تیکت پیدا نشد.", show_alert=True)
        return

    close_ticket(ticket_id)

    try:
        await callback.bot.send_message(
            chat_id=ticket["telegram_id"],
            text=(
                f"✅ تیکت #{ticket_id} بسته شد.\n\n"
                "اگر هنوز مشکلی باقی مانده، از بخش پشتیبانی سریع یک تیکت جدید ثبت کنید."
            )
        )
    except Exception:
        pass

    await callback.message.answer(
        f"✅ تیکت #{ticket_id} بسته شد.",
        reply_markup=admin_tickets_keyboard()
    )
    await callback.answer()
