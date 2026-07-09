"""
بخش کیف‌پول در پنل هد ادمین — تایید/رد شارژ‌های کیف‌پول
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery

from config.settings import ADMIN_IDS
from database.wallet import get_pending_wallet_charges, get_wallet_charge, approve_wallet_charge, reject_wallet_charge
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

router = Router()


def _btn(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


def wallet_charges_kb(charges: list):
    rows = []
    for ch in charges:
        status_icon = "⏳" if ch["status"] == "waiting_admin_review" else "✅" if ch["status"] == "approved" else "❌"
        rows.append([_btn(
            f"{status_icon} #{ch['id']} | {ch['amount_toman']:,}T | {ch['telegram_id']}",
            f"ha:wallet_charge:{ch['id']}"
        )])
    rows.append([_btn("⬅️ بازگشت", "ha:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def wallet_charge_detail_kb(charge_id: int, status: str):
    if status != "waiting_admin_review":
        return InlineKeyboardMarkup(inline_keyboard=[[_btn("⬅️ بازگشت", "ha:wallet_charges")]])
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("✅ تایید", f"ha:wallet_approve:{charge_id}"), _btn("❌ رد", f"ha:wallet_reject:{charge_id}")],
        [_btn("⬅️ بازگشت", "ha:wallet_charges")],
    ])


@router.callback_query(F.data == "ha:wallet_charges")
async def ha_wallet_charges(cb: CallbackQuery):
    if not ADMIN_IDS or cb.from_user.id not in ADMIN_IDS:
        return
    charges = get_pending_wallet_charges(20)
    if not charges:
        return await cb.message.edit_text(
            "💳 شارژ‌های کیف‌پول\n\nهیچ درخواست شارژی در انتظار نیست.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[_btn("⬅️ بازگشت", "ha:home")]])
        )
    text = f"💳 درخواست‌های شارژ کیف‌پول ({len(charges)}):\n\nروی یکی کلیک کن:"
    await cb.message.edit_text(text, reply_markup=wallet_charges_kb(charges))
    await cb.answer()


@router.callback_query(F.data.startswith("ha:wallet_charge:"))
async def ha_wallet_charge_detail(cb: CallbackQuery):
    if not ADMIN_IDS or cb.from_user.id not in ADMIN_IDS:
        return
    charge_id = int(cb.data.split(":")[2])
    charge = get_wallet_charge(charge_id)
    if not charge:
        return await cb.answer("شارژ پیدا نشد", show_alert=True)
    
    status_text = "⏳ در انتظار" if charge["status"] == "waiting_admin_review" else "✅ تایید شد" if charge["status"] == "approved" else "❌ رد شد"
    text = (
        f"💳 درخواست شارژ #{charge_id}\n\n"
        f"کاربر آیدی: <code>{charge['telegram_id']}</code>\n"
        f"مبلغ: {charge['amount_toman']:,} تومان\n"
        f"روش: {charge['payment_method']}\n"
        f"وضعیت: {status_text}\n\n"
        f"رسید:\n{charge['receipt_text']}\n"
    )
    await cb.message.edit_text(text, reply_markup=wallet_charge_detail_kb(charge_id, charge["status"]))
    await cb.answer()


@router.callback_query(F.data.startswith("ha:wallet_approve:"))
async def ha_wallet_approve(cb: CallbackQuery):
    if not ADMIN_IDS or cb.from_user.id not in ADMIN_IDS:
        return
    charge_id = int(cb.data.split(":")[2])
    if not approve_wallet_charge(charge_id, cb.from_user.id):
        return await cb.answer("خطایی رخ داد", show_alert=True)
    await cb.answer("✅ شارژ تایید شد", show_alert=True)
    charge = get_wallet_charge(charge_id)
    await cb.bot.send_message(
        chat_id=charge["telegram_id"],
        text=f"✅ شارژ کیف‌پول شما تایید شد\n\nمبلغ: {charge['amount_toman']:,} تومان",
    )
    await cb.message.edit_reply_markup(reply_markup=wallet_charge_detail_kb(charge_id, "approved"))


@router.callback_query(F.data.startswith("ha:wallet_reject:"))
async def ha_wallet_reject(cb: CallbackQuery):
    if not ADMIN_IDS or cb.from_user.id not in ADMIN_IDS:
        return
    charge_id = int(cb.data.split(":")[2])
    if not reject_wallet_charge(charge_id):
        return await cb.answer("خطایی رخ داد", show_alert=True)
    await cb.answer("❌ شارژ رد شد", show_alert=True)
    charge = get_wallet_charge(charge_id)
    await cb.bot.send_message(
        chat_id=charge["telegram_id"],
        text=f"❌ شارژ کیف‌پول شما رد شد\n\nمبلغ: {charge['amount_toman']:,} تومان",
    )
    await cb.message.edit_reply_markup(reply_markup=wallet_charge_detail_kb(charge_id, "rejected"))
