from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def payment_review_keyboard(order_id: int, payment_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ تایید پرداخت",
            callback_data=f"admin_payment:approve:{order_id}:{payment_id}"
        )],
        [InlineKeyboardButton(
            text="❌ رد پرداخت",
            callback_data=f"admin_payment:reject:{order_id}:{payment_id}"
        )],
    ])


def admin_panel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 آمار کلی", callback_data="admin:stats")],
        [InlineKeyboardButton(text="🧾 سفارش‌های اخیر", callback_data="admin:orders")],
        [InlineKeyboardButton(text="⏳ پرداخت‌های در انتظار", callback_data="admin:pending_payments")],
        [InlineKeyboardButton(text="👥 کاربران اخیر", callback_data="admin:users")],
        [InlineKeyboardButton(text="📦 اشتراک‌های فعال", callback_data="admin:subscriptions")],
        [InlineKeyboardButton(text="🛍 مدیریت سرویس‌ها", callback_data="admin:services")],
        [InlineKeyboardButton(text="🎟 مدیریت کد تخفیف", callback_data="admin:discounts")],
        [InlineKeyboardButton(text="🎫 تیکت‌های پشتیبانی", callback_data="admin:tickets")],
        [InlineKeyboardButton(text="📣 ارسال همگانی", callback_data="admin:broadcast")],
        [InlineKeyboardButton(text="❓ مدیریت سوالات متداول", callback_data="admin:faq")],
        [InlineKeyboardButton(text="📝 مدیریت متن‌ها", callback_data="admin:content")],
    ])


def admin_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ بازگشت به پنل ادمین", callback_data="admin:home")]
    ])


def admin_services_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ افزودن سرویس", callback_data="admin_service:add")],
        [InlineKeyboardButton(text="✏️ ویرایش سرویس", callback_data="admin_service:edit")],
        [InlineKeyboardButton(text="🔄 فعال/غیرفعال سرویس", callback_data="admin_service:toggle")],
        [InlineKeyboardButton(text="➕ افزودن پلن برای سرویس", callback_data="admin_plan:add")],
        [InlineKeyboardButton(text="✏️ ویرایش پلن", callback_data="admin_plan:edit")],
        [InlineKeyboardButton(text="🔄 فعال/غیرفعال پلن", callback_data="admin_plan:toggle")],
        [InlineKeyboardButton(text="📋 لیست سرویس‌ها و پلن‌ها", callback_data="admin_service:list")],
        [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin:home")],
    ])


def service_category_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="V2Ray", callback_data="admin_service_category:v2ray")],
        [InlineKeyboardButton(text="L2TP", callback_data="admin_service_category:l2tp")],
        [InlineKeyboardButton(text="OpenVPN", callback_data="admin_service_category:openvpn")],
        [InlineKeyboardButton(text="استارلینک", callback_data="admin_service_category:starlink")],
        [InlineKeyboardButton(text="لغو", callback_data="admin_service:cancel")],
    ])


def service_type_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="تک‌کاربره", callback_data="admin_service_type:single")],
        [InlineKeyboardButton(text="چندکاربره / سازمانی", callback_data="admin_service_type:bulk")],
        [InlineKeyboardButton(text="حجم دلخواه", callback_data="admin_service_type:custom_volume")],
        [InlineKeyboardButton(text="لغو", callback_data="admin_service:cancel")],
    ])


def cancel_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="لغو عملیات", callback_data="admin_service:cancel")]
    ])


def admin_discounts_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ ساخت کد تخفیف", callback_data="admin_discount:add")],
        [InlineKeyboardButton(text="📋 مشاهده کدهای تخفیف", callback_data="admin_discount:list")],
        [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin:home")],
    ])


def discount_type_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="درصدی", callback_data="discount_type:percent")],
        [InlineKeyboardButton(text="مبلغ ثابت تومان", callback_data="discount_type:fixed_toman")],
        [InlineKeyboardButton(text="لغو", callback_data="admin_discount:cancel")],
    ])


def cancel_discount_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="لغو عملیات", callback_data="admin_discount:cancel")]
    ])


def ticket_admin_keyboard(ticket_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✍️ پاسخ به تیکت",
            callback_data=f"admin_ticket:reply:{ticket_id}"
        )],
        [InlineKeyboardButton(
            text="✅ بستن تیکت",
            callback_data=f"admin_ticket:close:{ticket_id}"
        )],
    ])


def admin_tickets_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 تیکت‌های باز", callback_data="admin_ticket:list_open")],
        [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin:home")],
    ])


def admin_broadcast_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 ارسال به همه کاربران", callback_data="broadcast:all")],
        [InlineKeyboardButton(text="👤 ارسال به یک کاربر خاص", callback_data="broadcast:single")],
        [InlineKeyboardButton(text="🚫 ارسال به همه به‌جز لیست سیاه", callback_data="broadcast:except_blacklist")],
        [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin:home")],
    ])


def admin_faq_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ افزودن سوال", callback_data="admin_faq:add")],
        [InlineKeyboardButton(text="📋 لیست سوالات", callback_data="admin_faq:list")],
        [InlineKeyboardButton(text="✏️ ویرایش سوال", callback_data="admin_faq:edit")],
        [InlineKeyboardButton(text="🗑 حذف سوال", callback_data="admin_faq:delete")],
        [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin:home")],
    ])