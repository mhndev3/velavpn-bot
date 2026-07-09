from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)


def back_keyboard(
    callback_data: str = "back:main"
):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ بازگشت",
                    callback_data=callback_data
                )
            ]
        ]
    )


def back_and_close_keyboard(
    back_callback: str = "back:main"
):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ بازگشت",
                    callback_data=back_callback
                ),
                InlineKeyboardButton(
                    text="❌ خروج",
                    callback_data="close:menu"
                )
            ]
        ]
    )


def cancel_reply_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="❌ لغو عملیات"
                )
            ]
        ],
        resize_keyboard=True
    )