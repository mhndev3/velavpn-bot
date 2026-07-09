"""
payment_plan_patch.py - FIX: update_order_payment_method رو حذف کردیم از قبل از wallet
تا connection قبل از X-UI باز نمونه
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from states.user_states import PaymentStates
from handlers.user_payment import (
    get_order,
    admin_card_contact_text, process_wallet_payment,
)

router = Router()


@router.callback_query(F.data.startswith("payment_method:"))
async def payment_method_handler_fixed(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    order_id = int(parts[1])
    method = parts[2]

    order = get_order(order_id)
    if not order:
        return await callback.answer("سفارش پیدا نشد.", show_alert=True)

    if method == "card":
        # فقط برای card: update method و ست state
        from handlers.user_payment import update_order_payment_method
        update_order_payment_method(order_id, "card")
        await state.set_state(PaymentStates.waiting_for_card_receipt)
        await state.update_data(order_id=order_id, payment_method="card")
        await callback.message.answer(admin_card_contact_text(order, order_id))
        await callback.answer()

    elif method == "wallet":
        # wallet: بدون هیچ DB write قبلی — همه داخل process_wallet_payment
        await callback.answer("⏳ در حال پردازش...", show_alert=False)
        await process_wallet_payment(
            callback.message, callback.from_user.id, order_id, state
        )

    else:
        await callback.answer("روش پرداخت نامعتبر است.", show_alert=True)
