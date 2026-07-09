from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config.settings import ADMIN_IDS
from database.db import get_connection
from keyboards.admin_keyboards import (
    admin_panel_keyboard,
    admin_back_keyboard,
    admin_services_keyboard,
    service_category_keyboard,
    service_type_keyboard,
    cancel_admin_keyboard,
)
from states.user_states import AdminServiceStates


router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def rows_to_dicts(cursor, rows):
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def get_count(table_name: str, where: str = None):
    conn = get_connection()
    cursor = conn.cursor()

    query = f"SELECT COUNT(*) FROM {table_name}"

    if where:
        query += f" WHERE {where}"

    cursor.execute(query)
    count = cursor.fetchone()[0]

    conn.close()
    return count


def get_recent_orders(limit: int = 10):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM orders
    ORDER BY id DESC
    LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    orders = rows_to_dicts(cursor, rows)

    conn.close()
    return orders


def get_pending_payments(limit: int = 10):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT 
        payments.id AS payment_id,
        payments.order_id,
        payments.telegram_id,
        payments.payment_method,
        payments.status,
        payments.created_at,
        orders.service_name,
        orders.plan_title,
        orders.price_toman,
        orders.final_price_toman,
        orders.discount_code,
        orders.discount_amount
    FROM payments
    JOIN orders ON orders.id = payments.order_id
    WHERE payments.status = 'waiting_admin_review'
    ORDER BY payments.id DESC
    LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    payments = rows_to_dicts(cursor, rows)

    conn.close()
    return payments


def get_recent_users(limit: int = 10):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM users
    ORDER BY id DESC
    LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    users = rows_to_dicts(cursor, rows)

    conn.close()
    return users


def get_active_subscriptions(limit: int = 10):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM subscriptions
    WHERE status = 'active'
    ORDER BY id DESC
    LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    subscriptions = rows_to_dicts(cursor, rows)

    conn.close()
    return subscriptions


def get_services():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM services
    ORDER BY category ASC, service_type ASC, id DESC
    """)

    rows = cursor.fetchall()
    services = rows_to_dicts(cursor, rows)

    conn.close()
    return services


def get_service_by_id(service_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM services
    WHERE id = ?
    """, (service_id,))

    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    service = rows_to_dicts(cursor, [row])[0]
    conn.close()
    return service


def get_plan_by_id(plan_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT 
        plans.*,
        services.name AS service_name,
        services.category AS category,
        services.service_type AS service_type
    FROM plans
    LEFT JOIN services ON services.id = plans.service_id
    WHERE plans.id = ?
    """, (plan_id,))

    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    plan = rows_to_dicts(cursor, [row])[0]
    conn.close()
    return plan


def get_plans_for_service(service_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM plans
    WHERE service_id = ?
    ORDER BY duration_days ASC
    """, (service_id,))

    rows = cursor.fetchall()
    plans = rows_to_dicts(cursor, rows)

    conn.close()
    return plans


def create_service(
    category: str,
    service_type: str,
    name: str,
    description: str
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO services (
        category,
        service_type,
        name,
        description,
        is_active
    )
    VALUES (?, ?, ?, ?, ?)
    """, (
        category,
        service_type,
        name,
        description,
        1
    ))

    service_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return service_id


def update_service(service_id: int, name: str, description: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE services
    SET name = ?, description = ?
    WHERE id = ?
    """, (
        name,
        description,
        service_id
    ))

    conn.commit()
    conn.close()


def toggle_service(service_id: int):
    service = get_service_by_id(service_id)

    if not service:
        return None

    new_status = 0 if service["is_active"] else 1

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE services
    SET is_active = ?
    WHERE id = ?
    """, (
        new_status,
        service_id
    ))

    conn.commit()
    conn.close()

    return new_status


def create_plan(service_id: int, title: str, price_toman: int, duration_days: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO plans (
        service_id,
        title,
        price_toman,
        duration_days,
        is_active
    )
    VALUES (?, ?, ?, ?, ?)
    """, (
        service_id,
        title,
        price_toman,
        duration_days,
        1
    ))

    plan_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return plan_id


