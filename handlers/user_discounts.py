from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from database.db import get_connection
from keyboards.user_keyboards import (
    payment_methods_keyboard,
    payment_methods_keyboard_with_discount,
    toman_payment_keyboard,
)
from states.user_states import UserDiscountStates
from services.ui_service import send_screen
from services.price_service import payment_price_block


router = Router()


def rows_to_dicts(cursor, rows):
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def get_plan(plan_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT 
        plans.id,
        plans.service_id,
        plans.title,
        plans.price_toman,
        plans.duration_days,
        services.name AS service_name,
        services.category AS category
    FROM plans
    JOIN services ON services.id = plans.service_id
    WHERE plans.id = ? AND plans.is_active = 1
    """, (plan_id,))

    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    plan = rows_to_dicts(cursor, [row])[0]
    conn.close()
    return plan


def get_discount_by_code(code: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM discount_codes
    WHERE code = ? AND is_active = 1
    """, (code.upper(),))

    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    discount = rows_to_dicts(cursor, [row])[0]
    conn.close()
    return discount


def is_discount_valid(discount: dict):
    if not discount:
        return False, T("disc_err_notfound", "کد تخفیف پیدا نشد.")

    if discount["used_count"] >= discount["max_uses"]:
        return False, T("disc_err_capacity", "ظرفیت استفاده از این کد تخفیف تمام شده است.")

    expires_at = datetime.strptime(discount["expires_at"], "%Y-%m-%d %H:%M:%S")

    if expires_at < datetime.now():
        return False, T("disc_err_expired", "این کد تخفیف منقضی شده است.")

    return True, None


def calculate_discount(price: int, discount: dict):
    if discount["discount_type"] == "percent":
        discount_amount = int(price * discount["amount"] / 100)
    else:
        discount_amount = int(discount["amount"])

    if discount_amount > price:
        discount_amount = price

    final_price = price - discount_amount

    return discount_amount, final_price


def create_discounted_order(
    telegram_id: int,
    plan: dict,
    discount: dict,
    discount_amount: int,
    final_price: int
):
    from database.db import get_sub_admin
    sub_admin = get_sub_admin(telegram_id)
    sub_admin_id = sub_admin["id"] if sub_admin else None

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO orders (
        telegram_id,
        plan_id,
        service_name,
        plan_title,
        price_toman,
        duration_days,
        payment_method,
        status,
        discount_code,
        discount_amount,
        final_price_toman,
        sub_admin_id,
        referral_processed
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        telegram_id,
        plan["id"],
        plan["service_name"],
        plan["title"],
        plan["price_toman"],
        plan["duration_days"],
        None,
        "pending",
        discount["code"],
        discount_amount,
        final_price,
        sub_admin_id,
        0
    ))

    order_id = cursor.lastrowid

    cursor.execute("""
    UPDATE discount_codes
    SET used_count = used_count + 1
    WHERE id = ?
    """, (discount["id"],))

    cursor.execute("""
    INSERT INTO discount_usages (
        discount_code_id,
        telegram_id,
        order_id
    )
    VALUES (?, ?, ?)
    """, (
        discount["id"],
        telegram_id,
        order_id
    ))

    conn.commit()
    conn.close()

    return order_id


@router.callback_query(F.data.startswith("user_discount:none:"))
async def no_discount_callback(callback: CallbackQuery, state: FSMContext):
    plan_id = int(callback.data.split(":")[2])

    await send_screen(
        callback,
        state,
        "💳 <b>انتخاب روش پرداخت</b>\n━━━━━━━━━━━━━━\n\nلطفاً روش پرداخت سفارش خود را انتخاب کنید. پس از تایید رسید، کانفیگ اختصاصی شما ارسال می‌شود.",
        reply_markup=payment_methods_keyboard(plan_id),
        banner_key="payment",
    )


