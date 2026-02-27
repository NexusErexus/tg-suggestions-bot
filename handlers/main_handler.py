import logging
import traceback
import asyncio
from datetime import datetime

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.text_decorations import html_decoration
from aiogram.types import MessageOriginChannel

from config import *
from create_bot import bot, cursor, base
from handlers.admin_handler import is_banned, is_admin, get_user_info
from handlers.keyboards import post_moderation_keyboard

router = Router()

# Временное хранилище для media groups (альбомов)
media_groups = {}


# ─── ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ─────────────────────────────────────

def get_html_caption(message: types.Message) -> str:
    """Возвращает HTML-представление caption сообщения."""
    if message.caption:
        return html_decoration.unparse(message.caption, message.caption_entities or [])
    return ""


def get_html_text(message: types.Message) -> str:
    """Возвращает HTML-представление текста сообщения."""
    if message.text:
        return message.html_text
    return ""


async def answer_banned(user_id: int):
    """Отвечает забаненому пользователю с учётом причины бана."""
    cursor.execute('SELECT ban_reason FROM ban_id WHERE user_id = %s', (user_id,))
    row = cursor.fetchone()
    reason = row[0] if row else None
    if reason is None:
        await bot.send_message(chat_id=user_id, text=TEXT_MESSAGES['user_banned'])
    else:
        await bot.send_message(chat_id=user_id, text=TEXT_MESSAGES['user_reason_banned'].format(reason))


# ─── КОМАНДЫ ─────────────────────────────────────────────────────

@router.message(Command("start"))
async def starting(message: types.Message):
    if message.chat.type != 'private':
        if is_admin(message.from_user.id):
            await message.answer("✅ Бот работает исправно")
        try:
            await message.delete()
        except Exception:
            pass
    else:
        await message.answer(TEXT_MESSAGES['start'])


@router.message(Command("rules"), F.chat.type == "private")
async def cmd_rules(message: types.Message):
    await message.answer(TEXT_MESSAGES.get('rules', 'Правила временно недоступны.'))


# Неизвестные команды в личке (должен быть после всех Command-хендлеров)
@router.message(F.chat.type == "private", F.text.startswith('/'))
async def unknown_command(message: types.Message):
    await message.reply(
        "❌ Неизвестная команда.\n\n"
        "Доступные команды:\n"
        "/start — начать работу\n"
        "/rules — правила использования"
    )


# ─── ОТВЕТ АДМИНА НА ПОСТ В ГРУППЕ ──────────────────────────────

KEYBOARD_BUTTONS = {"🗑️ Очистить предложку", "📋 Банлист", "ℹ️ Помощь"}


@router.message(
    F.chat.id == int(CHAT_ID),
    F.reply_to_message,
    F.reply_to_message.from_user.is_bot == True
)
async def reply_to_user(message: types.Message):
    # Игнорируем команды и кнопки ReplyKeyboard
    if message.text and (message.text.startswith('/') or message.text in KEYBOARD_BUTTONS):
        return

    cursor.execute(
        "SELECT tg_user_id FROM message_id WHERE bot_message_id = %s",
        (message.reply_to_message.message_id,)
    )
    row = cursor.fetchone()

    if not row:
        return  # Служебное сообщение бота — игнорируем

    user_id = row[0]

    if is_banned(user_id):
        await message.reply(TEXT_MESSAGES['is_banned'])
        return

    bot_message = await bot.copy_message(
        chat_id=user_id,
        from_chat_id=message.chat.id,
        message_id=message.message_id
    )

    cursor.execute(
        "SELECT full_name FROM message_id WHERE tg_user_id = %s AND full_name IS NOT NULL LIMIT 1",
        (user_id,)
    )
    name_row = cursor.fetchone()
    full_name = name_row[0] if name_row else None

    utc_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute(
        "INSERT INTO message_id (user_message_id, bot_message_id, datatime, tg_user_id, full_name) VALUES (%s, %s, %s, %s, %s)",
        (message.message_id, bot_message.message_id, utc_time, user_id, full_name)
    )
    base.commit()


# ─── ПЕРЕСЫЛКА СООБЩЕНИЙ ОТ ПОЛЬЗОВАТЕЛЕЙ ────────────────────────

