from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from keyboards.user_keyboards import main_menu_keyboard_for
from services.ui_service import send_screen


router = Router()


@router.callback_query(F.data == "close:menu")
async def close_menu_handler(callback: CallbackQuery):
    await send_screen(callback, None, "❌ منو بسته شد.")


@router.callback_query(F.data == "back:main")
async def back_main_handler(callback: CallbackQuery):
    await send_screen(
        callback,
        None,
        "🏠 <b>منوی اصلی WGV</b>\n━━━━━━━━━━━━━━\n\nگزینه موردنظر خود را انتخاب کنید.",
        reply_markup=main_menu_keyboard_for(callback.from_user.id),
        banner_key="start_message",
    )


@router.message(F.text == "❌ لغو عملیات")
async def cancel_operation_handler(
    message: Message,
    state: FSMContext
):
    await state.clear()

    await message.answer(
        "❌ عملیات لغو شد.\n\n"
        "به منوی اصلی برگشتید.",
        reply_markup=main_menu_keyboard_for(message.from_user.id)
    )