@router.callback_query(F.data.startswith("user_discount:have:"))
async def have_discount_callback(callback: CallbackQuery, state: FSMContext):
    plan_id = int(callback.data.split(":")[2])

    await state.update_data(plan_id=plan_id)

    from services.ui_texts import T
    await send_screen(
        callback,
        state,
        T("pay_discount_ask", "🎟 <b>اعمال کد تخفیف</b>\n━━━━━━━━━━━━━━\n\nلطفاً کد تخفیف خود را ارسال کنید تا مبلغ نهایی سفارش محاسبه شود."),
        banner_key="payment",
        back_to="u:menu",
    )

    await state.set_state(UserDiscountStates.waiting_for_discount_code)


async def _legacy_user_discount_code_message(message: Message, state: FSMContext):
    code = message.text.strip().upper() if message.text else ""
    data = await state.get_data()

    plan_id = data.get("plan_id")
    plan = get_plan(plan_id)

    if not plan:
        await message.answer("پلن پیدا نشد.")
        await state.clear()
        return

    discount = get_discount_by_code(code)
    is_valid, error = is_discount_valid(discount)

    if not is_valid:
        await message.answer(
            f"❌ {error}\n\n"
            "می‌توانید دوباره کد را ارسال کنید یا از اول خرید را بدون کد ادامه دهید."
        )
        return

    from database.sub_admin_pricing import get_price_for_user
    base_price = get_price_for_user(message.from_user.id, plan_id)

    discount_amount, final_price = calculate_discount(
        price=base_price,
        discount=discount
    )

    text = (
        "✅ کد تخفیف اعمال شد\n\n"
        f"سرویس: {plan['service_name']}\n"
        f"پلن: {plan['title']}\n"
        f"قیمت پایه: {base_price:,} تومان\n"
        f"مبلغ تخفیف: {discount_amount:,} تومان\n"
        f"{payment_price_block(final_price)}\n\n"
        "لطفاً روش پرداخت را انتخاب کنید:"
    )

    await send_screen(
        message,
        state,
        text,
        reply_markup=payment_methods_keyboard_with_discount(
            plan_id=plan_id,
            discount_code=discount["code"]
        ),
        banner_key="payment",
    )

    await state.clear()


@router.callback_query(F.data.startswith("payment_currency_discount:"))
async def payment_currency_discount_callback(callback: CallbackQuery, state: FSMContext):
    _, plan_id_raw, currency, discount_code = callback.data.split(":")
    plan_id = int(plan_id_raw)

    plan = get_plan(plan_id)
    discount = get_discount_by_code(discount_code)

    if not plan:
        await callback.answer("پلن پیدا نشد.", show_alert=True)
        return

    is_valid, error = is_discount_valid(discount)

    if not is_valid:
        await callback.answer(error, show_alert=True)
        return

    from database.sub_admin_pricing import get_price_for_user
    base_price = get_price_for_user(callback.from_user.id, plan_id)

    discount_amount, final_price = calculate_discount(
        price=base_price,
        discount=discount
    )

    order_id = create_discounted_order(
        telegram_id=callback.from_user.id,
        plan=plan,
        discount=discount,
        discount_amount=discount_amount,
        final_price=final_price
    )

    if currency == "wallet":
        from handlers.user_payment import process_wallet_payment
        await process_wallet_payment(callback.message, callback.from_user.id, order_id, state)
        await callback.answer()
        return

    text = (
        "🧾 سفارش شما ثبت شد\n\n"
        f"شماره سفارش: <code>{order_id}</code>\n"
        f"سرویس: {plan['service_name']}\n"
        f"پلن: {plan['title']}\n"
        f"قیمت پایه: {base_price:,} تومان\n"
        f"کد تخفیف: <code>{discount['code']}</code>\n"
        f"مبلغ تخفیف: {discount_amount:,} تومان\n"
        f"{payment_price_block(final_price)}\n\n"
        "لطفاً روش پرداخت را انتخاب کنید:"
    )

    if currency == "toman":
        await send_screen(callback, state, text, reply_markup=toman_payment_keyboard(order_id), banner_key="payment")
    else:
        await callback.answer("روش پرداخت نامعتبر است.", show_alert=True)
        return

# ═══════════════════════════════════════════════════════════
# سیستم کد تخفیف order-based (جریان خرید فعلی)
# صفحهٔ «کد تخفیف دارم / ادامه بدون کد» پیش از انتخاب روش پرداخت
# ═══════════════════════════════════════════════════════════
from services.ui_texts import T as _T


