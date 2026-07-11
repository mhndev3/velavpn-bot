from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext

from database.db import get_connection, get_setting, is_onboarding_done
from keyboards.user_keyboards import main_menu_keyboard_for
from services.content_media_service import send_content_page
from services.referral_service import set_referrer
from handlers.glass_menu import send_user_menu
from handlers.onboarding import advance_onboarding


router = Router()


def save_user(message: Message):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT OR IGNORE INTO users 
    (telegram_id, full_name, username)
    VALUES (?, ?, ?)
    """, (
        message.from_user.id,
        message.from_user.full_name,
        message.from_user.username
    ))

    cursor.execute("""
    UPDATE users
    SET full_name = ?, username = ?
    WHERE telegram_id = ?
    """, (
        message.from_user.full_name,
        message.from_user.username,
        message.from_user.id
    ))

    conn.commit()
    conn.close()


@router.message(CommandStart())
async def start_handler(
    message: Message,
    command: CommandObject,
    state: FSMContext,
):
    save_user(message)

    referral_registered = False

    if command.args:
        args = command.args.strip()

        if args.startswith("ref_"):
            inviter_raw = args.replace("ref_", "")

            if inviter_raw.isdigit():
                inviter_id = int(inviter_raw)

                if inviter_id != message.from_user.id:
                    referral_registered = set_referrer(
                        invited_id=message.from_user.id,
                        inviter_id=inviter_id
                    )

    if referral_registered:
        await message.answer(
            "✅ ورود شما از طریق لینک دعوت ثبت شد."
        )

    # جریان ثبت‌نام (کانال/قوانین/شماره/نام کاربری) — اگر کامل نباشد همین‌جا متوقف می‌شویم
    if not is_onboarding_done(message.from_user.id):
        done = await advance_onboarding(message, message.from_user.id, state, message.bot)
        if not done:
            return

    await send_content_page(
        message=message,
        key="start_message",
        fallback_text=(
            "سلام {name} 👋\n"
            "🆔 آیدی شما: {id}\n"
            "📅 تاریخ: {datetime}\n\n"
            "از منوی زیر گزینه مورد نظر خود را انتخاب کنید:"
        ),
        user=message.from_user,
    )

    await send_user_menu(message, message.from_user.id)