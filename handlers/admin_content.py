from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext

from config.settings import ADMIN_IDS
from database.db import get_connection
from states.user_states import ContentStates


router = Router()


CONTENT_TITLES = {
    "start_message": "پیام شروع",
    "pricing": "تعرفه سرویس‌ها",
    "channels_list": "راهنمای اتصال",
    "faq": "سوالات متداول",
    "support": "پشتیبانی سریع",
    "referral": "دعوت دوستان",
}


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def rows_to_dicts(cursor, rows):
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def get_content_pages():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT key, title, content, file_id, file_type, updated_at
    FROM content_pages
    ORDER BY title ASC
    """)

    rows = cursor.fetchall()
    data = rows_to_dicts(cursor, rows)

    conn.close()

    if data:
        return data

    return [
        {
            "key": key,
            "title": title,
            "content": "هنوز متنی ثبت نشده است.",
            "file_id": None,
            "file_type": None,
            "updated_at": None,
        }
        for key, title in CONTENT_TITLES.items()
    ]


def get_content_page(key: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT key, title, content, file_id, file_type, updated_at
    FROM content_pages
    WHERE key = ?
    """, (key,))

    row = cursor.fetchone()

    if not row:
        conn.close()

        title = CONTENT_TITLES.get(key, key)

        return {
            "key": key,
            "title": title,
            "content": "هنوز متنی ثبت نشده است.",
            "file_id": None,
            "file_type": None,
            "updated_at": None,
        }

    data = rows_to_dicts(cursor, [row])[0]
    conn.close()
    return data


def update_content_page(
    key: str,
    title: str,
    content: str,
    file_id=None,
    file_type=None
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT OR REPLACE INTO content_pages (
        key,
        title,
        content,
        file_id,
        file_type,
        updated_at
    )
    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (
        key,
        title,
        content,
        file_id,
        file_type
    ))

    conn.commit()
    conn.close()


def content_pages_keyboard():
    keyboard = []

    existing_keys = set()

    for page in get_content_pages():
        existing_keys.add(page["key"])

        keyboard.append([
            InlineKeyboardButton(
                text=f"✏️ {page['title']}",
                callback_data=f"admin_content:edit:{page['key']}"
            )
        ])

    for key, title in CONTENT_TITLES.items():
        if key not in existing_keys:
            keyboard.append([
                InlineKeyboardButton(
                    text=f"✏️ {title}",
                    callback_data=f"admin_content:edit:{key}"
                )
            ])

    keyboard.append([
        InlineKeyboardButton(
            text="⬅️ بازگشت",
            callback_data="admin:home"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def content_cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="لغو عملیات",
                callback_data="admin_content:cancel"
            )
        ]
    ])


@router.callback_query(F.data == "admin:content")
async def admin_content_home(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "شما دسترسی ادمین ندارید.",
            show_alert=True
        )
        return

    await callback.message.edit_text(
        "📝 مدیریت متن‌ها و مدیا\n\n"
        "یکی از بخش‌های قابل ویرایش را انتخاب کن.\n\n"
        "می‌توانی فقط متن بفرستی، یا متن همراه عکس/ویدیو/فایل.",
        reply_markup=content_pages_keyboard()
    )

    await callback.answer()


@router.callback_query(F.data.startswith("admin_content:edit:"))
async def admin_content_edit(
    callback: CallbackQuery,
    state: FSMContext
):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "شما دسترسی ادمین ندارید.",
            show_alert=True
        )
        return

    key = callback.data.split(":")[2]
    page = get_content_page(key)

    await state.update_data(
        content_key=key,
        content_title=page["title"]
    )

    media_status = "ندارد"

    if page.get("file_id"):
        media_status = page.get("file_type") or "ثبت شده"

    await callback.message.edit_text(
        f"✏️ ویرایش: {page['title']}\n\n"
        f"مدیای فعلی: {media_status}\n\n"
        f"متن فعلی:\n\n"
        f"{page['content']}\n\n"
        "متن جدید را ارسال کن.\n\n"
        "اگر می‌خواهی عکس/ویدیو/فایل هم ذخیره شود، همان مدیا را با کپشن ارسال کن.\n\n"
        "اگر فقط متن بفرستی، مدیای قبلی حذف می‌شود.",
        reply_markup=content_cancel_keyboard()
    )

    await state.set_state(ContentStates.waiting_for_content_text)
    await callback.answer()


@router.message(ContentStates.waiting_for_content_text)
async def admin_content_save(
    message: Message,
    state: FSMContext
):
    if not is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return

    data = await state.get_data()

    key = data.get("content_key")
    title = data.get("content_title") or CONTENT_TITLES.get(key, key)

    content = message.caption or message.text or ""

    if len(content.strip()) < 1:
        await message.answer(
            "متن یا کپشن خالیه. حداقل یه چیزی بنویس که ربات به پوچی نرسه.",
            reply_markup=content_cancel_keyboard()
        )
        return

    file_id = None
    file_type = None

    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"

    elif message.video:
        file_id = message.video.file_id
        file_type = "video"

    elif message.document:
        file_id = message.document.file_id
        file_type = "document"

    update_content_page(
        key=key,
        title=title,
        content=content,
        file_id=file_id,
        file_type=file_type
    )

    if file_type:
        media_text = f"مدیا ذخیره شد: {file_type}"
    else:
        media_text = "بدون مدیا ذخیره شد."

    await message.answer(
        "✅ محتوا با موفقیت ذخیره شد.\n\n"
        f"{media_text}",
        reply_markup=content_pages_keyboard()
    )

    await state.clear()


@router.callback_query(F.data == "admin_content:cancel")
async def admin_content_cancel(
    callback: CallbackQuery,
    state: FSMContext
):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "شما دسترسی ادمین ندارید.",
            show_alert=True
        )
        return

    await state.clear()

    await callback.message.edit_text(
        "عملیات لغو شد.",
        reply_markup=content_pages_keyboard()
    )

    await callback.answer()