from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

from create_bot import base, cursor, bot
from handlers.keyboards import (
    clear_confirm_keyboard, banlist_keyboard,
    unban_confirm_keyboard, admin_menu_keyboard
)
from config import *

router = Router()

ADMIN_IDS = {}
BANLIST_PAGE_SIZE = 5


def is_admin(user_id: int) -> bool:
    return int(user_id) in ADMIN_IDS


def is_banned(user_id: int) -> bool:
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


def get_user_info(bot_message_id: int) -> tuple[int, str | None] | None:
    """Возвращает (tg_user_id, full_name) по bot_message_id, или None если не найдено."""
    cursor.execute(
        "SELECT tg_user_id, full_name FROM message_id WHERE bot_message_id = %s",
        (bot_message_id,)
    )
    row = cursor.fetchone()
    return (row[0], row[1]) if row else None


# ─── КОМАНДЫ ─────────────────────────────────────────────────────
@router.message(Command("profile"), F.chat.id == int(CHAT_ID), F.reply_to_message)
async def cmd_profile(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    if not check_replied(message.reply_to_message):
        await message.reply(TEXT_MESSAGES['reply_error'])
        return

    bot_message_id = message.reply_to_message.message_id
    info = get_user_info(bot_message_id)
    if not info:
        await message.reply("❌ Не удалось определить пользователя")
        return
    user_id, full_name = info

    try:
        user = await bot.get_chat(user_id)
        username = f"@{user.username}" if user.username else None
        display_name = " ".join(filter(None, [user.first_name, user.last_name])) or full_name or f"ID: {user_id}"

        if username:
            text = f"👤 <b>{display_name}</b>\n\n<a href='tg://user?id={user_id}'>{username}</a>\n\nID: <code>{user_id}</code>"
        else:
            text = f"👤 <a href='tg://user?id={user_id}'><b>{display_name}</b></a>\n\nID: <code>{user_id}</code>"

        await message.reply(text)
    except Exception:
        await message.reply(f"❌ Не удалось получить профиль. 👤 {full_name or 'Неизвестен'} ID: <code>{user_id}</code>")

    try:
        await message.delete()
    except Exception:
        pass

@router.message(Command("ban"), F.chat.id == int(CHAT_ID), F.reply_to_message)
async def ban_user(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    if not check_replied(message.reply_to_message):
        await message.reply(TEXT_MESSAGES['reply_error'])
        return

    bot_message_id = message.reply_to_message.message_id
    info = get_user_info(bot_message_id)
    
    if not info:
        await message.reply("❌ Не удалось определить пользователя")
        return
    
    user_id, full_name = info

    if user_id == message.from_user.id:
        await message.reply("🚫 Нельзя забанить самого себя.")
        return

    if is_admin(user_id):
        await message.reply("🚫 Нельзя забанить администратора.")
        return
    try:
        reason = message.text.split(' ', maxsplit=1)[1]
    except Exception:
        reason = None

    if is_banned(user_id):
        await message.answer(TEXT_MESSAGES['already_banned'])
    else:
        cursor.execute(
            "INSERT INTO ban_id (user_id, ban_reason, full_name) VALUES (%s, %s, %s)",
            (user_id, reason, full_name)
        )
        base.commit()
        await message.reply(TEXT_MESSAGES['has_banned'])
        # Импортируем здесь, чтобы избежать circular import на уровне модуля
        from handlers.main_handler import answer_banned
        await answer_banned(user_id)

    try:
        await message.delete()
    except Exception:
        pass


@router.message(Command("unban"), F.chat.id == int(CHAT_ID), F.reply_to_message)
async def unban_user(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    if not check_replied(message.reply_to_message):
        await message.reply(TEXT_MESSAGES['reply_error'])
        return

    bot_message_id = message.reply_to_message.message_id
    info = get_user_info(bot_message_id)
    if not info:
        await message.reply("❌ Не удалось определить пользователя")
        return
    user_id, _ = info

    if is_banned(user_id):
        cursor.execute("DELETE FROM ban_id WHERE user_id = %s", (user_id,))
        base.commit()
        await message.reply(TEXT_MESSAGES['has_unbanned'])
        await bot.send_message(chat_id=user_id, text=TEXT_MESSAGES['user_unbanned'])
    else:
        await message.reply(TEXT_MESSAGES['not_banned'])

    try:
        await message.delete()
    except Exception:
        pass


@router.message(Command("start"), F.chat.id == int(CHAT_ID))
async def cmd_start_group(message: types.Message):
    """Создаёт и закрепляет системное сообщение в группе (только для админов)"""
    if not is_admin(message.from_user.id):
        return

    cursor.execute("SELECT message_id FROM system_message LIMIT 1")
    row = cursor.fetchone()

    if row:
        await message.reply(f"ℹ️ Системное сообщение уже существует (ID: {row[0]})")
        return

    sys_msg = await bot.send_message(
        chat_id=CHAT_ID,
        text=TEXT_MESSAGES['system_message']
    )

    await bot.pin_chat_message(
        chat_id=CHAT_ID,
        message_id=sys_msg.message_id,
        disable_notification=True
    )

    cursor.execute(
        "INSERT INTO system_message (message_id) VALUES (%s)",
        (sys_msg.message_id,)
    )
    base.commit()

    await message.reply("✅ Системное сообщение создано и закреплено")


@router.message(Command("clear"), F.chat.id == int(CHAT_ID))
async def cmd_clear(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "⚠️ Вы уверены, что хотите удалить <b>все</b> посты в предложке?",
        reply_markup=clear_confirm_keyboard()
    )

    try:
        await message.delete()
    except Exception:
        pass


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    if message.chat.id == int(CHAT_ID) and is_admin(message.from_user.id):
        await message.answer(
            TEXT_MESSAGES['help'],
            reply_markup=admin_menu_keyboard()
        )
    else:
        await message.answer(TEXT_MESSAGES['help'])


# ─── BANLIST ──────────────────────────────────────────────────────

def get_banlist_page(page: int) -> tuple[list, int]:
    cursor.execute("SELECT COUNT(*) FROM ban_id")
    total = cursor.fetchone()[0]
    total_pages = max(1, (total + BANLIST_PAGE_SIZE - 1) // BANLIST_PAGE_SIZE)

    offset = page * BANLIST_PAGE_SIZE
    cursor.execute(
        "SELECT user_id, full_name FROM ban_id ORDER BY user_id LIMIT %s OFFSET %s",
        (BANLIST_PAGE_SIZE, offset)
    )
    users = cursor.fetchall()
    return users, total_pages


@router.message(Command("banlist"), F.chat.id == int(CHAT_ID))
async def cmd_banlist(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    users, total_pages = get_banlist_page(0)

    if not users:
        await message.answer("📋 Список забаненых пуст.")
        return

    await message.answer(
        f"📋 Забаненые пользователи (стр. 1/{total_pages}):",
        reply_markup=banlist_keyboard(users, 0, total_pages)
    )

    try:
        await message.delete()
    except Exception:
        pass


# ─── ReplyKeyboard КНОПКИ ────────────────────────────────────────

@router.message(F.chat.id == int(CHAT_ID), F.text == "🗑️ Очистить предложку")
async def button_clear(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    await cmd_clear(message)


@router.message(F.chat.id == int(CHAT_ID), F.text == "📋 Банлист")
async def button_banlist(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    await cmd_banlist(message)


@router.message(F.chat.id == int(CHAT_ID), F.text == "ℹ️ Помощь")
async def button_help(message: types.Message):
    await cmd_help(message)


# ─── CALLBACK HANDLERS ───────────────────────────────────────────

@router.callback_query(F.data.startswith("ban:"))
async def callback_ban(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])

    if is_banned(user_id):
        await callback.answer("Пользователь уже забанен", show_alert=True)
        return

    info = get_user_info(callback.message.message_id)
    full_name = info[1] if info else None
    
    if user_id == callback.message.from_user.id:
        await callback.message.reply("🚫 Нельзя забанить самого себя.")
        return

    if is_admin(user_id):
        await callback.message.reply("🚫 Нельзя забанить администратора.")
        return
    cursor.execute(
        "INSERT INTO ban_id (user_id, ban_reason, full_name) VALUES (%s, %s, %s)",
        (user_id, None, full_name)
    )
    base.commit()
    await callback.answer("✅ Пользователь забанен", show_alert=True)

    from handlers.main_handler import answer_banned
    await answer_banned(user_id)


@router.callback_query(F.data == "delete_post")
async def callback_delete_post(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав", show_alert=True)
        return

    keyboard_msg_id = callback.message.message_id
    chat_id = callback.message.chat.id

    # Удаляем связанные сообщения альбома (документы/фото/видео) из media_group_messages
    cursor.execute(
        "SELECT album_message_id FROM media_group_messages WHERE keyboard_message_id = %s",
        (keyboard_msg_id,)
    )
    album_rows = cursor.fetchall()
    for row in album_rows:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=row[0])
        except Exception:
            pass
    if album_rows:
        cursor.execute("DELETE FROM media_group_messages WHERE keyboard_message_id = %s", (keyboard_msg_id,))
        base.commit()

    # Удаляем само сообщение с кнопками (и все связанные записи из message_id)
    cursor.execute("DELETE FROM message_id WHERE bot_message_id = %s", (keyboard_msg_id,))
    base.commit()

    try:
        await bot.delete_message(chat_id=chat_id, message_id=keyboard_msg_id)
    except Exception:
        await callback.answer("❌ Не удалось удалить сообщение", show_alert=True)


@router.callback_query(F.data.startswith("delete_all:"))
async def callback_delete_all(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])
    chat_id = callback.message.chat.id

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
        keyboard_msg_id = row[0]

        # Для каждого поста удаляем связанные сообщения альбома
        cursor.execute(
            "SELECT album_message_id FROM media_group_messages WHERE keyboard_message_id = %s",
            (keyboard_msg_id,)
        )
        album_rows = cursor.fetchall()
        for album_row in album_rows:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=album_row[0])
                deleted += 1
            except Exception:
                pass
        if album_rows:
            cursor.execute("DELETE FROM media_group_messages WHERE keyboard_message_id = %s", (keyboard_msg_id,))

        # Удаляем само сообщение
        try:
            await bot.delete_message(chat_id=chat_id, message_id=keyboard_msg_id)
            deleted += 1
        except Exception:
            pass

    cursor.execute("DELETE FROM message_id WHERE tg_user_id = %s", (user_id,))
    base.commit()

    await callback.answer(f"✅ Удалено {deleted} сообщений", show_alert=True)


@router.callback_query(F.data == "publish")
async def callback_publish(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав", show_alert=True)
        return

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


@router.callback_query(F.data.startswith("profile:"))
async def callback_profile(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])

    try:
        user = await bot.get_chat(user_id)
        username = f"@{user.username}" if user.username else f"ID: {user_id}"
        full_name = " ".join(filter(None, [user.first_name, user.last_name]))

        await callback.answer(
            f"👤 {full_name}\n{username}\n\nПерейти: tg://user?id={user_id}",
            show_alert=True
        )
    except Exception:
        await callback.answer(
            "❌ Не удалось получить профиль пользователя.\nВозможно профиль закрыт или аккаунт удалён.",
            show_alert=True
        )


@router.callback_query(F.data == "clear_confirm")
async def callback_clear_confirm(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав", show_alert=True)
        return

    cursor.execute("SELECT message_id FROM system_message LIMIT 1")
    system_row = cursor.fetchone()
    system_msg_id = system_row[0] if system_row else None

    max_msg_id = callback.message.message_id
    min_msg_id = max(1, max_msg_id - 50000)

    deleted = 0
    for msg_id in range(min_msg_id, max_msg_id + 1):
        if system_msg_id and msg_id == system_msg_id:
            continue
        try:
            await bot.delete_message(chat_id=callback.message.chat.id, message_id=msg_id)
            deleted += 1
        except Exception:
            pass

    await callback.message.edit_text(f"✅ Удалено {deleted} сообщений.")


@router.callback_query(F.data == "clear_cancel")
async def callback_clear_cancel(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав", show_alert=True)
        return

    await callback.message.delete()


@router.callback_query(F.data.startswith("banlist_page:"))
async def callback_banlist_page(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав", show_alert=True)
        return

    page = int(callback.data.split(":")[1])
    users, total_pages = get_banlist_page(page)

    if not users:
        await callback.message.edit_text("📋 Список забаненых пуст.")
        return

    await callback.message.edit_text(
        f"📋 Забаненые пользователи (стр. {page + 1}/{total_pages}):",
        reply_markup=banlist_keyboard(users, page, total_pages)
    )


@router.callback_query(F.data == "banlist_close")
async def callback_banlist_close(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав", show_alert=True)
        return

    await callback.message.delete()


@router.callback_query(F.data.startswith("banlist_user:"))
async def callback_banlist_user(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])

    cursor.execute("SELECT full_name FROM ban_id WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    if not row:
        await callback.answer("❌ Пользователь не найден в списке", show_alert=True)
        return

    full_name = row[0] or f"ID: {user_id}"

    await callback.message.edit_text(
        f"🔓 Разблокировать <b>{full_name}</b>?",
        reply_markup=unban_confirm_keyboard(user_id)
    )


@router.callback_query(F.data.startswith("unban_confirm:"))
async def callback_unban_confirm(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])

    cursor.execute("SELECT full_name FROM ban_id WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    full_name = row[0] if row and row[0] else f"ID: {user_id}"

    cursor.execute("DELETE FROM ban_id WHERE user_id = %s", (user_id,))
    base.commit()

    try:
        await bot.send_message(chat_id=user_id, text=TEXT_MESSAGES['user_unbanned'])
    except Exception:
        pass

    users, total_pages = get_banlist_page(0)
    if not users:
        await callback.message.edit_text(f"✅ {full_name} разблокирован.\n\n📋 Список забаненых пуст.")
    else:
        await callback.message.edit_text(
            f"✅ {full_name} разблокирован.\n\n📋 Забаненые пользователи (стр. 1/{total_pages}):",
            reply_markup=banlist_keyboard(users, 0, total_pages)
        )