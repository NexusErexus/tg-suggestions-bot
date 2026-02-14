import aiogram.utils.exceptions
from aiogram import types, Dispatcher
from aiogram.dispatcher import filters
from datetime import datetime
import asyncio

from config import *
from create_bot import bot, cursor, base
from handlers.admin_handler import is_banned, is_admin, get_user_info
from handlers.keyboards import post_moderation_keyboard

# Временное хранилище для media groups (альбомов)
media_groups = {}

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
    if message.chat.type != 'private':
        # В группе — только для админов
        if is_admin(message.from_user.id):
            await message.answer("✅ Бот работает исправно")
        try:
            await message.delete()
        except Exception:
            pass
    else:
        # В личке — приветствие для всех
        await message.answer(TEXT_MESSAGES['start'])


# Rules command (when '/rules' command is entered)
async def cmd_rules(message: types.Message):
    # # Только в личке
    # if message.chat.type == 'private':
        await message.answer(TEXT_MESSAGES.get('rules', 'Правила временно недоступны.'))


# Handler for unknown commands (blocks all commands except /start and /rules for users)
async def unknown_command(message: types.Message):
    # Только в личке блокируем неизвестные команды
    if message.chat.type == 'private':
        await message.reply(
            "❌ Неизвестная команда.\n\n"
            "Доступные команды:\n"
            "/start — Начать работу\n"
            "/rules — Правила использования бота"
        )


