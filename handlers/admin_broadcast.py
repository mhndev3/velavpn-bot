import asyncio

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from config.settings import ADMIN_IDS
from database.db import get_connection
from keyboards.admin_keyboards import admin_broadcast_keyboard
from states.user_states import AdminBroadcastStates


router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def get_all_user_ids():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT telegram_id
    FROM users
    ORDER BY id ASC
    """)

    rows = cursor.fetchall()
    conn.close()

    return [row[0] for row in rows]


def parse_user_ids(text: str):
    if not text:
        return []

    parts = text.replace(",", " ").split()
    user_ids = []

    for part in parts:
        if part.strip().isdigit():
            user_ids.append(int(part.strip()))

    return user_ids


@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_home(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    await state.clear()

    await callback.message.edit_text(
        "📣 ارسال همگانی\n\n"
        "نوع ارسال را انتخاب کن:",
        reply_markup=admin_broadcast_keyboard()
    )

    await callback.answer()


@router.callback_query(F.data.startswith("broadcast:"))
async def broadcast_type_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    broadcast_type = callback.data.split(":")[1]

    await state.update_data(broadcast_type=broadcast_type)

    if broadcast_type == "all":
        await callback.message.edit_text(
            "📣 ارسال به همه کاربران\n\n"
            "پیام مورد نظر را ارسال کن.\n\n"
            "می‌تواند متن، عکس، فایل یا ویدیو باشد."
        )
        await state.set_state(AdminBroadcastStates.waiting_for_message)

    elif broadcast_type == "single":
        await callback.message.edit_text(
            "👤 ارسال به یک کاربر خاص\n\n"
            "آیدی عددی کاربر را ارسال کن:"
        )
        await state.set_state(AdminBroadcastStates.waiting_for_target)

    elif broadcast_type == "except_blacklist":
        await callback.message.edit_text(
            "🚫 ارسال به همه به‌جز لیست سیاه\n\n"
            "آیدی عددی کاربرهایی که نباید پیام بگیرند را ارسال کن.\n\n"
            "مثال:\n"
            "<code>123456 987654</code>\n\n"
            "یا با کاما:\n"
            "<code>123456,987654</code>"
        )
        await state.set_state(AdminBroadcastStates.waiting_for_blacklist)

    else:
        await callback.answer("نوع ارسال نامعتبر است.", show_alert=True)
        return

    await callback.answer()


@router.message(AdminBroadcastStates.waiting_for_target)
async def broadcast_target_handler(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return

    if not message.text or not message.text.strip().isdigit():
        await message.answer("آیدی عددی باید فقط عدد باشد.")
        return

    target_user_id = int(message.text.strip())

    await state.update_data(target_user_id=target_user_id)

    await message.answer(
        "حالا پیام مورد نظر را ارسال کن.\n\n"
        "می‌تواند متن، عکس، فایل یا ویدیو باشد."
    )

    await state.set_state(AdminBroadcastStates.waiting_for_message)


@router.message(AdminBroadcastStates.waiting_for_blacklist)
async def broadcast_blacklist_handler(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return

    blacklist = parse_user_ids(message.text)

    await state.update_data(blacklist=blacklist)

    await message.answer(
        f"تعداد افراد لیست سیاه: {len(blacklist)}\n\n"
        "حالا پیام مورد نظر را ارسال کن.\n\n"
        "می‌تواند متن، عکس، فایل یا ویدیو باشد."
    )

    await state.set_state(AdminBroadcastStates.waiting_for_message)


async def send_broadcast_message(bot, user_id: int, source_message: Message):
    if source_message.photo:
        await bot.send_photo(
            chat_id=user_id,
            photo=source_message.photo[-1].file_id,
            caption=source_message.caption
        )

    elif source_message.document:
        await bot.send_document(
            chat_id=user_id,
            document=source_message.document.file_id,
            caption=source_message.caption
        )

    elif source_message.video:
        await bot.send_video(
            chat_id=user_id,
            video=source_message.video.file_id,
            caption=source_message.caption
        )

    elif source_message.text:
        await bot.send_message(
            chat_id=user_id,
            text=source_message.text
        )

    else:
        await bot.copy_message(
            chat_id=user_id,
            from_chat_id=source_message.chat.id,
            message_id=source_message.message_id
        )


@router.message(AdminBroadcastStates.waiting_for_message)
async def broadcast_message_handler(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return

    data = await state.get_data()
    broadcast_type = data.get("broadcast_type")

    if broadcast_type == "all":
        user_ids = get_all_user_ids()

    elif broadcast_type == "single":
        user_ids = [data.get("target_user_id")]

    elif broadcast_type == "except_blacklist":
        blacklist = data.get("blacklist", [])
        user_ids = [
            user_id for user_id in get_all_user_ids()
            if user_id not in blacklist
        ]

    else:
        await message.answer("نوع ارسال نامعتبر است.")
        await state.clear()
        return

    if not user_ids:
        await message.answer("هیچ کاربری برای ارسال پیدا نشد.")
        await state.clear()
        return

    await message.answer(
        f"📣 ارسال شروع شد...\n\n"
        f"تعداد مقصد: {len(user_ids)}"
    )

    success = 0
    failed = 0

    for user_id in user_ids:
        try:
            await send_broadcast_message(
                bot=message.bot,
                user_id=user_id,
                source_message=message
            )
            success += 1

        except Exception:
            failed += 1

        await asyncio.sleep(0.05)

    await message.answer(
        "✅ ارسال همگانی تمام شد.\n\n"
        f"موفق: {success}\n"
        f"ناموفق: {failed}"
    )

    await state.clear()