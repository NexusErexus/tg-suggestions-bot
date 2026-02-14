from create_bot import base, cursor, bot, dp
from handlers import main_handler
from handlers.keyboards import clear_confirm_keyboard, banlist_keyboard, unban_confirm_keyboard, admin_menu_keyboard
from aiogram import types, Dispatcher
from aiogram.dispatcher import filters
from config import *


ADMIN_IDS = {} # id admin here
BANLIST_PAGE_SIZE = 10


def is_admin(user_id: int) -> bool:
    return int(user_id) in ADMIN_IDS
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


def get_user_info(bot_message_id: int) -> tuple[int, str | None] | None:
    """Возвращает (tg_user_id, full_name) по bot_message_id, или None если не найдено."""
    cursor.execute(
        "SELECT tg_user_id, full_name FROM message_id WHERE bot_message_id = %s",
        (bot_message_id,)
    )
    row = cursor.fetchone()
    return (row[0], row[1]) if row else None


# Function to ban user from writing to this bot using SQL
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
        await main_handler.answer_banned(user_id)
    
    # Удаляем команду из чата
    try:
        await message.delete()
    except Exception:
        pass


# Function to unban user from ban list
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
    
    # Удаляем команду из чата
    try:
        await message.delete()
    except Exception:
        pass


# ─── CALLBACK HANDLERS ───────────────────────────────────────────

# 🚫 Бан пользователя через кнопку
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

    cursor.execute(
        "INSERT INTO ban_id (user_id, ban_reason, full_name) VALUES (%s, %s, %s)",
        (user_id, None, full_name)
    )
    base.commit()
    await callback.answer("✅ Пользователь забанен", show_alert=True)
    await main_handler.answer_banned(user_id)


# 🧹 Удалить конкретный пост в чате
async def callback_delete_post(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав", show_alert=True)
        return

    try:
        await bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id)
    except Exception:
        await callback.answer("❌ Не удалось удалить сообщение", show_alert=True)


# 🗑️ Удалить все посты автора в чате
async def callback_delete_all(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав", show_alert=True)
        return

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
            pass  # Сообщение уже удалено или недоступно

    # Удаляем записи из БД для этого пользователя
    cursor.execute("DELETE FROM message_id WHERE tg_user_id = %s", (user_id,))
    base.commit()

    await callback.answer(f"✅ Удалено {deleted} сообщений", show_alert=True)


# 📢 Публикация поста в канал
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


# 👤 Профиль пользователя
async def callback_profile(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])

    try:
        # Пытаемся получить информацию о пользователе
        user = await bot.get_chat(user_id)
        
        # Если получилось — профиль открыт, показываем ссылку
        username = f"@{user.username}" if user.username else f"ID: {user_id}"
        full_name = " ".join(filter(None, [user.first_name, user.last_name]))
        
        await callback.answer(
            f"👤 {full_name}\n{username}\n\nПерейти: tg://user?id={user_id}",
            show_alert=True
        )
    except Exception as e:
        # Если ошибка — профиль закрыт или пользователь удалил аккаунт
        await callback.answer(
            "❌ Не удалось получить профиль пользователя.\nВозможно профиль закрыт или аккаунт удалён.",
            show_alert=True
        )

# ─── /clear ──────────────────────────────────────────────────────

async def cmd_clear(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "⚠️ Вы уверены, что хотите удалить <b>все</b> посты в предложке?",
        parse_mode="HTML",
        reply_markup=clear_confirm_keyboard()
    )
    
    # Удаляем команду из чата
    try:
        await message.delete()
    except Exception:
        pass

