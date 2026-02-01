from typing import Type
from create_bot import base, cursor, bot, dp
from handlers import main_handler
from aiogram import types, Dispatcher
from aiogram.dispatcher import filters
from config import *


ADMIN_IDS = {} # put admin id's here

# Function for checking if user is banned
def is_banned(user_id):
    if int(user_id) in ADMIN_IDS:
        return False

    cursor.execute("SELECT user_id FROM ban_id WHERE user_id = %s", (user_id,))
    return True if cursor.fetchone() else False


def check_replied(reply: types.Message) -> bool:
    if not reply:
        return False

    if not reply.from_user:
        return False

    if not reply.from_user.is_bot:
        return False

    return True


def get_user_id(bot_message_id: int) -> int | None:
    cursor.execute(
        "SELECT tg_user_id FROM message_id WHERE bot_message_id = %s",
        (bot_message_id,)
    )
    row = cursor.fetchone()
    return row[0] if row else None



# Function to ban user from writing to this bot using SQL
async def ban_user(message: types.Message):
    if not check_replied(message.reply_to_message):
        await message.reply(TEXT_MESSAGES['reply_error'])
        return
    
    bot_message_id = message.reply_to_message.message_id
    user_id = get_user_id(bot_message_id)

    try:
        reason = message.text.split(' ', maxsplit=1)[1]
    except Exception:
        reason = None
    if is_banned(user_id):
        await message.answer(TEXT_MESSAGES['already_banned'])  # If this user is already banned, we inform about it
    else:
        cursor.execute("INSERT INTO ban_id VALUES (%s, %s)", (user_id, reason))
        base.commit()
        await message.reply(TEXT_MESSAGES['has_banned'])  # Informing that this user has been banned
        await main_handler.answer_banned(user_id)


# Function to unban user from ban list
async def unban_user(message: types.Message):
    if not check_replied(message.reply_to_message):
        await message.reply(TEXT_MESSAGES['reply_error'])
        return

    bot_message_id = message.reply_to_message.message_id
    user_id = get_user_id(bot_message_id)
    if is_banned(user_id):
        cursor.execute("DELETE FROM ban_id WHERE user_id = %s", (user_id,))
        base.commit()
        await message.reply(TEXT_MESSAGES['has_unbanned'])
        await bot.send_message(chat_id=user_id, text=TEXT_MESSAGES['user_unbanned'])
    else:
        await message.reply(TEXT_MESSAGES['not_banned'])  # If user is not banned, we inform aboit it


# ─── CALLBACK HANDLERS ───────────────────────────────────────────

# Ban user via button
async def callback_ban(callback: types.CallbackQuery):
    user_id = int(callback.data.split(":")[1])

    if is_banned(user_id):
        await callback.answer("Пользователь уже забанен", show_alert=True)
        return

    cursor.execute("INSERT INTO ban_id VALUES (%s, %s)", (user_id, None))
    base.commit()
    await callback.answer("✅ Пользователь забанен", show_alert=True)
    await main_handler.answer_banned(user_id)


# Delete right this post from user
async def callback_delete_post(callback: types.CallbackQuery):
    try:
        await bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id)
    except Exception:
        await callback.answer("❌ Не удалось удалить сообщение", show_alert=True)


# Delete all posts from that user
async def callback_delete_all(callback: types.CallbackQuery):
    user_id = int(callback.data.split(":")[1])

    cursor.execute(
        "SELECT bot_message_id FROM message_id WHERE tg_user_id = %s",
        (user_id,)
    )
    rows = cursor.fetchall()

    if not rows:
        await callback.answer("❌ Постов этого автора не найдено", show_alert=True)
        return

    deleted = 0
    for row in rows:
        try:
            await bot.delete_message(chat_id=callback.message.chat.id, message_id=row[0])
            deleted += 1
        except Exception:
            pass  # The message hass been deleted or unavailable

    # Delete data from db for this user
    cursor.execute("DELETE FROM message_id WHERE tg_user_id = %s", (user_id,))
    base.commit()

    await callback.answer(f"✅ Удалено {deleted} сообщений", show_alert=True)


# Post publication via channel
async def callback_publish(callback: types.CallbackQuery):
    if not CHANNEL_ID:
        await callback.answer("❌ Канал не настроен (CHANNEL_ID)", show_alert=True)
        return

    try:
        await bot.copy_message(
            chat_id=CHANNEL_ID,
            from_chat_id=callback.message.chat.id,
            message_id=callback.message.message_id
        )
        await callback.answer("✅ Пост опубликован в канал", show_alert=True)
    except Exception as e:
        await callback.answer(f"❌ Ошибка публикации: {e}", show_alert=True)

# async def callback_profile(callback: types.CallbackQuery):
#     try:
#         user_id = int(callback.data.split(":")[1])

#     except Exception:
#         await callback.answer("❌ Не удалось перейти в профиль", show_alert=True)


# Registering all dispatchers with their filters and commands
def setup_dispatcher(dp: Dispatcher):
    # Callback handlers для кнопок
    dp.register_callback_query_handler(callback_ban, lambda c: c.data and c.data.startswith("ban:"))
    dp.register_callback_query_handler(callback_delete_post, lambda c: c.data == "delete_post")
    dp.register_callback_query_handler(callback_delete_all, lambda c: c.data and c.data.startswith("delete_all:"))
    dp.register_callback_query_handler(callback_publish, lambda c: c.data == "publish")

    # Command handlers
    dp.register_message_handler(filters.IsReplyFilter(True), filters.IDFilter(chat_id=CHAT_ID), ban_user,
                                commands=["ban"], is_reply=True)
    dp.register_message_handler(filters.IsReplyFilter(True), filters.IDFilter(chat_id=CHAT_ID), unban_user,
                                commands=["unban"], is_reply=True)