def update_plan(plan_id: int, title: str, price_toman: int, duration_days: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE plans
    SET title = ?, price_toman = ?, duration_days = ?
    WHERE id = ?
    """, (
        title,
        price_toman,
        duration_days,
        plan_id
    ))

    conn.commit()
    conn.close()


def toggle_plan(plan_id: int):
    plan = get_plan_by_id(plan_id)

    if not plan:
        return None

    new_status = 0 if plan["is_active"] else 1

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE plans
    SET is_active = ?
    WHERE id = ?
    """, (
        new_status,
        plan_id
    ))

    conn.commit()
    conn.close()

    return new_status


def status_to_fa(status: str) -> str:
    statuses = {
        "pending": "در انتظار پرداخت",
        "waiting_admin_review": "در انتظار بررسی ادمین",
        "waiting_delivery": "در انتظار تحویل اشتراک",
        "approved": "تایید شده",
        "rejected": "رد شده",
        "active": "فعال",
    }

    return statuses.get(status, status)


def category_to_fa(category: str) -> str:
    categories = {
        "v2ray": "V2Ray",
        "l2tp": "L2TP",
        "openvpn": "OpenVPN",
        "starlink": "استارلینک",
    }

    return categories.get(category, category)


def service_type_to_fa(service_type: str) -> str:
    types = {
        "single": "تک‌کاربره",
        "bulk": "چندکاربره / سازمانی",
        "custom_volume": "حجم دلخواه",
    }

    return types.get(service_type, service_type)