async def reply_to_user(message: types.Message):
    if not message.reply_to_message or not message.reply_to_message.from_user.is_bot:
        return

    # Игнорируем команды — они обрабатываются отдельными handlers
    if message.is_command():
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

    # Берём full_name из существующей записи этого юзера
    cursor.execute(
        "SELECT full_name FROM message_id WHERE tg_user_id = %s AND full_name IS NOT NULL LIMIT 1",
        (user_id,)
    )
    name_row = cursor.fetchone()
    full_name = name_row[0] if name_row else None

    utc_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute(
        """
        INSERT INTO message_id (user_message_id, bot_message_id, datatime, tg_user_id, full_name)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (message.message_id, bot_message.message_id, utc_time, user_id, full_name)
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

        # Блокируем неизвестные команды (они обрабатываются в unknown_command)
        # forward_handler вызывается ПОСЛЕ всех command handlers
        # Если сюда попала команда — значит она неизвестная, просто игнорируем
        if message.is_command():
            return

        # Определяем источник (если forwarded из канала)
        source = None
        if message.forward_from_chat:
            source = message.forward_from_chat.title

        # -------- MEDIA GROUP (альбом) --------
        if message.media_group_id:
            media_group_id = message.media_group_id

            # Если это первое сообщение из альбома — создаём буфер
            if media_group_id not in media_groups:
                media_groups[media_group_id] = {
                    'messages': [],
                    'user_id': user_id,
                    'full_name': full_name,
                    'source': source
                }

            # Добавляем сообщение в буфер
            media_groups[media_group_id]['messages'].append(message)

            # Ждём чтобы собрать весь альбом (задержка 0.5 сек)
            await asyncio.sleep(0.5)

            # Если мы последние кто обрабатывает этот media_group — отправляем
            if media_group_id in media_groups and len(media_groups[media_group_id]['messages']) > 0:
                group_data = media_groups.pop(media_group_id)
                messages = group_data['messages']
                user_id = group_data['user_id']
                full_name = group_data['full_name']
                source = group_data['source']

                # Отвечаем только на первое сообщение
                await messages[0].reply(TEXT_MESSAGES['pending'])

                # Собираем медиа
                media = []
                for msg in messages:
                    if msg.photo:
                        file_id = msg.photo[-1].file_id
                        caption = msg.caption or ""
                        media.append(types.InputMediaPhoto(media=file_id, caption=caption))
                    elif msg.video:
                        media.append(types.InputMediaVideo(media=msg.video.file_id, caption=msg.caption or ""))
                    elif msg.document:
                        media.append(types.InputMediaDocument(media=msg.document.file_id, caption=msg.caption or ""))

                # Подпись только на первом медиа
                text_line = f"👤 <code>{full_name}</code>"
                if source:
                    text_line += f"\n📰 Источник: <b>{source}</b>"

                if media:
                    media[0].caption = (media[0].caption or "") + f"\n\n{text_line}"
                    media[0].parse_mode = "HTML"

                # Отправляем альбом
                sent_messages = await bot.send_media_group(chat_id=CHAT_ID, media=media)

                # Сохраняем в БД только первое сообщение альбома
                utc_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    """
                    INSERT INTO message_id
                    (user_message_id, bot_message_id, datatime, tg_user_id, full_name)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (messages[0].message_id, sent_messages[0].message_id, utc_time, user_id, full_name)
                )
                base.commit()

            return  # Выходим, чтобы не обрабатывать дальше

        # -------- ОБЫЧНЫЕ СООБЩЕНИЯ (не альбом) --------

        await message.reply(TEXT_MESSAGES['pending'])

        text = message.text or message.caption or ""

        # Формируем подпись с источником
        text_user = text
        if text_user:
            text_user += "\n\n"
        text_user += f"👤 <code>{full_name}</code>"
        if source:
            text_user += f"\n📰 Источник: <b>{source}</b>"

        # -------- TEXT --------
        if message.text and not message.is_command():
            bot_message = await bot.send_message(
                CHAT_ID,
                text_user,
                parse_mode="HTML",
                reply_markup=post_moderation_keyboard(user_id)
            )

        # -------- STICKER --------
        elif message.sticker:
            await message.reply(TEXT_MESSAGES['unsupported_format'])
            return

        # -------- MEDIA (одно фото/видео) --------
        else:
            bot_message = await bot.copy_message(
                CHAT_ID,
                message.chat.id,
                message.message_id,
                caption=text_user,
                parse_mode="HTML",
                reply_markup=post_moderation_keyboard(user_id)
            )

        # -------- SAVE DB --------
        utc_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            """
            INSERT INTO message_id
            (user_message_id, bot_message_id, datatime, tg_user_id, full_name)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (message.message_id, bot_message.message_id, utc_time, user_id, full_name)
        )
        base.commit()

    except Exception as e:
        import logging
        import traceback
        
        # Логируем полную ошибку
        logging.error(f"FATAL forward_handler error: {e}")
        logging.error(traceback.format_exc())
        
        # Пытаемся уведомить пользователя
        try:
            await message.reply(
                "❌ Произошла ошибка при пересылке сообщения.\n"
                "Попробуйте позже или обратитесь к администратору."
            )
        except Exception:
            pass
        
        # Пытаемся уведомить админов в группе
        try:
            await bot.send_message(
                CHAT_ID,
                f"⚠️ ОШИБКА в forward_handler:\n\n<code>{e}</code>",
                parse_mode="HTML"
            )
        except Exception:
            pass


# Function which is responsible for editing responses in the chat and edit copied message from bot in private chat
async def chat_edited_messages(message: types.Message):
    if not message.reply_to_message.from_user.is_bot or message.is_command():
        return

    # Получаем user_id из сообщения бота на которое отвечает модератор
    info = get_user_info(message.reply_to_message.message_id)
    if not info:
        await message.reply("❌ Не удалось определить пользователя")
        return
    user_id, _ = info

    if is_banned(user_id):
        await message.reply(TEXT_MESSAGES['is_banned'])
        return

    # Ищем bot_message_id (сообщение отправленное юзеру) по user_message_id (текущее сообщение модератора)
    cursor.execute(
        "SELECT bot_message_id FROM message_id WHERE user_message_id = %s",
        (message.message_id,)
    )
    row = cursor.fetchone()
    if not row:
        await message.reply(TEXT_MESSAGES['message_not_found'])
        return
    to_edit_id = row[0]

    # Defining type of the message
    if message.text:
        try:
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=to_edit_id,
                text=message.text,
                parse_mode='HTML',
                entities=message.entities
            )
        except Exception as e:
            if type(e) == aiogram.utils.exceptions.MessageToEditNotFound:
                await message.reply(TEXT_MESSAGES['message_not_found'])
    else:
        try:
            await bot.edit_message_caption(
                chat_id=user_id,
                message_id=to_edit_id,
                caption=message.caption or "",
                parse_mode="HTML",
                caption_entities=message.caption_entities
            )
        except Exception as e:
            if type(e) == aiogram.utils.exceptions.MessageNotModified:
                await message.reply(TEXT_MESSAGES['message_was_not_edited'])
            elif type(e) == aiogram.utils.exceptions.MessageToEditNotFound:
                await message.reply(TEXT_MESSAGES['message_not_found'])


# Function which is responsible for editing messages from users in private chat
async def private_edited_messages(message: types.Message):
    user_id = message.from_user.id
    full_name = " ".join(filter(None, [message.from_user.first_name, message.from_user.last_name]))

    if is_banned(user_id):
        await answer_banned(user_id)
        return

    # Finding bot message to edit by looking for it in SQL table
    cursor.execute(
        "SELECT bot_message_id FROM message_id WHERE user_message_id = %s",
        (message.message_id,)
    )
    row = cursor.fetchone()
    if not row:
        await message.reply(TEXT_MESSAGES['message_not_found'])
        return
    to_edit_id = row[0]

    # Defining type of the message
    if message.text:
        text_user = TEXT_MESSAGES['message_template'].format(
            text=message.text,
            full_name=full_name
        )
        try:
            await bot.edit_message_text(
                text=text_user,
                chat_id=CHAT_ID,
                message_id=to_edit_id,
                parse_mode="HTML",
                entities=message.entities,
                reply_markup=post_moderation_keyboard(user_id)
            )
        except Exception as e:
            if type(e) == aiogram.utils.exceptions.MessageToEditNotFound:
                await message.reply(TEXT_MESSAGES['message_not_found'])
    else:
        text = message.caption or ""
        text_user = TEXT_MESSAGES['message_template'].format(
            text=text,
            full_name=full_name
        )
        try:
            await bot.edit_message_caption(
                chat_id=CHAT_ID,
                message_id=to_edit_id,
                caption=text_user,
                parse_mode="HTML",
                caption_entities=message.caption_entities,
                reply_markup=post_moderation_keyboard(user_id)
            )
        except Exception as e:
            if type(e) == aiogram.utils.exceptions.MessageNotModified:
                await message.reply(TEXT_MESSAGES['message_was_not_edited'])
            elif type(e) == aiogram.utils.exceptions.MessageToEditNotFound:
                await message.reply(TEXT_MESSAGES['message_not_found'])


# This function register all needed message handlers with filters and commands
def setup_dispatcher(dp: Dispatcher):
    # Command handlers (обрабатываются первыми)
    dp.register_message_handler(starting, commands=["start"])  # Handler for '/start' command
    dp.register_message_handler(cmd_rules, commands=["rules"])  # Handler for '/rules' command
    
    # Unknown command handler (ловит все остальные команды в личке)
    # Должен быть ПОСЛЕ известных команд, но ДО forward_handler
    dp.register_message_handler(unknown_command, lambda msg: msg.text and msg.text.startswith('/'), chat_type='private')
    
    # Reply handler (для ответов админов в группе)
    dp.register_message_handler(filters.IsReplyFilter(True), filters.IDFilter(chat_id=CHAT_ID), reply_to_user,
                                is_reply=True, content_types=['any'])
    
    # Handler for forwarding users' messages to chat (обрабатывается последним)
    dp.register_message_handler(forward_handler, chat_type='private', content_types=['any'])
    
    # Handler for editing chat messages
    dp.register_edited_message_handler(filters.IsReplyFilter(True), filters.IDFilter(chat_id=CHAT_ID),
                                       chat_edited_messages, is_reply=True, content_types=['any'])
    # Handler for editing users' messages
    dp.register_edited_message_handler(private_edited_messages, content_types=['any'], chat_type='private')