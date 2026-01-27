from create_bot import base, cursor, bot
from handlers import main_handler
from aiogram import types, Dispatcher
from aiogram.dispatcher import filters
from config import *

ADMIN_IDS = {550255122}
# Function for checking if user is banned
def is_banned(user_id):
    if int(user_id) in ADMIN_IDS:
        return False

    cursor.execute(f"SELECT user_id FROM ban_id WHERE user_id = {user_id}")
    return True if cursor.fetchone() else False


# Function which helps to prevent SQL error (if chat participant answers to bot informing message)
# def check_replied(message: types.Message):
#     if message.text:
#         if message.text.split()[-2].replace("*", "") != "id:":
#             return False
#     else:
#         if message.caption.split()[-2].replace("*", "") != "id:":
#             return False
#     return True


def check_replied(reply: types.Message) -> bool:
    if not reply:
        return False

    if not reply.from_user:
        return False

    if not reply.from_user.is_bot:
        return False

    return True


# def get_user_id(message: types.Message):
#     reply = message.reply_to_message
#     if not reply:
#         return None

#     entities = reply.entities or reply.caption_entities
#     if not entities:
#         return None

#     for entity in entities:
#         if entity.type == "text_link" and entity.url:
#             if entity.url.startswith("tg://user?id="):
#                 return int(entity.url.replace("tg://user?id=", ""))

#     return None
def get_user_id(message: types.Message) -> int | None:
    entities = message.entities or message.caption_entities
    if not entities:
        return None

    for entity in entities:
        if entity.type == "text_mention" and entity.user:
            return entity.user.id

    return None





# Function to ban user from writing to this bot using SQL
async def ban_user(message: types.Message):
    if not check_replied(message.reply_to_message):
        await message.reply(TEXT_MESSAGES['reply_error'])
        return
    
    user_id = get_user_id(message.reply_to_message)     # Getting user's id from the end of the message sent by bot
    try:
        reason = message.text.split(' ', maxsplit=1)[1]
    except Exception:
        reason = None
    if is_banned(user_id):
        await message.answer(TEXT_MESSAGES['already_banned'])  # If this user is already banned, we inform about it
    else:
        cursor.execute(f"INSERT INTO ban_id VALUES (%s, %s)", (user_id, reason))  # Inserting user into table
        base.commit()
        await message.reply(TEXT_MESSAGES['has_banned'])  # Informing that this user has been banned
        await main_handler.answer_banned(user_id)


# Function to unban user from ban list
async def unban_user(message: types.Message):
    if not check_replied(message.reply_to_message):
        await message.reply(TEXT_MESSAGES['reply_error'])
        return

    user_id = get_user_id(message.reply_to_message)     # Getting user's id from the end of the message sent by bot
    if is_banned(user_id):
        cursor.execute(f"DELETE FROM ban_id WHERE user_id = {user_id}")  # Deleting user from ban list if it was found
        base.commit()
        await bot.send_message(
    chat_id=-5132763484,
    text=f"DEBUG user_id = {user_id}"
)
        await message.reply(TEXT_MESSAGES['has_unbanned'])  # Informing that this user is unbanned now
        await bot.send_message(chat_id=user_id, text=TEXT_MESSAGES['user_unbanned'])
    else:
        await message.reply(TEXT_MESSAGES['not_banned'])  # If user is not banned, we inform aboit it


# Registering all dispatchers with their filters and commands
def setup_dispatcher(dp: Dispatcher):
    dp.register_message_handler(filters.IsReplyFilter(True), filters.IDFilter(chat_id=CHAT_ID), ban_user,
                                commands=["ban"], is_reply=True)  # Handler for '/ban' command
    dp.register_message_handler(filters.IsReplyFilter(True), filters.IDFilter(chat_id=CHAT_ID), unban_user,
                                commands=["unban"], is_reply=True)  # Handler for '/unban' command
