"""
wallet.py — کیف‌پول کاربر
FIX: رسید جدا از دکمه‌ها ارسال میشه تا edit_text روی پیام متنی کار کنه
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from database.wallet import (
    get_or_create_wallet, create_wallet_charge,
    approve_wallet_charge, reject_wallet_charge,
    get_wallet_charge, get_wallet_transactions,
)
from database.db import save_user, get_user, get_connection
from config.settings import ADMIN_IDS
from handlers.btn_filter import Btn
from services.ui_texts import T, TF

router = Router()


def _purchase_count(uid: int) -> int:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM orders WHERE telegram_id = ? "
            "AND status IN ('approved','completed','paid','success')",
            (uid,),
        )
        n = cur.fetchone()[0]
        conn.close()
        return int(n or 0)
    except Exception:
        return 0


def _profile_text(uid: int) -> str:
    u = get_user(uid) or {}
    uname = (u.get("custom_username") or "").strip() or "—"
    phone = (u.get("phone") or "").strip() or "—"
    purchases = _purchase_count(uid)
    text = (
        T("profile_title", "👤 پنل کاربری") + "\n"
        "━━━━━━━━━━━━━━\n\n"
        + T("profile_lbl_username", "🏷 نام کاربری:") + " " + str(uname) + "\n"
        + T("profile_lbl_id", "🆔 آیدی عددی:") + " <code>" + str(uid) + "</code>\n"
        + T("profile_lbl_phone", "📱 شماره تلفن:") + " " + str(phone) + "\n"
        + T("profile_lbl_purchases", "🛒 تعداد خریدها:") + " " + str(purchases) + "\n"
    )
    footer = T("profile_footer", "")
    if footer:
        text += "\n" + footer
    return text


class WalletStates(StatesGroup):
    waiting_for_charge_amount = State()
    waiting_for_payment_receipt = State()


def _btn(t, d):
    return InlineKeyboardButton(text=t, callback_data=d)


def wallet_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(T("wal_btn_balance", "💰 موجودی"), "wallet:balance")],
        [_btn(T("wal_btn_charge", "➕ شارژ کیف‌پول"), "wallet:charge_start")],
        [_btn(T("wal_btn_history", "📊 تاریخچه"), "wallet:history")],
        [_btn(T("wal_btn_back", "⬅️ بازگشت"), "u:menu")],
    ])


def profile_kb():
    """پنل کاربری — فعلاً فقط دکمهٔ بازگشت."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(T("profile_btn_back", "⬅️ بازگشت"), "u:menu")],
    ])


@router.message(Btn("btn_profile", "👤 پنل کاربری"))
async def profile_entry(msg: Message):
    save_user(msg.from_user.id, msg.from_user.full_name, msg.from_user.username)
    text = _profile_text(msg.from_user.id)
    kb = profile_kb()
    sent = False
    try:
        from services.banner_service import send_banner
        sent = await send_banner(msg, "profile", caption=text, reply_markup=kb)
    except Exception:
        sent = False
    if not sent:
        await msg.answer(text, reply_markup=kb)


@router.callback_query(F.data == "u:profile")
async def profile_cb(cb: CallbackQuery):
    text = _profile_text(cb.from_user.id)
    kb = profile_kb()
    try:
        if cb.message.photo or cb.message.caption is not None:
            raise ValueError("photo message")
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer()


@router.message(Btn("btn_wallet", "💳 کیف پول", "کیف پول"))
async def wallet_entry(msg: Message):
    save_user(msg.from_user.id, msg.from_user.full_name, msg.from_user.username)
    w = get_or_create_wallet(msg.from_user.id)
    await msg.answer(
        TF("wal_home", "💰 کیف‌پول شما\n\nموجودی: {balance} تومان", balance="{:,}".format(w["balance_toman"])),
        reply_markup=wallet_main_kb()
    )


