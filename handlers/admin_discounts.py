from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from config.settings import ADMIN_IDS
from database.db import get_connection
from keyboards.admin_keyboards import (
    admin_discounts_keyboard,
    discount_type_keyboard,
    cancel_discount_keyboard,
    discount_manage_keyboard,
    discount_edit_field_keyboard,
    discount_del_confirm_keyboard,
)
from states.user_states import DiscountStates


router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def rows_to_dicts(cursor, rows):
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def safe_int(value, default=0):
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def parse_datetime(value):
    if not value:
        return None

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            pass

    return None


def discount_status(item: dict):
    now = datetime.now()

    is_active = safe_int(item.get("is_active"), 0)
    used_count = safe_int(item.get("used_count"), 0)
    max_uses = safe_int(item.get("max_uses"), 1)
    expires_at = parse_datetime(item.get("expires_at"))

    if is_active == 0:
        return "غیرفعال دستی"

    if max_uses > 0 and used_count >= max_uses:
        return "ظرفیت تمام شده"

    if expires_at and expires_at < now:
        return "منقضی شده"

    return "فعال"


def create_discount_code(
    code: str,
    discount_type: str,
    amount: int,
    max_uses: int,
    expire_hours: int
):
    expires_at = datetime.now() + timedelta(hours=expire_hours)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO discount_codes (
        code,
        discount_type,
        amount,
        max_uses,
        used_count,
        expires_at,
        is_active
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        code.upper(),
        discount_type,
        amount,
        max_uses,
        0,
        expires_at.strftime("%Y-%m-%d %H:%M:%S"),
        1
    ))

    discount_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return discount_id, expires_at


