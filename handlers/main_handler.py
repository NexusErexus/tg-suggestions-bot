import aiogram.utils.exceptions
from aiogram import types, Dispatcher
from aiogram.dispatcher import filters
from datetime import datetime

from config import *
from create_bot import bot, cursor, base
from handlers.admin_handler import is_banned
from handlers.keyboards import post_moderation_keyboard


# Function which answers to banned users based on availability of ban reason
async def answer_banned(user_id):
    cursor.execute('SELECT ban_reason FROM ban_id WHERE user_id = %s', (user_id,))
    reason = cursor.fetchone()[0]
    if reason is None:
        await bot.send_message(chat_id=user_id, text=TEXT_MESSAGES['user_banned'])
    else:
        await bot.send_message(chat_id=user_id, text=TEXT_MESSAGES['user_reason_banned'].format(reason),
                               parse_mode='HTML')


# Starting message (when '/start' command is entered)
async def starting(message: types.Message):
    await message.answer(TEXT_MESSAGES['start'])


async def reply_to_user(message: types.Message):
    if not message.reply_to_message or not message.reply_to_message.from_user.is_bot:
        return

    cursor.execute(
        "SELECT tg_user_id FROM message_id WHERE bot_message_id = %s",
        (message.reply_to_message.message_id,)
    )
    row = cursor.fetchone()

    if not row:
        await message.reply("❌ Не удалось определить пользователя")
        return

    user_id = row[0]

    if is_banned(user_id):
        await message.reply(TEXT_MESSAGES['is_banned'])
        return

    bot_message = await bot.copy_message(
        chat_id=user_id,
        from_chat_id=message.chat.id,
        message_id=message.message_id
    )

    utc_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute(
        """
        INSERT INTO message_id (user_message_id, bot_message_id, datatime, tg_user_id)
        VALUES (%s, %s, %s, %s)
        """,
        (message.message_id, bot_message.message_id, utc_time, user_id)
    )
    base.commit()



async def forward_handler(message: types.Message):
    try:

        user = message.from_user
        user_id = user.id
        full_name = " ".join(filter(None, [user.first_name, user.last_name]))

        if is_banned(user_id):
            await answer_banned(user_id)
            return

        await message.answer(TEXT_MESSAGES['pending'])

        text = message.text or message.caption or ""

        text_user = TEXT_MESSAGES['message_template'].format(
            text=text,
            full_name=full_name
        )

        # Text
        if message.text and not message.is_command():
            bot_message = await bot.send_message(
                CHAT_ID,
                text_user,
                parse_mode="HTML",
                reply_markup=post_moderation_keyboard(user_id)
            )

        # Sticker is not allowed
        elif message.sticker:
            await message.reply(TEXT_MESSAGES['unsupported_format'])
            return

        # Media
        else:
            bot_message = await bot.copy_message(
                CHAT_ID,
                message.chat.id,
                message.message_id,
                caption=text_user if text else f"👤 <code>{full_name}</code>",
                parse_mode="HTML",
                reply_markup=post_moderation_keyboard(user_id)
            )

        # Save db

        utc_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute(
            """
            INSERT INTO message_id
            (user_message_id, bot_message_id, datatime, tg_user_id)
            VALUES (%s, %s, %s, %s)
            """,
            (message.message_id, bot_message.message_id, utc_time, user_id)
        )

        base.commit()

    except Exception as e:
        await bot.send_message(CHAT_ID, f"FATAL forward_handler error:\n{e}")


# Function which is responsible for editing responses in the chat and edit copied message from bot in private chat
async def chat_edited_messages(message: types.Message):
    if not message.reply_to_message.from_user.is_bot or message.is_command():
        return

    user_id = get_user_id(message)
    if is_banned(user_id):
        await message.reply(TEXT_MESSAGES['is_banned'])
        return

    cursor.execute(f"SELECT bot_message_id FROM message_id WHERE user_message_id = {message.message_id}")
    to_edit_id = cursor.fetchone()[0]
    # Defining type of the message
    if message.text:
        try:
            await bot.edit_message_text(chat_id=user_id, message_id=to_edit_id, text=message.parse_entities(),
                                        parse_mode='HTML', entities=message.entities)
        except Exception as e:
            if type(e) == aiogram.utils.exceptions.MessageToEditNotFound:
                await message.reply(TEXT_MESSAGES['message_not_found'])
    else:
        try:
            await bot.edit_message_caption(chat_id=user_id, message_id=to_edit_id, caption=message.parse_entities(),
                                           parse_mode="HTML")
        except Exception as e:
            if type(e) == aiogram.utils.exceptions.MessageNotModified:
                await message.reply(TEXT_MESSAGES['message_was_not_edited'])
            elif type(e) == aiogram.utils.exceptions.MessageToEditNotFound:
                await message.reply(TEXT_MESSAGES['message_not_found'])


# Function which is responsible for editing messages from users in private chat
async def private_edited_messages(message: types.Message):
    user_id = message.from_user.id
    # Checking if user was banned; if not, sending his message with his id in the end; else, telling him he was banned
    if is_banned(user_id):
        await answer_banned(user_id)
        return

    # Finding bot message to edit by looking for it in SQL table
    cursor.execute(f"SELECT bot_message_id FROM message_id WHERE user_message_id = {message.message_id}")
    to_edit_id = cursor.fetchone()[0]
    # Defining type of the message
    if message.text:
        text_user = TEXT_MESSAGES['message_template'].format(message.from_user.username, message.parse_entities() + '\n\n',
                                                             user_id)
        # Trying to edit text. If not successful - message was not found in database
        try:
            await bot.edit_message_text(text=text_user, chat_id=CHAT_ID, message_id=to_edit_id,
                                        parse_mode="HTML", entities=message.entities)
        except Exception as e:
            if type(e) == aiogram.utils.exceptions.MessageToEditNotFound:
                await message.reply(TEXT_MESSAGES['message_not_found'])
    else:
        text_user = TEXT_MESSAGES['message_template'].format(message.from_user.username,
                                                             message.parse_entities() + '\n\n' if message.caption is not None
                                                             else '', user_id)
        # Bot can edit only caption and text, so if user or chat member is trying to edit photo/video itself, we notify
        # him that he cannot do it.
        try:
            await bot.edit_message_caption(chat_id=CHAT_ID, message_id=to_edit_id, caption=text_user,
                                           parse_mode="HTML")
        except Exception as e:
            if type(e) == aiogram.utils.exceptions.MessageNotModified:
                await message.reply(TEXT_MESSAGES['message_was_not_edited'])
            elif type(e) == aiogram.utils.exceptions.MessageToEditNotFound:
                await message.reply(TEXT_MESSAGES['message_not_found'])


# This function register all needed message handlers with filters and commands
def setup_dispatcher(dp: Dispatcher):
    dp.register_message_handler(starting, commands=["start"])    # Handler for '/start' command
    dp.register_message_handler(filters.IsReplyFilter(True), filters.IDFilter(chat_id=CHAT_ID), reply_to_user,
                                is_reply=True, content_types=['any'])    # Handler for replying to user
    
    # Handler for forwarding users' messages to chat
    dp.register_message_handler(forward_handler, chat_type='private', content_types=['any'])

    # Handler for editing chat messages
    dp.register_edited_message_handler(filters.IsReplyFilter(True), filters.IDFilter(chat_id=CHAT_ID),
                                       chat_edited_messages, is_reply=True, content_types=['any'])

    # Handler for editing users' messages
    dp.register_edited_message_handler(private_edited_messages, content_types=['any'], chat_type='private')