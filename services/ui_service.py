from aiogram.types import CallbackQuery, Message, FSInputFile

from services.banner_service import banner_path


# In-memory tracker for the last bot UI screen in each chat.
# This fixes the old behavior where some handlers passed state=None and the
# previous banner message could not be found/deleted.
ACTIVE_SCREEN_IDS: dict[int, int] = {}


async def delete_message_safe(bot, chat_id: int, message_id: int | None):
    if not message_id:
        return
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        # Message may already be deleted, too old, or not deletable.
        pass


async def clear_last_screen(state, bot, chat_id: int):
    last_id = ACTIVE_SCREEN_IDS.get(chat_id)

    if state:
        try:
            data = await state.get_data()
            state_last_id = data.get("active_screen_message_id")
            if state_last_id:
                last_id = state_last_id
        except Exception:
            pass

    await delete_message_safe(bot, chat_id, last_id)
    ACTIVE_SCREEN_IDS.pop(chat_id, None)

    if state:
        try:
            await state.update_data(active_screen_message_id=None)
        except Exception:
            pass


async def send_screen(
    target,
    state,
    text: str,
    reply_markup=None,
    banner_key: str | None = None,
    delete_trigger: bool = True,
):
    """Send exactly one clean UI screen.

    Behavior:
    - Deletes the previous bot screen in this chat even when handlers pass state=None.
    - Deletes the clicked/typed trigger message when possible.
    - Sends banner + caption + buttons as one Telegram message when a banner exists.
    - Saves the new screen id both in memory and FSM state when available.
    """
    if isinstance(target, CallbackQuery):
        message = target.message
        bot = target.bot
        chat_id = message.chat.id
        trigger_message_id = message.message_id
    else:
        message = target
        bot = target.bot
        chat_id = message.chat.id
        trigger_message_id = message.message_id

    # 1) Delete previous active screen from memory tracker.
    last_id = ACTIVE_SCREEN_IDS.get(chat_id)

    # 2) Also check FSM state if it exists.
    if state:
        try:
            data = await state.get_data()
            state_last_id = data.get("active_screen_message_id")
            if state_last_id:
                last_id = state_last_id
        except Exception:
            pass

    if last_id and last_id != trigger_message_id:
        await delete_message_safe(bot, chat_id, last_id)

    # 3) Delete the message that triggered this screen.
    # For callback clicks this is usually the old bot screen.
    # For typed messages this is the user's command/volume input.
    if delete_trigger:
        await delete_message_safe(bot, chat_id, trigger_message_id)

    path = banner_path(banner_key) if banner_key else None

    if path:
        sent = await message.answer_photo(
            photo=FSInputFile(path),
            caption=text,
            reply_markup=reply_markup,
        )
    else:
        sent = await message.answer(text, reply_markup=reply_markup)

    ACTIVE_SCREEN_IDS[chat_id] = sent.message_id

    if state:
        try:
            await state.update_data(active_screen_message_id=sent.message_id)
        except Exception:
            pass

    if isinstance(target, CallbackQuery):
        try:
            await target.answer()
        except Exception:
            pass

    return sent