@router.message(F.chat.type == "private")
async def forward_handler(message: types.Message):
    try:
        user = message.from_user
        user_id = user.id
        full_name = " ".join(filter(None, [user.first_name, user.last_name]))
        username = user.username

        if is_banned(user_id):
            await answer_banned(user_id)
            return

        # Блокируем команды (они обрабатываются выше)
        if message.text and message.text.startswith('/'):
            return

        # -------- ФИЛЬТР ТИПОВ --------
        is_allowed = (
            message.text
            or message.photo
            or message.video
            or message.document
            or message.media_group_id
            or message.forward_origin  # aiogram 3: вместо forward_from_chat
        )
        if not is_allowed:
            await message.reply(TEXT_MESSAGES['unsupported_format'])
            return

        # Определяем источник (если forwarded из канала)
        source = None
        if message.forward_origin and isinstance(message.forward_origin, MessageOriginChannel):
            source = message.forward_origin.chat.title

        # -------- MEDIA GROUP (альбом) --------
        if message.media_group_id:
            media_group_id = message.media_group_id

            if media_group_id not in media_groups:
                media_groups[media_group_id] = {
                    'messages': [],
                    'user_id': user_id,
                    'full_name': full_name,
                    'username': username,
                    'source': source
                }

            media_groups[media_group_id]['messages'].append(message)

            await asyncio.sleep(0.5)

            if media_group_id in media_groups and len(media_groups[media_group_id]['messages']) > 0:
                group_data = media_groups.pop(media_group_id)
                messages = group_data['messages']
                user_id = group_data['user_id']
                full_name = group_data['full_name']
                username = group_data['username']
                source = group_data['source']

                await messages[0].answer(TEXT_MESSAGES['pending'])

                # Собираем медиа. Подписи >1024 символов убираем из медиа
                # и сохраняем отдельно, чтобы отправить текстом после альбома
                media = []
                long_captions = []  # [(индекс, текст)] — подписи которые не влезли
                for i, msg in enumerate(messages):
                    caption = get_html_caption(msg)
                    if len(caption) > 1024:
                        long_captions.append((i, caption))
                        caption = ""

                    if msg.photo:
                        media.append(types.InputMediaPhoto(
                            media=msg.photo[-1].file_id,
                            caption=caption,
                            parse_mode="HTML"
                        ))
                    elif msg.video:
                        media.append(types.InputMediaVideo(
                            media=msg.video.file_id,
                            caption=caption,
                            parse_mode="HTML"
                        ))
                    elif msg.document:
                        media.append(types.InputMediaDocument(
                            media=msg.document.file_id,
                            caption=caption,
                            parse_mode="HTML"
                        ))

                # Метаданные — всегда в сообщении "Альбом выше", не в медиа
                metadata_html = f"👤 <code>{full_name}</code>"
                if source:
                    metadata_html += f"\n📰 Источник: <b>{source}</b>"

                # Отправляем альбом в отдельном try/except —
                # даже если send_media_group упадёт, keyboard_message всё равно отправится
                sent_messages = []
                try:
                    sent_messages = await bot.send_media_group(chat_id=CHAT_ID, media=media)
                except Exception as e:
                    logging.error(f"send_media_group error: {e}")
                    await bot.send_message(CHAT_ID, f"⚠️ Ошибка при отправке альбома: <code>{e}</code>")

                # Если были длинные подписи — отправляем их отдельными сообщениями с кнопками
                for _, caption_text in long_captions:
                    long_msg = await bot.send_message(
                        CHAT_ID,
                        caption_text,
                        reply_markup=post_moderation_keyboard(user_id, username)
                    )
                    utc_time_lc = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute(
                        "INSERT INTO message_id (user_message_id, bot_message_id, datatime, tg_user_id, full_name, username, source) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (messages[0].message_id, long_msg.message_id, utc_time_lc, user_id, full_name, username, source)
                    )

                # Сообщение с кнопками — отправляется всегда, даже если альбом не ушёл
                keyboard_message = await bot.send_message(
                    CHAT_ID,
                    text=f"🎞 Альбом выше\n\n{metadata_html}",
                    reply_markup=post_moderation_keyboard(user_id, username)
                )

                # Сохраняем file_id медиа альбома
                for i, sent_msg in enumerate(sent_messages):
                    orig_msg = messages[i] if i < len(messages) else messages[-1]
                    if orig_msg.photo:
                        file_id = orig_msg.photo[-1].file_id
                        media_type = "photo"
                        caption_html = get_html_caption(orig_msg)
                    elif orig_msg.video:
                        file_id = orig_msg.video.file_id
                        media_type = "video"
                        caption_html = get_html_caption(orig_msg)
                    else:
                        continue

                    cursor.execute(
                        "INSERT INTO media_group_messages (keyboard_message_id, album_message_id, file_id, media_type, caption) VALUES (%s, %s, %s, %s, %s)",
                        (keyboard_message.message_id, sent_msg.message_id, file_id, media_type, caption_html)
                    )

                utc_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    "INSERT INTO message_id (user_message_id, bot_message_id, datatime, tg_user_id, full_name, username, source) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (messages[0].message_id, keyboard_message.message_id, utc_time, user_id, full_name, username, source)
                )
                base.commit()

            return

        # -------- ОБЫЧНЫЕ СООБЩЕНИЯ --------

        await message.answer(TEXT_MESSAGES['pending'])

        if message.text:
            original_html = get_html_text(message)
        else:
            original_html = get_html_caption(message)

        metadata_html = f"👤 <code>{full_name}</code>"
        if source:
            metadata_html += f"\n📰 Источник: <b>{source}</b>"

        # TEXT
        if message.text:
            final_html = (original_html + "\n\n" + metadata_html) if original_html else metadata_html
            bot_message = await bot.send_message(
                CHAT_ID,
                final_html,
                reply_markup=post_moderation_keyboard(user_id, username)
            )

        # MEDIA (фото/видео)
        else:
            full_caption_html = (original_html + "\n\n" + metadata_html) if original_html else metadata_html

            if len(full_caption_html) > 1024:
                # Медиа с метаданными
                if message.photo:
                    bot_message = await bot.send_photo(
                        CHAT_ID, message.photo[-1].file_id,
                        caption=metadata_html,
                        reply_markup=post_moderation_keyboard(user_id, username)
                    )
                elif message.video:
                    bot_message = await bot.send_video(
                        CHAT_ID, message.video.file_id,
                        caption=metadata_html,
                        reply_markup=post_moderation_keyboard(user_id, username)
                    )
                elif message.document:
                    bot_message = await bot.send_document(
                        CHAT_ID, message.document.file_id,
                        caption=metadata_html,
                        reply_markup=post_moderation_keyboard(user_id, username)
                    )
                else:
                    bot_message = await bot.copy_message(
                        CHAT_ID, message.chat.id, message.message_id,
                        caption=metadata_html,
                        reply_markup=post_moderation_keyboard(user_id, username)
                    )

                # Текст отдельно
                if original_html:
                    text_message = await bot.send_message(
                        CHAT_ID, original_html,
                        reply_markup=post_moderation_keyboard(user_id, username)
                    )

                utc_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    "INSERT INTO message_id (user_message_id, bot_message_id, datatime, tg_user_id, full_name, username, source) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (message.message_id, bot_message.message_id, utc_time, user_id, full_name, username, source)
                )
                if original_html:
                    cursor.execute(
                        "INSERT INTO message_id (user_message_id, bot_message_id, datatime, tg_user_id, full_name, username, source) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (message.message_id, text_message.message_id, utc_time, user_id, full_name, username, source)
                    )
                base.commit()
                return

            else:
                if message.photo:
                    bot_message = await bot.send_photo(
                        CHAT_ID, message.photo[-1].file_id,
                        caption=full_caption_html,
                        reply_markup=post_moderation_keyboard(user_id, username)
                    )
                elif message.video:
                    bot_message = await bot.send_video(
                        CHAT_ID, message.video.file_id,
                        caption=full_caption_html,
                        reply_markup=post_moderation_keyboard(user_id, username)
                    )
                elif message.document:
                    bot_message = await bot.send_document(
                        CHAT_ID, message.document.file_id,
                        caption=full_caption_html,
                        reply_markup=post_moderation_keyboard(user_id, username)
                    )
                else:
                    bot_message = await bot.copy_message(
                        CHAT_ID, message.chat.id, message.message_id,
                        caption=full_caption_html,
                        reply_markup=post_moderation_keyboard(user_id, username)
                    )

        # SAVE DB
        utc_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            "INSERT INTO message_id (user_message_id, bot_message_id, datatime, tg_user_id, full_name, username, source) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (message.message_id, bot_message.message_id, utc_time, user_id, full_name, username, source)
        )
        base.commit()

    except Exception as e:
        logging.error(f"FATAL forward_handler error: {e}")
        logging.error(traceback.format_exc())

        try:
            await message.reply(
                "❌ Произошла ошибка при пересылке сообщения.\n"
                "Попробуйте позже или обратитесь к администратору."
            )
        except Exception:
            pass

        try:
            await bot.send_message(
                CHAT_ID,
                f"⚠️ ОШИБКА в forward_handler:\n\n<code>{e}</code>"
            )
        except Exception:
            pass