@router.callback_query(F.data == "wallet:home")
async def wallet_home(cb: CallbackQuery):
    w = get_or_create_wallet(cb.from_user.id)
    text = TF("wal_home", "💰 کیف‌پول شما\n\nموجودی: {balance} تومان", balance="{:,}".format(w["balance_toman"]))
    try:
        if cb.message.photo or cb.message.caption is not None:
            raise ValueError("photo message")
        await cb.message.edit_text(text, reply_markup=wallet_main_kb())
    except Exception:
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(text, reply_markup=wallet_main_kb())
    await cb.answer()


@router.callback_query(F.data == "wallet:balance")
async def wallet_balance(cb: CallbackQuery):
    w = get_or_create_wallet(cb.from_user.id)
    await cb.answer(TF("wal_balance", "💰 موجودی: {amount} تومان",
                       amount="{:,}".format(w["balance_toman"])), show_alert=True)


@router.callback_query(F.data == "wallet:history")
async def wallet_history(cb: CallbackQuery):
    txs = get_wallet_transactions(cb.from_user.id, limit=10)
    if not txs:
        return await cb.message.edit_text(
            T("wal_hist_empty", "تاریخچه‌ای ثبت نشده."),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[_btn(T("wal_btn_back", "⬅️ بازگشت"), "wallet:home")]])
        )
    text = T("wal_hist_title", "📊 تاریخچه:\n\n")
    for tr in txs:
        ico = "➕" if tr["type"] == "charge" else "➖"
        text += TF("wal_hist_item", "{icon} {amount}T — {desc}\n",
                   icon=ico, amount="{:,}".format(tr["amount_toman"]),
                   desc=tr["description"] or "")
    await cb.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[_btn(T("wal_btn_back", "⬅️ بازگشت"), "wallet:home")]])
    )
    await cb.answer()


@router.callback_query(F.data == "wallet:charge_start")
async def charge_start(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text(
        T("wal_charge_ask", "➕ شارژ کیف‌پول\n\nمبلغ رو به تومان وارد کن (فقط عدد):\nمثال: 500000"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[_btn(T("wal_btn_cancel", "⬅️ انصراف"), "wallet:home")]]),
    )
    await state.set_state(WalletStates.waiting_for_charge_amount)
    await cb.answer()


@router.message(WalletStates.waiting_for_charge_amount)
async def charge_amount(msg: Message, state: FSMContext):
    if not msg.text or not msg.text.strip().isdigit():
        return await msg.answer(T("wal_err_numeric", "❌ فقط عدد قبول میشه:"))
    amount = int(msg.text.strip())
    if amount < 1000:
        return await msg.answer(T("wal_err_min", "❌ حداقل ۱,۰۰۰ تومان:"))
    if amount > 100_000_000:
        return await msg.answer(T("wal_err_max", "❌ حداکثر ۱۰۰,۰۰۰,۰۰۰ تومان:"))

    from database.db import get_setting
    card_info = get_setting("card_info", "تنظیم نشده — هد ادمین از تنظیمات وارد کند")

    await state.update_data(amount_toman=amount)
    await msg.answer(
        TF("wal_card_text",
           "💳 اطلاعات کارت:\n<code>{card}</code>\n\n"
           "مبلغ: {amount} تومان\n\n"
           "لطفاً واریز کن و رسید (عکس یا متن) رو اینجا بفرست:",
           card=card_info, amount="{:,}".format(amount))
    )
    await state.set_state(WalletStates.waiting_for_payment_receipt)