async def callback_clear_confirm(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав", show_alert=True)
        return

    # Берём ID системного сообщения
    cursor.execute("SELECT message_id FROM system_message LIMIT 1")
    system_row = cursor.fetchone()
    system_msg_id = system_row[0] if system_row else None

    # Удаляем все сообщения в диапазоне (последние 50000)
    max_msg_id = callback.message.message_id
    min_msg_id = max(1, max_msg_id - 50000)  # Последние 50000 сообщений

    deleted = 0
    for msg_id in range(min_msg_id, max_msg_id + 1):
        # Пропускаем системное сообщение
        if system_msg_id and msg_id == system_msg_id:
            continue
        
        try:
            await bot.delete_message(chat_id=callback.message.chat.id, message_id=msg_id)
            deleted += 1
        except Exception:
            pass  # Сообщение уже удалено или недоступно

    await callback.message.edit_text(f"✅ Удалено {deleted} сообщений.")

async def callback_clear_cancel(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав", show_alert=True)
        return

    await callback.message.delete()


# ─── /banlist ─────────────────────────────────────────────────────

def get_banlist_page(page: int) -> tuple[list, int]:
    """Возвращает список забаненых на странице и общее кол-во страниц."""
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
    
    # Удаляем команду из чата
    try:
        await message.delete()
    except Exception:
        pass


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


async def callback_banlist_close(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав", show_alert=True)
        return

    await callback.message.delete()


async def callback_banlist_user(callback: types.CallbackQuery):
    """Нажатие на имя забаненого — показываем подтверждение разбана."""
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
        parse_mode="HTML",
        reply_markup=unban_confirm_keyboard(user_id)
    )


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
        pass  # Пользователь может не иметь диалога с ботом

    # После разбана возвращаем список на первую страницу
    users, total_pages = get_banlist_page(0)
    if not users:
        await callback.message.edit_text(f"✅ {full_name} разблокирован.\n\n📋 Список забаненых пуст.")
    else:
        await callback.message.edit_text(
            f"✅ {full_name} разблокирован.\n\n📋 Забаненые пользователи (стр. 1/{total_pages}):",
            reply_markup=banlist_keyboard(users, 0, total_pages)
        )


# ─── /help ────────────────────────────────────────────────────────

async def cmd_help(message: types.Message):
    # Если админ пишет в группе предложки — отправляем с клавиатурой
    if message.chat.id == int(CHAT_ID) and is_admin(message.from_user.id):
        await message.answer(
            TEXT_MESSAGES['help'],
            parse_mode="HTML",
            reply_markup=admin_menu_keyboard()
        )
    else:
        await message.answer(TEXT_MESSAGES['help'], parse_mode="HTML")


# ─── Обработчики кнопок ReplyKeyboard ────────────────────────────

async def button_clear(message: types.Message):
    """Обработчик кнопки 'Очистить предложку' — вызывает cmd_clear"""
    if not is_admin(message.from_user.id):
        return
    await cmd_clear(message)


async def button_banlist(message: types.Message):
    """Обработчик кнопки 'Банлист' — вызывает cmd_banlist"""
    if not is_admin(message.from_user.id):
        return
    await cmd_banlist(message)


async def button_help(message: types.Message):
    """Обработчик кнопки 'Помощь' — вызывает cmd_help"""
    await cmd_help(message)


# Registering all dispatchers with their filters and commands
def setup_dispatcher(dp: Dispatcher):
    # Callback handlers для кнопок на постах
    dp.register_callback_query_handler(callback_ban, lambda c: c.data and c.data.startswith("ban:"))
    dp.register_callback_query_handler(callback_delete_post, lambda c: c.data == "delete_post")
    dp.register_callback_query_handler(callback_delete_all, lambda c: c.data and c.data.startswith("delete_all:"))
    dp.register_callback_query_handler(callback_publish, lambda c: c.data == "publish")
    dp.register_callback_query_handler(callback_profile, lambda c: c.data and c.data.startswith("profile:"))


    # Callback handlers для /clear
    dp.register_callback_query_handler(callback_clear_confirm, lambda c: c.data == "clear_confirm")
    dp.register_callback_query_handler(callback_clear_cancel, lambda c: c.data == "clear_cancel")

    # Callback handlers для /banlist
    dp.register_callback_query_handler(callback_banlist_page, lambda c: c.data and c.data.startswith("banlist_page:"))
    dp.register_callback_query_handler(callback_banlist_close, lambda c: c.data == "banlist_close")
    dp.register_callback_query_handler(callback_banlist_user, lambda c: c.data and c.data.startswith("banlist_user:"))
    dp.register_callback_query_handler(callback_unban_confirm, lambda c: c.data and c.data.startswith("unban_confirm:"))

    # Command handlers
    dp.register_message_handler(cmd_help, commands=["help"])  # Доступна везде
    #dp.register_message_handler(filters.IDFilter(chat_id=CHAT_ID), cmd_start_group, commands=["start"])  # /start в группе
    dp.register_message_handler(filters.IDFilter(chat_id=CHAT_ID), cmd_clear, commands=["clear"])
    dp.register_message_handler(filters.IDFilter(chat_id=CHAT_ID), cmd_banlist, commands=["banlist"])
    dp.register_message_handler(filters.IsReplyFilter(True), filters.IDFilter(chat_id=CHAT_ID), ban_user,
                                commands=["ban"], is_reply=True)
    dp.register_message_handler(filters.IsReplyFilter(True), filters.IDFilter(chat_id=CHAT_ID), unban_user,
                                commands=["unban"], is_reply=True)

    # ReplyKeyboard button handlers (текстовые сообщения от кнопок)
    dp.register_message_handler(
        button_clear,
        filters.IDFilter(chat_id=CHAT_ID),
        filters.Text(equals="🗑️ Очистить предложку")
    )
    dp.register_message_handler(
        button_banlist,
        filters.IDFilter(chat_id=CHAT_ID),
        filters.Text(equals="📋 Банлист")
    )
    dp.register_message_handler(
        button_help,
        filters.IDFilter(chat_id=CHAT_ID),
        filters.Text(equals="ℹ️ Помощь")
    )