def get_discount_codes():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM discount_codes
    ORDER BY id DESC
    LIMIT 20
    """)

    rows = cursor.fetchall()
    discounts = rows_to_dicts(cursor, rows)

    conn.close()
    return discounts


def discount_type_to_fa(discount_type: str):
    if discount_type == "percent":
        return "درصدی"
    if discount_type == "fixed_toman":
        return "مبلغ ثابت تومان"
    return discount_type


@router.callback_query(F.data == "admin:discounts")
async def admin_discounts_home(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    await callback.message.edit_text(
        "🎟 مدیریت کد تخفیف\n\n"
        "از این بخش می‌توانی کد تخفیف بسازی و کدهای جاری را ببینی.",
        reply_markup=admin_discounts_keyboard()
    )

    await callback.answer()


@router.callback_query(F.data == "admin_discount:add")
async def admin_discount_add(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    await state.clear()

    await callback.message.edit_text(
        "➕ ساخت کد تخفیف\n\n"
        "کد تخفیف را ارسال کن.\n\n"
        "مثال:\n"
        "<code>VIP10</code>",
        reply_markup=cancel_discount_keyboard()
    )

    await state.set_state(DiscountStates.waiting_for_code)
    await callback.answer()


@router.message(DiscountStates.waiting_for_code)
async def discount_code_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return

    code = message.text.strip().upper() if message.text else ""

    if len(code) < 2:
        await message.answer("کد خیلی کوتاهه. یه چیز قابل استفاده بفرست.")
        return

    await state.update_data(code=code)

    await message.answer(
        "نوع تخفیف را انتخاب کن:",
        reply_markup=discount_type_keyboard()
    )

    await state.set_state(DiscountStates.waiting_for_type)


@router.callback_query(F.data.startswith("discount_type:"))
async def discount_type_callback(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    discount_type = callback.data.split(":")[1]

    await state.update_data(discount_type=discount_type)

    if discount_type == "percent":
        text = (
            "درصد تخفیف را ارسال کن.\n\n"
            "مثال برای ۱۰ درصد:\n"
            "<code>10</code>"
        )
    else:
        text = (
            "مبلغ تخفیف را به تومان ارسال کن.\n\n"
            "مثال:\n"
            "<code>50000</code>"
        )

    await callback.message.edit_text(
        text,
        reply_markup=cancel_discount_keyboard()
    )

    await state.set_state(DiscountStates.waiting_for_amount)
    await callback.answer()


@router.message(DiscountStates.waiting_for_amount)
async def discount_amount_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return

    if not message.text or not message.text.strip().isdigit():
        await message.answer("مقدار تخفیف باید عددی باشد.")
        return

    amount = int(message.text.strip())
    data = await state.get_data()

    if data["discount_type"] == "percent" and not 1 <= amount <= 100:
        await message.answer("درصد باید بین ۱ تا ۱۰۰ باشد. ریاضی هم امروز زنده ماند.")
        return

    if data["discount_type"] == "fixed_toman" and amount <= 0:
        await message.answer("مبلغ باید بیشتر از صفر باشد.")
        return

    await state.update_data(amount=amount)

    await message.answer(
        "تعداد دفعات قابل استفاده را ارسال کن.\n\n"
        "مثال:\n"
        "<code>1</code>"
    )

    await state.set_state(DiscountStates.waiting_for_max_uses)


@router.message(DiscountStates.waiting_for_max_uses)
async def discount_max_uses_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return

    if not message.text or not message.text.strip().isdigit():
        await message.answer("تعداد استفاده باید عددی باشد.")
        return

    max_uses = int(message.text.strip())

    if max_uses <= 0:
        await message.answer("تعداد استفاده باید بیشتر از صفر باشد.")
        return

    await state.update_data(max_uses=max_uses)

    await message.answer(
        "مدت اعتبار کد را به ساعت ارسال کن.\n\n"
        "مثال:\n"
        "<code>24</code>\n\n"
        "برای یک روز یعنی ۲۴ ساعت."
    )

    await state.set_state(DiscountStates.waiting_for_expire_hours)


@router.message(DiscountStates.waiting_for_expire_hours)
async def discount_expire_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return

    if not message.text or not message.text.strip().isdigit():
        await message.answer("مدت اعتبار باید عددی باشد.")
        return

    expire_hours = int(message.text.strip())

    if expire_hours <= 0:
        await message.answer("مدت اعتبار باید بیشتر از صفر باشد.")
        return

    data = await state.get_data()

    try:
        discount_id, expires_at = create_discount_code(
            code=data["code"],
            discount_type=data["discount_type"],
            amount=data["amount"],
            max_uses=data["max_uses"],
            expire_hours=expire_hours
        )
    except Exception as e:
        await message.answer(
            "❌ ساخت کد تخفیف ناموفق بود.\n\n"
            "احتمالاً این کد قبلاً ساخته شده.\n\n"
            f"<code>{e}</code>",
            reply_markup=admin_discounts_keyboard()
        )
        await state.clear()
        return

    await message.answer(
        "✅ کد تخفیف ساخته شد.\n\n"
        f"آیدی: <code>{discount_id}</code>\n"
        f"کد: <code>{data['code']}</code>\n"
        f"نوع: {discount_type_to_fa(data['discount_type'])}\n"
        f"مقدار: {data['amount']}\n"
        f"تعداد استفاده: {data['max_uses']}\n"
        f"انقضا: {expires_at.strftime('%Y-%m-%d %H:%M')}",
        reply_markup=admin_discounts_keyboard()
    )

    await state.clear()


@router.callback_query(F.data == "admin_discount:list")
async def admin_discount_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    discounts = get_discount_codes()

    if not discounts:
        await callback.message.edit_text(
            "هنوز هیچ کد تخفیفی ساخته نشده.",
            reply_markup=admin_discounts_keyboard()
        )
        await callback.answer()
        return

    text = "📋 کدهای تخفیف اخیر:\n\n"

    for item in discounts:
        status_text = discount_status(item)

        text += (
            f"🆔 {item['id']}\n"
            f"کد: <code>{item['code']}</code>\n"
            f"نوع: {discount_type_to_fa(item['discount_type'])}\n"
            f"مقدار: {item['amount']}\n"
            f"استفاده: {safe_int(item.get('used_count'))} / {safe_int(item.get('max_uses'))}\n"
            f"انقضا: {item['expires_at']}\n"
            f"وضعیت: {status_text}\n\n"
        )

    await callback.message.edit_text(
        text,
        reply_markup=admin_discounts_keyboard()
    )

    await callback.answer()


@router.callback_query(F.data == "admin_discount:cancel")
async def admin_discount_cancel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
        return

    await state.clear()

    await callback.message.edit_text(
        "عملیات لغو شد.",
        reply_markup=admin_discounts_keyboard()
    )

    await callback.answer()

# ═══════════════════════════════════════════════════════════
# مدیریت کدها: ویرایش و حذف
# ═══════════════════════════════════════════════════════════
def _get_discount(discount_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM discount_codes WHERE id = ?", (discount_id,))
    row = cur.fetchone()
    result = rows_to_dicts(cur, [row])[0] if row else None
    conn.close()
    return result


@router.callback_query(F.data == "admin_discount:manage")
async def admin_discount_manage(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("شما دسترسی ادمین ندارید.", show_alert=True)
    await state.clear()
    discounts = get_discount_codes()
    if not discounts:
        await callback.message.edit_text(
            "هنوز هیچ کد تخفیفی ساخته نشده.",
            reply_markup=admin_discounts_keyboard(),
        )
        return await callback.answer()
    await callback.message.edit_text(
        "✏️ <b>مدیریت کدهای تخفیف</b>\n\n"
        "برای ویرایش یا حذف هر کد، دکمه‌های زیرش را بزنید.",
        reply_markup=discount_manage_keyboard(discounts),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_disc:info:"))
async def admin_disc_info(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("دسترسی ندارید.", show_alert=True)
    discount_id = int(callback.data.split(":")[2])
    d = _get_discount(discount_id)
    if not d:
        return await callback.answer("کد پیدا نشد.", show_alert=True)
    await callback.answer(
        "کد: " + str(d["code"]) + "\n"
        "نوع: " + discount_type_to_fa(d["discount_type"]) + "\n"
        "مقدار: " + str(d["amount"]) + "\n"
        "استفاده: " + str(safe_int(d.get("used_count"))) + "/" + str(safe_int(d.get("max_uses"))) + "\n"
        "وضعیت: " + discount_status(d),
        show_alert=True,
    )


# ── حذف ──────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("admin_disc:del:"))
async def admin_disc_del(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("دسترسی ندارید.", show_alert=True)
    discount_id = int(callback.data.split(":")[2])
    d = _get_discount(discount_id)
    if not d:
        return await callback.answer("کد پیدا نشد.", show_alert=True)
    await callback.message.edit_text(
        "🗑 <b>حذف کد تخفیف</b>\n\n"
        "کد <code>" + str(d["code"]) + "</code> حذف شود؟\n"
        "این عمل قابل بازگشت نیست.",
        reply_markup=discount_del_confirm_keyboard(discount_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_disc:delok:"))
async def admin_disc_delok(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("دسترسی ندارید.", show_alert=True)
    discount_id = int(callback.data.split(":")[2])
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM discount_codes WHERE id = ?", (discount_id,))
        conn.commit()
    finally:
        conn.close()
    await callback.answer("🗑 حذف شد")
    discounts = get_discount_codes()
    if not discounts:
        await callback.message.edit_text("همهٔ کدها حذف شدند.", reply_markup=admin_discounts_keyboard())
    else:
        await callback.message.edit_text(
            "✏️ <b>مدیریت کدهای تخفیف</b>\n\nبرای ویرایش یا حذف، دکمه‌ها را بزنید.",
            reply_markup=discount_manage_keyboard(discounts),
        )


# ── ویرایش ───────────────────────────────────────────────────
@router.callback_query(F.data.startswith("admin_disc:edit:"))
async def admin_disc_edit(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("دسترسی ندارید.", show_alert=True)
    await state.clear()
    discount_id = int(callback.data.split(":")[2])
    d = _get_discount(discount_id)
    if not d:
        return await callback.answer("کد پیدا نشد.", show_alert=True)
    await callback.message.edit_text(
        "✏️ <b>ویرایش کد</b> <code>" + str(d["code"]) + "</code>\n\n"
        "نوع: " + discount_type_to_fa(d["discount_type"]) + "\n"
        "مقدار فعلی: " + str(d["amount"]) + "\n"
        "تعداد استفاده: " + str(safe_int(d.get("used_count"))) + "/" + str(safe_int(d.get("max_uses"))) + "\n"
        "وضعیت: " + discount_status(d) + "\n\n"
        "کدام مورد را می‌خواهید تغییر دهید؟",
        reply_markup=discount_edit_field_keyboard(discount_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_disc:toggle:"))
async def admin_disc_toggle(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("دسترسی ندارید.", show_alert=True)
    discount_id = int(callback.data.split(":")[2])
    d = _get_discount(discount_id)
    if not d:
        return await callback.answer("کد پیدا نشد.", show_alert=True)
    new_val = 0 if safe_int(d.get("is_active"), 0) else 1
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE discount_codes SET is_active = ? WHERE id = ?", (new_val, discount_id))
        conn.commit()
    finally:
        conn.close()
    await callback.answer("🟢 فعال شد" if new_val else "🔴 غیرفعال شد")
    d = _get_discount(discount_id)
    await callback.message.edit_text(
        "✏️ <b>ویرایش کد</b> <code>" + str(d["code"]) + "</code>\n\n"
        "مقدار: " + str(d["amount"]) + "\n"
        "تعداد استفاده: " + str(safe_int(d.get("used_count"))) + "/" + str(safe_int(d.get("max_uses"))) + "\n"
        "وضعیت: " + discount_status(d) + "\n\n"
        "کدام مورد را می‌خواهید تغییر دهید؟",
        reply_markup=discount_edit_field_keyboard(discount_id),
    )


@router.callback_query(F.data.startswith("admin_disc:editf:"))
async def admin_disc_edit_field(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("دسترسی ندارید.", show_alert=True)
    parts = callback.data.split(":")
    field, discount_id = parts[2], int(parts[3])
    await state.update_data(edit_discount_id=discount_id, edit_field=field)
    await state.set_state(DiscountStates.waiting_for_edit_value)
    prompts = {
        "amount": "مقدار جدید تخفیف را بفرست (درصد یا تومان بسته به نوع کد):",
        "max_uses": "تعداد کل دفعات مجاز استفاده را بفرست:",
        "expire": "چند ساعت به انقضا اضافه شود؟ (از الان محاسبه می‌شود)",
    }
    await callback.message.answer(prompts.get(field, "مقدار جدید را بفرست:"))
    await callback.answer()


@router.message(DiscountStates.waiting_for_edit_value)
async def admin_disc_edit_value(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    txt = (message.text or "").strip()
    if not txt.isdigit():
        return await message.answer("عدد معتبر بفرست.")
    val = int(txt)
    data = await state.get_data()
    discount_id = data.get("edit_discount_id")
    field = data.get("edit_field")
    d = _get_discount(discount_id)
    if not d:
        await state.clear()
        return await message.answer("کد پیدا نشد.")

    conn = get_connection()
    cur = conn.cursor()
    try:
        if field == "amount":
            if d["discount_type"] == "percent" and not (1 <= val <= 100):
                conn.close()
                return await message.answer("درصد باید بین ۱ تا ۱۰۰ باشد.")
            cur.execute("UPDATE discount_codes SET amount = ? WHERE id = ?", (val, discount_id))
        elif field == "max_uses":
            if val <= 0:
                conn.close()
                return await message.answer("تعداد باید بیشتر از صفر باشد.")
            cur.execute("UPDATE discount_codes SET max_uses = ? WHERE id = ?", (val, discount_id))
        elif field == "expire":
            new_exp = (datetime.now() + timedelta(hours=val)).strftime("%Y-%m-%d %H:%M:%S")
            cur.execute("UPDATE discount_codes SET expires_at = ? WHERE id = ?", (new_exp, discount_id))
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass

    await state.clear()
    d = _get_discount(discount_id)
    await message.answer(
        "✅ ویرایش شد.\n\n"
        "کد: <code>" + str(d["code"]) + "</code>\n"
        "مقدار: " + str(d["amount"]) + "\n"
        "تعداد استفاده: " + str(safe_int(d.get("used_count"))) + "/" + str(safe_int(d.get("max_uses"))) + "\n"
        "انقضا: " + str(d["expires_at"]) + "\n"
        "وضعیت: " + discount_status(d),
        reply_markup=discount_edit_field_keyboard(discount_id),
    )