@router.message(WalletStates.waiting_for_payment_receipt)
async def charge_receipt(msg: Message, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount_toman")
    receipt_text = msg.caption or msg.text or T("wal_receipt_no_text", "رسید بدون متن")
    receipt_type = "text"
    file_id = None

    if msg.photo:
        file_id = msg.photo[-1].file_id
        receipt_type = "photo"
    elif msg.document:
        file_id = msg.document.file_id
        receipt_type = "document"

    charge_id = create_wallet_charge(
        telegram_id=msg.from_user.id, amount_toman=amount,
        payment_method="card", receipt_type=receipt_type,
        receipt_text=receipt_text, file_id=file_id,
    )

    await msg.answer(
        TF("wal_charge_saved",
           "✅ درخواست شارژ ثبت شد\n\n"
           "مبلغ: {amount} تومان\n"
           "وضعیت: ⏳ در انتظار تایید ادمین",
           amount="{:,}".format(amount))
    )
    await state.clear()

    # ─── اطلاع ادمین ────────────────────────────────────────
    # دکمه‌ها روی یه پیام TEXT جداگانه (نه عکس) — چون edit_text فقط روی text کار می‌کنه
    admin_text = (
        "🔔 درخواست شارژ کیف‌پول\n\n"
        "کاربر: " + str(msg.from_user.full_name) + "\n"
        "آیدی: " + str(msg.from_user.id) + "\n"
        "مبلغ: {:,} تومان\n".format(amount) +
        "شماره: #" + str(charge_id) + "\n\n"
        "رسید:\n" + str(receipt_text)
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [_btn("✅ تایید", "admin_wallet_approve:" + str(charge_id)),
         _btn("❌ رد", "admin_wallet_reject:" + str(charge_id))],
    ])

    for admin_id in ADMIN_IDS:
        try:
            # اگه عکس/فایل بود اول رسید رو بفرست
            if receipt_type == "photo" and file_id:
                await msg.bot.send_photo(
                    chat_id=admin_id, photo=file_id,
                    caption="📎 رسید شارژ #" + str(charge_id)
                )
            elif receipt_type == "document" and file_id:
                await msg.bot.send_document(
                    chat_id=admin_id, document=file_id,
                    caption="📎 رسید شارژ #" + str(charge_id)
                )
            # دکمه‌ها همیشه روی پیام TEXT جداگانه
            await msg.bot.send_message(chat_id=admin_id, text=admin_text, reply_markup=kb)
        except Exception:
            pass


# ─── Admin Approval ──────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_wallet_approve:"))
async def admin_approve_charge(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("دسترسی ندارید", show_alert=True)

    charge_id = int(cb.data.split(":")[1])
    charge = get_wallet_charge(charge_id)
    if not charge:
        return await cb.answer("شارژ پیدا نشد", show_alert=True)
    if charge["status"] != "waiting_admin_review":
        return await cb.answer("قبلاً پردازش شده", show_alert=True)

    approve_wallet_charge(charge_id, cb.from_user.id)
    await cb.answer("✅ شارژ تایید شد", show_alert=True)

    # این پیام همیشه text است (چون جداگانه فرستادیم)
    try:
        await cb.message.edit_text(
            (cb.message.text or "") + "\n\n✅ تایید شد",
            reply_markup=None
        )
    except Exception:
        pass

    await cb.bot.send_message(
        chat_id=charge["telegram_id"],
        text=TF("wal_approved_user",
                "✅ شارژ کیف‌پول تایید شد!\n\nمبلغ: {amount} تومان\nاکنون می‌توانید خرید کنید.",
                amount="{:,}".format(charge["amount_toman"]))
    )


@router.callback_query(F.data.startswith("admin_wallet_reject:"))
async def admin_reject_charge(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("دسترسی ندارید", show_alert=True)

    charge_id = int(cb.data.split(":")[1])
    charge = get_wallet_charge(charge_id)
    if not charge:
        return await cb.answer("شارژ پیدا نشد", show_alert=True)
    if charge["status"] != "waiting_admin_review":
        return await cb.answer("قبلاً پردازش شده", show_alert=True)

    reject_wallet_charge(charge_id)
    await cb.answer("❌ شارژ رد شد", show_alert=True)

    try:
        await cb.message.edit_text(
            (cb.message.text or "") + "\n\n❌ رد شد",
            reply_markup=None
        )
    except Exception:
        pass

    await cb.bot.send_message(
        chat_id=charge["telegram_id"],
        text=TF("wal_rejected_user",
                "❌ شارژ کیف‌پول رد شد\n\nمبلغ: {amount} تومان\nدر صورت سوال با پشتیبانی تماس بگیرید.",
                amount="{:,}".format(charge["amount_toman"]))
    )
