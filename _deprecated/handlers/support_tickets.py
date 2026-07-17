"""
handler تیکت — ساپورت
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from database.tickets import (
    create_ticket, get_user_tickets, get_ticket, add_ticket_message,
    close_ticket, get_ticket_messages, get_open_tickets
)
from database.db import save_user
from config.settings import ADMIN_IDS

router = Router()


def _btn(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


class TicketStates(StatesGroup):
    subject = State()
    description = State()


@router.message(F.text == "🛟 پشتیبانی سریع")
async def support_menu(msg: Message):
    """منوی ساپورت"""
    save_user(msg.from_user.id, msg.from_user.full_name, msg.from_user.username)
    
    tickets = get_user_tickets(msg.from_user.id)
    open_count = len([t for t in tickets if t["status"] in ("open", "pending")])
    
    text = (
        f"🛟 ساپورت\n\n"
        f"تیکت‌های شما: {len(tickets)}\n"
        f"تیکت‌های باز: {open_count}\n\n"
        f"گزینه رو انتخاب کن:"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [_btn("➕ تیکت جدید", "ticket:new")],
        [_btn("📋 تیکت‌های من", "ticket:list")],
        [_btn("⬅️ بازگشت", "user:menu")],
    ])
    
    await msg.answer(text, reply_markup=kb)


@router.callback_query(F.data == "ticket:new")
async def ticket_new(cb: CallbackQuery, state: FSMContext):
    """تیکت جدید"""
    await state.clear()
    await cb.message.edit_text(
        "➕ تیکت جدید\n\n"
        f"موضوع تیکت رو بفرست:"
    )
    await state.set_state(TicketStates.subject)
    await cb.answer()


@router.message(TicketStates.subject)
async def ticket_subject(msg: Message, state: FSMContext):
    """موضوع تیکت"""
    await state.update_data(subject=msg.text.strip())
    await msg.answer("توضیح مسئله رو بفرست:")
    await state.set_state(TicketStates.description)


@router.message(TicketStates.description)
async def ticket_description(msg: Message, state: FSMContext):
    """توضیح تیکت"""
    data = await state.get_data()
    subject = data.get("subject")
    
    ticket_id = create_ticket(
        telegram_id=msg.from_user.id,
        subject=subject,
        description=msg.text.strip()
    )
    
    await state.clear()
    await msg.answer(
        f"✅ تیکت ایجاد شد\n\n"
        f"شماره تیکت: #{ticket_id}\n"
        f"موضوع: {subject}\n\n"
        f"منتظر پاسخ ادمین باشید...",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [_btn("⬅️ بازگشت", "user:menu")]
        ])
    )
    
    # اطلاع ادمین
    for admin_id in ADMIN_IDS:
        try:
            await msg.bot.send_message(
                chat_id=admin_id,
                text=f"🔔 تیکت جدید\n\n"
                     f"##{ticket_id}\n"
                     f"کاربر: {msg.from_user.full_name}\n"
                     f"موضوع: {subject}\n"
                     f"توضیح: {msg.text.strip()}"
            )
        except:
            pass


@router.callback_query(F.data == "ticket:list")
async def ticket_list(cb: CallbackQuery):
    """لیست تیکت‌ها"""
    tickets = get_user_tickets(cb.from_user.id)
    
    if not tickets:
        await cb.answer("هنوز تیکتی ایجاد نکردی", show_alert=True)
        return
    
    text = "📋 تیکت‌های شما:\n\n"
    rows = []
    
    for ticket in tickets:
        status_icon = "🟢" if ticket["status"] == "open" else "⏳" if ticket["status"] == "pending" else "✅"
        text += f"{status_icon} #{ticket['id']} - {ticket['subject'][:30]}\n"
        rows.append([_btn(f"#{ticket['id']}", f"ticket:view:{ticket['id']}")])
    
    rows.append([_btn("⬅️ بازگشت", "user:menu")])
    
    await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


@router.callback_query(F.data.startswith("ticket:view:"))
async def ticket_view(cb: CallbackQuery):
    """نمایش تیکت"""
    ticket_id = int(cb.data.split(":")[2])
    ticket = get_ticket(ticket_id)
    
    if not ticket or ticket["telegram_id"] != cb.from_user.id:
        return await cb.answer("تیکتی پیدا نشد", show_alert=True)
    
    messages = get_ticket_messages(ticket_id)
    
    text = (
        f"#{ticket_id}\n"
        f"موضوع: {ticket['subject']}\n"
        f"وضعیت: {ticket['status']}\n\n"
        f"پیام‌ها:\n"
    )
    
    for msg in messages[-5:]:  # آخر 5 پیام
        sender = "👤 شما" if msg["sender_type"] == "user" else "👨‍💼 ادمین"
        text += f"\n{sender}: {msg['message_text']}\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [_btn("⬅️ بازگشت", "ticket:list")]
    ])
    
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()
