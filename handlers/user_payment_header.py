from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from config.settings import (
    ADMIN_REPORT_CHANNEL_ID,
    STARLINK_ADMIN_REPORT_CHANNEL_ID,
    CRYPTO_PAYMENT_TEXT,
    ADMIN_IDS,
    ADMIN_PAYMENT_USERNAME,
)

from database.db import get_connection, get_setting

from keyboards.user_keyboards import (
    toman_payment_keyboard,
)

from keyboards.admin_keyboards import payment_review_keyboard

from states.user_states import (
    PaymentStates,
    AdminPaymentStates,
)

from services.referral_service import (
    process_referral_reward,
)
from services.ui_service import send_screen
from services.price_service import payment_price_block
from services.xui_service import provision_account
from database.db import get_plan as db_get_plan


router = Router()


def rows_to_dicts(cursor, rows):
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def is_starlink_order(order: dict) -> bool:
    if not order:
        return False
    service_name = str(order.get("service_name") or "")
    plan_title = str(order.get("plan_title") or "")
    return "استارلینک" in service_name or "starlink" in service_name.lower() or "استارلینک" in plan_title


def get_report_channel_id(order: dict):
    if is_starlink_order(order):
        return STARLINK_ADMIN_REPORT_CHANNEL_ID or ADMIN_REPORT_CHANNEL_ID
    return ADMIN_REPORT_CHANNEL_ID


def get_report_targets(order: dict) -> list:
    channel_id = get_report_channel_id(order)
    if channel_id:
        return [channel_id]
    return list(ADMIN_IDS)


def admin_card_contact_text(order: dict, order_id: int) -> str:
    final_price = order["final_price_toman"] or order["price_toman"]
    card_info = get_setting("card_info", "شماره کارت تنظیم نشده — ادمین از تنظیمات بات وارد کنید")
    return (
        "💳 <b>پرداخت کارت‌به‌کارت</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "🧾 شماره سفارش: <code>" + str(order_id) + "</code>\n"
        "💰 مبلغ: <b>" + "{:,}".format(final_price) + " تومان</b>\n\n"
        "💳 اطلاعات کارت:\n<code>" + card_info + "</code>\n\n"
        "لطفاً مبلغ را واریز کرده و <b>رسید</b> (عکس یا شماره پیگیری) را اینجا ارسال کنید."
    )