# ─── РЕДАКТИРОВАНИЕ СООБЩЕНИЙ ─────────────────────────────────────

@router.edited_message(
    F.chat.id == int(CHAT_ID),
    F.reply_to_message,
    F.reply_to_message.from_user.is_bot == True
)
async def chat_edited_messages(message: types.Message):
    if message.text and message.text.startswith('/'):
        return

    info = get_user_info(message.reply_to_message.message_id)
    if not info:
        return
    user_id, _ = info  # get_user_info возвращает (tg_user_id, full_name)

    if is_banned(user_id):
        await message.reply(TEXT_MESSAGES['is_banned'])
        return

    cursor.execute(
        "SELECT bot_message_id FROM message_id WHERE user_message_id = %s AND tg_user_id = %s",
        (message.message_id, user_id)
    )
    row = cursor.fetchone()
    if not row:
        await message.reply(TEXT_MESSAGES['message_not_found'])
        return
    to_edit_id = row[0]

    if message.text:
        try:
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=to_edit_id,
                text=message.text,
                entities=message.entities
            )
        except TelegramBadRequest as e:
            if "message to edit not found" in str(e).lower():
                await message.reply(TEXT_MESSAGES['message_not_found'])
    else:
        try:
            await bot.edit_message_caption(
                chat_id=user_id,
                message_id=to_edit_id,
                caption=message.caption or "",
                caption_entities=message.caption_entities
            )
        except TelegramBadRequest as e:
            err = str(e).lower()
            if "message is not modified" in err:
                await message.reply(TEXT_MESSAGES['message_was_not_edited'])
            elif "message to edit not found" in err:
                await message.reply(TEXT_MESSAGES['message_not_found'])