def _get_order_row(order_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    row = cur.fetchone()
    cols = [c[0] for c in cur.description] if row else []
    conn.close()
    return dict(zip(cols, row)) if row else None


@router.callback_query(F.data.startswith("disc:none:"))
async def disc_none_callback(callback: CallbackQuery, state: FSMContext):
    """ادامه بدون کد تخفیف → مستقیم به انتخاب روش پرداخت."""
    from keyboards.user_keyboards import payment_methods_for_order_keyboard
    order_id = int(callback.data.split(":")[2])
    await state.clear()
    text = _T("disc_pay_title", "💳 روش پرداخت را انتخاب کنید:")
    try:
        await callback.message.edit_text(text, reply_markup=payment_methods_for_order_keyboard(order_id))
    except Exception:
        await callback.message.answer(text, reply_markup=payment_methods_for_order_keyboard(order_id))
    await callback.answer()


@router.callback_query(F.data.startswith("disc:have:"))
async def disc_have_callback(callback: CallbackQuery, state: FSMContext):
    """کد تخفیف دارم → درخواست ارسال کد."""
    order_id = int(callback.data.split(":")[2])
    await state.update_data(disc_order_id=order_id)
    await state.set_state(UserDiscountStates.waiting_for_discount_code)
    text = _T("disc_ask", "🎟 کد تخفیف خود را ارسال کنید:")
    try:
        await callback.message.edit_text(text)
    except Exception:
        await callback.message.answer(text)
    await callback.answer()


@router.message(UserDiscountStates.waiting_for_discount_code)
async def disc_code_received(message: Message, state: FSMContext):
    """کد تخفیف دریافت شد → اعتبارسنجی و اعمال روی order."""
    from keyboards.user_keyboards import payment_methods_for_order_keyboard
    data = await state.get_data()
    order_id = data.get("disc_order_id")
    if not order_id:
        # اگر order_id نبود، این پیام مربوط به سیستم قدیمی است؛ رد کن
        return

    code = (message.text or "").strip().upper()
    order = _get_order_row(order_id)
    if not order:
        await state.clear()
        return await message.answer(_T("disc_order_gone", "سفارش پیدا نشد. لطفاً دوباره از خرید شروع کنید."))

    discount = get_discount_by_code(code)
    is_valid, error = is_discount_valid(discount)
    if not is_valid:
        return await message.answer(
            "❌ " + str(error) + "\n\n" +
            _T("disc_retry", "می‌توانید دوباره کد را بفرستید یا /start را بزنید.")
        )

    # قیمت پایه از خود سفارش (شامل تعداد)
    base_price = int(order.get("final_price_toman") or order.get("price_toman") or 0)
    discount_amount, final_price = calculate_discount(price=base_price, discount=discount)

    # اعمال روی سفارش
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE orders SET discount_code = ?, discount_amount = ?, final_price_toman = ? WHERE id = ?",
            (discount["code"], discount_amount, final_price, order_id),
        )
        cur.execute("UPDATE discount_codes SET used_count = used_count + 1 WHERE id = ?", (discount["id"],))
        cur.execute(
            "INSERT INTO discount_usages (discount_code_id, telegram_id, order_id) VALUES (?, ?, ?)",
            (discount["id"], message.from_user.id, order_id),
        )
        conn.commit()
    finally:
        conn.close()

    await state.clear()
    text = (
        _T("disc_applied_title", "✅ کد تخفیف اعمال شد") + "\n"
        "━━━━━━━━━━━━━━\n\n"
        + _T("disc_lbl_base", "قیمت پایه:") + " " + "{:,}".format(base_price) + " تومان\n"
        + _T("disc_lbl_off", "تخفیف:") + " " + "{:,}".format(discount_amount) + " تومان\n"
        + _T("disc_lbl_final", "مبلغ نهایی:") + " " + "{:,}".format(final_price) + " تومان\n\n"
        + _T("disc_pay_title", "💳 روش پرداخت را انتخاب کنید:")
    )
    await message.answer(text, reply_markup=payment_methods_for_order_keyboard(order_id))