@router.message(F.text == "/admin")
async def admin_panel_command(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ شما دسترسی ادمین ندارید.")
        return

    await message.answer(
        "🛠 پنل مدیریت\n\n"
        "یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=admin_panel_keyboard()
    )


@router.callback_query(F.data == "admin:home")
async def admin_home_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    await callback.message.edit_text(
        "🛠 پنل مدیریت\n\n"
        "یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=admin_panel_keyboard()
    )

    await callback.answer()


@router.callback_query(F.data == "admin:stats")
async def admin_stats_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    users_count = get_count("users")
    orders_count = get_count("orders")
    payments_count = get_count("payments")
    pending_payments_count = get_count(
        "payments",
        "status = 'waiting_admin_review'"
    )
    approved_orders_count = get_count(
        "orders",
        "status = 'approved'"
    )
    active_subscriptions_count = get_count(
        "subscriptions",
        "status = 'active'"
    )
    services_count = get_count("services")
    bulk_services_count = get_count(
        "services",
        "service_type = 'bulk'"
    )
    plans_count = get_count("plans")

    text = (
        "📊 آمار کلی ربات\n\n"
        f"👥 تعداد کاربران: {users_count}\n"
        f"🧾 تعداد سفارش‌ها: {orders_count}\n"
        f"💳 تعداد پرداخت‌ها: {payments_count}\n"
        f"⏳ پرداخت‌های در انتظار: {pending_payments_count}\n"
        f"✅ سفارش‌های تایید شده: {approved_orders_count}\n"
        f"📦 اشتراک‌های فعال: {active_subscriptions_count}\n"
        f"🛍 تعداد سرویس‌ها: {services_count}\n"
        f"📦 سرویس‌های چندکاربره / سازمانی: {bulk_services_count}\n"
        f"💰 تعداد پلن‌ها: {plans_count}"
    )

    await callback.message.edit_text(
        text,
        reply_markup=admin_back_keyboard()
    )

    await callback.answer()


@router.callback_query(F.data == "admin:orders")
async def admin_orders_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    orders = get_recent_orders()

    if not orders:
        await callback.message.edit_text(
            "🧾 هنوز سفارشی ثبت نشده است.",
            reply_markup=admin_back_keyboard()
        )
        await callback.answer()
        return

    text = "🧾 سفارش‌های اخیر:\n\n"

    for order in orders:
        final_price = order["final_price_toman"] or order["price_toman"]

        text += (
            f"#{order['id']}\n"
            f"کاربر: <code>{order['telegram_id']}</code>\n"
            f"سرویس: {order['service_name']}\n"
            f"پلن: {order['plan_title']}\n"
            f"مبلغ اصلی: {order['price_toman']:,} تومان\n"
            f"مبلغ نهایی: {final_price:,} تومان\n"
            f"وضعیت: {status_to_fa(order['status'])}\n"
            f"تاریخ: {order['created_at']}\n\n"
        )

    await callback.message.edit_text(
        text,
        reply_markup=admin_back_keyboard()
    )

    await callback.answer()


@router.callback_query(F.data == "admin:pending_payments")
async def admin_pending_payments_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    payments = get_pending_payments()

    if not payments:
        await callback.message.edit_text(
            "⏳ پرداخت در انتظاری وجود ندارد.",
            reply_markup=admin_back_keyboard()
        )
        await callback.answer()
        return

    text = "⏳ پرداخت‌های در انتظار بررسی:\n\n"

    for payment in payments:
        final_price = payment["final_price_toman"] or payment["price_toman"]

        text += (
            f"پرداخت #{payment['payment_id']}\n"
            f"سفارش: #{payment['order_id']}\n"
            f"کاربر: <code>{payment['telegram_id']}</code>\n"
            f"روش: {payment['payment_method']}\n"
            f"سرویس: {payment['service_name']}\n"
            f"پلن: {payment['plan_title']}\n"
            f"مبلغ نهایی: {final_price:,} تومان\n"
            f"تاریخ: {payment['created_at']}\n\n"
        )

    await callback.message.edit_text(
        text,
        reply_markup=admin_back_keyboard()
    )

    await callback.answer()


@router.callback_query(F.data == "admin:users")
async def admin_users_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    users = get_recent_users()

    if not users:
        await callback.message.edit_text(
            "👥 هنوز کاربری ثبت نشده است.",
            reply_markup=admin_back_keyboard()
        )
        await callback.answer()
        return

    text = "👥 کاربران اخیر:\n\n"

    for user in users:
        username = f"@{user['username']}" if user["username"] else "ندارد"
        referrer = user["referrer_id"] if "referrer_id" in user else None

        text += (
            f"#{user['id']}\n"
            f"نام: {user['full_name']}\n"
            f"آیدی: <code>{user['telegram_id']}</code>\n"
            f"یوزرنیم: {username}\n"
            f"معرف: {referrer or 'ندارد'}\n"
            f"تاریخ عضویت: {user['created_at']}\n\n"
        )

    await callback.message.edit_text(
        text,
        reply_markup=admin_back_keyboard()
    )

    await callback.answer()


@router.callback_query(F.data == "admin:subscriptions")
async def admin_subscriptions_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    subscriptions = get_active_subscriptions()

    if not subscriptions:
        await callback.message.edit_text(
            "📦 اشتراک فعالی وجود ندارد.",
            reply_markup=admin_back_keyboard()
        )
        await callback.answer()
        return

    text = "📦 آخرین اشتراک‌های فعال:\n\n"

    for sub in subscriptions:
        text += (
            f"اشتراک #{sub['id']}\n"
            f"کاربر: <code>{sub['telegram_id']}</code>\n"
            f"سرویس: {sub['service_name']}\n"
            f"پلن: {sub['plan_title']}\n"
            f"مدت: {sub['duration_days']} روز\n"
            f"انقضا: {sub['expires_at']}\n\n"
        )

    await callback.message.edit_text(
        text,
        reply_markup=admin_back_keyboard()
    )

    await callback.answer()


@router.callback_query(F.data == "admin:services")
async def admin_services_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    await callback.message.edit_text(
        "🛍 مدیریت سرویس‌ها\n\n"
        "از این بخش سرویس‌ها و پلن‌ها را مدیریت کن.",
        reply_markup=admin_services_keyboard()
    )

    await callback.answer()


@router.callback_query(F.data == "admin_service:list")
async def admin_service_list_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    services = get_services()

    if not services:
        await callback.message.edit_text(
            "هنوز هیچ سرویسی ثبت نشده است.",
            reply_markup=admin_services_keyboard()
        )
        await callback.answer()
        return

    text = "📋 لیست سرویس‌ها:\n\n"

    for service in services:
        plans = get_plans_for_service(service["id"])

        text += (
            f"🆔 سرویس: {service['id']}\n"
            f"نام: {service['name']}\n"
            f"دسته: {category_to_fa(service['category'])}\n"
            f"نوع: {service_type_to_fa(service['service_type'])}\n"
            f"وضعیت: {'فعال' if service['is_active'] else 'غیرفعال'}\n"
            f"تعداد پلن‌ها: {len(plans)}\n"
        )

        if plans:
            text += "پلن‌ها:\n"
            for plan in plans:
                text += (
                    f"  🆔 {plan['id']} | "
                    f"{plan['title']} | "
                    f"{plan['price_toman']:,} تومان | "
                    f"{plan['duration_days']} روز | "
                    f"{'فعال' if plan['is_active'] else 'غیرفعال'}\n"
                )

        text += "\n"

    await callback.message.edit_text(
        text,
        reply_markup=admin_services_keyboard()
    )

    await callback.answer()


@router.callback_query(F.data == "admin_service:add")
async def admin_service_add_callback(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    await state.clear()

    await callback.message.edit_text(
        "➕ افزودن سرویس جدید\n\n"
        "اول دسته‌بندی سرویس را انتخاب کن:",
        reply_markup=service_category_keyboard()
    )

    await state.set_state(AdminServiceStates.waiting_for_category)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_service_category:"))
async def admin_service_category_callback(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    category = callback.data.split(":")[1]

    await state.update_data(category=category)

    await callback.message.edit_text(
        "نوع سرویس را انتخاب کن:",
        reply_markup=service_type_keyboard()
    )

    await state.set_state(AdminServiceStates.waiting_for_service_type)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_service_type:"))
async def admin_service_type_callback(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    service_type = callback.data.split(":")[1]

    if service_type not in ["single", "bulk"]:
        await callback.answer("نوع سرویس نامعتبر است.", show_alert=True)
        return

    await state.update_data(service_type=service_type)

    await callback.message.edit_text(
        "نام سرویس را ارسال کن.\n\n"
        "مثال:\n"
        "<code>سرویس سیگنال VIP بیت‌کوین</code>\n\n"
        "یا برای چندکاربره / سازمانی:\n"
        "<code>چندکاربره / سازمانی راهنمای اتصالی V2Ray</code>",
        reply_markup=cancel_admin_keyboard()
    )

    await state.set_state(AdminServiceStates.waiting_for_service_name)
    await callback.answer()


@router.message(AdminServiceStates.waiting_for_service_name)
async def admin_service_name_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return

    name = message.text.strip() if message.text else ""

    if len(name) < 2:
        await message.answer("نام سرویس خیلی کوتاهه.")
        return

    await state.update_data(name=name)

    await message.answer(
        "توضیحات سرویس را ارسال کن.\n\n"
        "این متن برای کاربر نمایش داده می‌شود."
    )

    await state.set_state(AdminServiceStates.waiting_for_service_description)


@router.message(AdminServiceStates.waiting_for_service_description)
async def admin_service_description_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return

    description = message.text or ""
    data = await state.get_data()

    service_id = create_service(
        category=data["category"],
        service_type=data["service_type"],
        name=data["name"],
        description=description
    )

    await message.answer(
        "✅ سرویس جدید ثبت شد.\n\n"
        f"آیدی سرویس: <code>{service_id}</code>\n"
        f"نام: {data['name']}\n"
        f"دسته: {category_to_fa(data['category'])}\n"
        f"نوع: {service_type_to_fa(data['service_type'])}",
        reply_markup=admin_services_keyboard()
    )

    await state.clear()


@router.callback_query(F.data == "admin_service:edit")
async def admin_service_edit_callback(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    services = get_services()

    if not services:
        await callback.message.edit_text(
            "هیچ سرویسی برای ویرایش وجود ندارد.",
            reply_markup=admin_services_keyboard()
        )
        await callback.answer()
        return

    text = "✏️ ویرایش سرویس\n\nآیدی سرویس مورد نظر را ارسال کن:\n\n"

    for service in services:
        text += (
            f"{service['id']} - {service['name']} | "
            f"{category_to_fa(service['category'])} | "
            f"{service_type_to_fa(service['service_type'])}\n"
        )

    await callback.message.edit_text(
        text,
        reply_markup=cancel_admin_keyboard()
    )

    await state.set_state(AdminServiceStates.waiting_for_edit_service_id)
    await callback.answer()


@router.message(AdminServiceStates.waiting_for_edit_service_id)
async def admin_edit_service_id_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return

    if not message.text or not message.text.strip().isdigit():
        await message.answer("فقط آیدی عددی سرویس را بفرست.")
        return

    service_id = int(message.text.strip())
    service = get_service_by_id(service_id)

    if not service:
        await message.answer("سرویسی با این آیدی پیدا نشد.")
        return

    await state.update_data(service_id=service_id)

    await message.answer(
        "نام جدید سرویس را ارسال کن.\n\n"
        f"نام فعلی:\n{service['name']}"
    )

    await state.set_state(AdminServiceStates.waiting_for_edit_service_name)


@router.message(AdminServiceStates.waiting_for_edit_service_name)
async def admin_edit_service_name_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return

    name = message.text.strip() if message.text else ""

    if len(name) < 2:
        await message.answer("نام سرویس خیلی کوتاهه.")
        return

    await state.update_data(name=name)

    await message.answer("توضیحات جدید سرویس را ارسال کن.")

    await state.set_state(AdminServiceStates.waiting_for_edit_service_description)


@router.message(AdminServiceStates.waiting_for_edit_service_description)
async def admin_edit_service_description_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return

    description = message.text or ""
    data = await state.get_data()

    update_service(
        service_id=data["service_id"],
        name=data["name"],
        description=description
    )

    await message.answer(
        "✅ سرویس با موفقیت ویرایش شد.",
        reply_markup=admin_services_keyboard()
    )

    await state.clear()


@router.callback_query(F.data == "admin_service:toggle")
async def admin_service_toggle_callback(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    services = get_services()

    if not services:
        await callback.message.edit_text(
            "هیچ سرویسی وجود ندارد.",
            reply_markup=admin_services_keyboard()
        )
        await callback.answer()
        return

    text = "🔄 فعال/غیرفعال سرویس\n\nآیدی سرویس را ارسال کن:\n\n"

    for service in services:
        text += (
            f"{service['id']} - {service['name']} | "
            f"{service_type_to_fa(service['service_type'])} | "
            f"{'فعال' if service['is_active'] else 'غیرفعال'}\n"
        )

    await callback.message.edit_text(
        text,
        reply_markup=cancel_admin_keyboard()
    )

    await state.set_state(AdminServiceStates.waiting_for_toggle_service_id)
    await callback.answer()


@router.message(AdminServiceStates.waiting_for_toggle_service_id)
async def admin_toggle_service_id_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return

    if not message.text or not message.text.strip().isdigit():
        await message.answer("فقط آیدی عددی سرویس را بفرست.")
        return

    service_id = int(message.text.strip())
    new_status = toggle_service(service_id)

    if new_status is None:
        await message.answer("سرویس پیدا نشد.")
        return

    await message.answer(
        f"✅ وضعیت سرویس تغییر کرد: {'فعال' if new_status else 'غیرفعال'}",
        reply_markup=admin_services_keyboard()
    )

    await state.clear()

@router.callback_query(F.data == "admin_plan:add")
async def admin_plan_add_callback(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    services = get_services()

    if not services:
        await callback.message.edit_text(
            "اول باید حداقل یک سرویس بسازی، بعد براش پلن تعریف کنی.",
            reply_markup=admin_services_keyboard()
        )
        await callback.answer()
        return

    text = (
        "➕ افزودن پلن\n\n"
        "آیدی سرویس مورد نظر را ارسال کن.\n\n"
        "لیست سرویس‌ها:\n\n"
    )

    for service in services:
        text += (
            f"{service['id']} - {service['name']} | "
            f"{category_to_fa(service['category'])} | "
            f"{service_type_to_fa(service['service_type'])}\n"
        )

    await callback.message.edit_text(
        text,
        reply_markup=cancel_admin_keyboard()
    )

    await state.set_state(AdminServiceStates.waiting_for_plan_service_id)
    await callback.answer()


@router.message(AdminServiceStates.waiting_for_plan_service_id)
async def admin_plan_service_id_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return

    if not message.text or not message.text.strip().isdigit():
        await message.answer("فقط آیدی عددی سرویس را بفرست.")
        return

    service_id = int(message.text.strip())
    service = get_service_by_id(service_id)

    if not service:
        await message.answer("سرویسی با این آیدی پیدا نشد.")
        return

    await state.update_data(service_id=service_id)

    await message.answer(
        "عنوان پلن را ارسال کن.\n\n"
        "مثال:\n"
        "<code>اشتراک 1 ماهه</code>"
    )

    await state.set_state(AdminServiceStates.waiting_for_plan_title)


@router.message(AdminServiceStates.waiting_for_plan_title)
async def admin_plan_title_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return

    title = message.text.strip() if message.text else ""

    if len(title) < 2:
        await message.answer("عنوان پلن خیلی کوتاهه.")
        return

    await state.update_data(title=title)

    await message.answer(
        "قیمت پلن را به تومان ارسال کن.\n\n"
        "مثال:\n"
        "<code>500000</code>"
    )

    await state.set_state(AdminServiceStates.waiting_for_plan_price)


@router.message(AdminServiceStates.waiting_for_plan_price)
async def admin_plan_price_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return

    if not message.text or not message.text.strip().isdigit():
        await message.answer("قیمت باید عددی باشد. کاما و حروف نذار، زندگی به قدر کافی سخت هست.")
        return

    price = int(message.text.strip())

    if price <= 0:
        await message.answer("قیمت باید بیشتر از صفر باشد.")
        return

    await state.update_data(price_toman=price)

    await message.answer(
        "مدت اشتراک را به روز ارسال کن.\n\n"
        "مثال:\n"
        "<code>30</code>"
    )

    await state.set_state(AdminServiceStates.waiting_for_plan_duration)


@router.message(AdminServiceStates.waiting_for_plan_duration)
async def admin_plan_duration_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return

    if not message.text or not message.text.strip().isdigit():
        await message.answer("مدت اشتراک باید عددی باشد.")
        return

    duration_days = int(message.text.strip())

    if duration_days <= 0:
        await message.answer("مدت اشتراک باید بیشتر از صفر باشد.")
        return

    data = await state.get_data()

    plan_id = create_plan(
        service_id=data["service_id"],
        title=data["title"],
        price_toman=data["price_toman"],
        duration_days=duration_days
    )

    service = get_service_by_id(data["service_id"])

    await message.answer(
        "✅ پلن جدید ثبت شد.\n\n"
        f"آیدی پلن: <code>{plan_id}</code>\n"
        f"آیدی سرویس: <code>{data['service_id']}</code>\n"
        f"سرویس: {service['name'] if service else '-'}\n"
        f"نوع سرویس: {service_type_to_fa(service['service_type']) if service else '-'}\n"
        f"عنوان: {data['title']}\n"
        f"قیمت: {data['price_toman']:,} تومان\n"
        f"مدت: {duration_days} روز",
        reply_markup=admin_services_keyboard()
    )

    await state.clear()


@router.callback_query(F.data == "admin_plan:edit")
async def admin_plan_edit_callback(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    services = get_services()

    text = "✏️ ویرایش پلن\n\nآیدی پلن مورد نظر را ارسال کن:\n\n"

    any_plan = False

    for service in services:
        plans = get_plans_for_service(service["id"])
        if plans:
            any_plan = True
            text += (
                f"سرویس: {service['name']} | "
                f"{service_type_to_fa(service['service_type'])}\n"
            )
            for plan in plans:
                text += (
                    f"{plan['id']} - {plan['title']} | "
                    f"{plan['price_toman']:,} تومان | "
                    f"{plan['duration_days']} روز\n"
                )
            text += "\n"

    if not any_plan:
        await callback.message.edit_text(
            "هیچ پلنی برای ویرایش وجود ندارد.",
            reply_markup=admin_services_keyboard()
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        text,
        reply_markup=cancel_admin_keyboard()
    )

    await state.set_state(AdminServiceStates.waiting_for_edit_plan_id)
    await callback.answer()


@router.message(AdminServiceStates.waiting_for_edit_plan_id)
async def admin_edit_plan_id_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return

    if not message.text or not message.text.strip().isdigit():
        await message.answer("فقط آیدی عددی پلن را بفرست.")
        return

    plan_id = int(message.text.strip())
    plan = get_plan_by_id(plan_id)

    if not plan:
        await message.answer("پلنی با این آیدی پیدا نشد.")
        return

    await state.update_data(plan_id=plan_id)

    await message.answer(
        "عنوان جدید پلن را ارسال کن.\n\n"
        f"عنوان فعلی:\n{plan['title']}"
    )

    await state.set_state(AdminServiceStates.waiting_for_edit_plan_title)


@router.message(AdminServiceStates.waiting_for_edit_plan_title)
async def admin_edit_plan_title_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return

    title = message.text.strip() if message.text else ""

    if len(title) < 2:
        await message.answer("عنوان پلن خیلی کوتاهه.")
        return

    await state.update_data(title=title)

    await message.answer("قیمت جدید را به تومان ارسال کن.")

    await state.set_state(AdminServiceStates.waiting_for_edit_plan_price)


@router.message(AdminServiceStates.waiting_for_edit_plan_price)
async def admin_edit_plan_price_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return

    if not message.text or not message.text.strip().isdigit():
        await message.answer("قیمت باید عددی باشد.")
        return

    price = int(message.text.strip())

    if price <= 0:
        await message.answer("قیمت باید بیشتر از صفر باشد.")
        return

    await state.update_data(price_toman=price)

    await message.answer("مدت جدید اشتراک را به روز ارسال کن.")

    await state.set_state(AdminServiceStates.waiting_for_edit_plan_duration)


@router.message(AdminServiceStates.waiting_for_edit_plan_duration)
async def admin_edit_plan_duration_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return

    if not message.text or not message.text.strip().isdigit():
        await message.answer("مدت باید عددی باشد.")
        return

    duration_days = int(message.text.strip())

    if duration_days <= 0:
        await message.answer("مدت باید بیشتر از صفر باشد.")
        return

    data = await state.get_data()

    update_plan(
        plan_id=data["plan_id"],
        title=data["title"],
        price_toman=data["price_toman"],
        duration_days=duration_days
    )

    await message.answer(
        "✅ پلن با موفقیت ویرایش شد.",
        reply_markup=admin_services_keyboard()
    )

    await state.clear()


@router.callback_query(F.data == "admin_plan:toggle")
async def admin_plan_toggle_callback(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    services = get_services()

    text = "🔄 فعال/غیرفعال پلن\n\nآیدی پلن را ارسال کن:\n\n"

    any_plan = False

    for service in services:
        plans = get_plans_for_service(service["id"])
        if plans:
            any_plan = True
            text += (
                f"سرویس: {service['name']} | "
                f"{service_type_to_fa(service['service_type'])}\n"
            )
            for plan in plans:
                text += (
                    f"{plan['id']} - {plan['title']} | "
                    f"{'فعال' if plan['is_active'] else 'غیرفعال'}\n"
                )
            text += "\n"

    if not any_plan:
        await callback.message.edit_text(
            "هیچ پلنی وجود ندارد.",
            reply_markup=admin_services_keyboard()
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        text,
        reply_markup=cancel_admin_keyboard()
    )

    await state.set_state(AdminServiceStates.waiting_for_toggle_plan_id)
    await callback.answer()


@router.message(AdminServiceStates.waiting_for_toggle_plan_id)
async def admin_toggle_plan_id_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return

    if not message.text or not message.text.strip().isdigit():
        await message.answer("فقط آیدی عددی پلن را بفرست.")
        return

    plan_id = int(message.text.strip())
    new_status = toggle_plan(plan_id)

    if new_status is None:
        await message.answer("پلن پیدا نشد.")
        return

    await message.answer(
        f"✅ وضعیت پلن تغییر کرد: {'فعال' if new_status else 'غیرفعال'}",
        reply_markup=admin_services_keyboard()
    )

    await state.clear()


@router.callback_query(F.data == "admin_service:cancel")
async def admin_service_cancel_callback(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    await state.clear()

    await callback.message.edit_text(
        "عملیات لغو شد.",
        reply_markup=admin_services_keyboard()
    )

    await callback.answer()