@router.edited_message(F.chat.type == "private")
async def private_edited_messages(message: types.Message):
    user_id = message.from_user.id
    full_name = " ".join(filter(None, [message.from_user.first_name, message.from_user.last_name]))

    if is_banned(user_id):
        await answer_banned(user_id)
        return

    cursor.execute(
        "SELECT bot_message_id FROM message_id WHERE user_message_id = %s",
        (message.message_id,)
    )
    row = cursor.fetchone()
    if not row:
        await message.reply(TEXT_MESSAGES['message_not_found'])
        return
    to_edit_id = row[0]

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
                entities=message.entities,
                reply_markup=post_moderation_keyboard(user_id)
            )
        except TelegramBadRequest as e:
            if "message to edit not found" in str(e).lower():
                await message.reply(TEXT_MESSAGES['message_not_found'])
    else:
        text_user = TEXT_MESSAGES['message_template'].format(
            text=message.caption or "",
            full_name=full_name
        )
        try:
            await bot.edit_message_caption(
                chat_id=CHAT_ID,
                message_id=to_edit_id,
                caption=text_user,
                caption_entities=message.caption_entities,
                reply_markup=post_moderation_keyboard(user_id)
            )
        except TelegramBadRequest as e:
            err = str(e).lower()
            if "message is not modified" in err:
                await message.reply(TEXT_MESSAGES['message_was_not_edited'])
            elif "message to edit not found" in err:
                await message.reply(TEXT_MESSAGES['message_not_found'])