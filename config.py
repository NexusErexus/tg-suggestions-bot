import os

# Bot Data
TOKEN = os.getenv("TELEGRAM_TOKEN") # Get your bot token using https://t.me/BotFather

# Support Chat
CHAT_ID = os.getenv("CHAT_ID") # To find out your channels ID use: https://t.me/getidsbot

# Publication Channel
CHANNEL_ID = os.getenv("CHANNEL_ID") # Channel where posts are published via 📢 button

# Database Data
HOSTNAME = os.getenv("POSTGRES_HOST")
DATABASE = os.getenv("POSTGRES_DB")
USERNAME = os.getenv("POSTGRES_USER")
PORT_ID = os.getenv("POSTGRES_PORT")
DB_PASS = os.getenv("POSTGRES_PASSWORD")
REMOVAL_INTERVAL = os.getenv("ROW_REMOVAL_INTERVAL")

# Predefined text to send, you can change its values to customize your own bot
TEXT_MESSAGES = {
    'start': 'Добро пожаловать 👋 \n\nНапиши свое сообщение здесь и автор рассмотрит его.',
    'message_template': '{text}\n\n👤 <code>{full_name}</code>',
    'is_banned': '❌ Пользователь забанен!',
    'already_banned': '❌ Пользователь уже забанен!',
    'not_banned': '❌ Такого пользователя в бан листе нет!',
    'user_banned': '🚫 Ты не можешь отправлять сообщения в этот бот!',
    'user_unbanned': '🥳 Тебя помиловали и ты снова сможешь писать сообщения!',
    'user_reason_banned': '🚫 Ты не можешь писать сообщения сюда по следующей причине: <i>{}</i>.',
    'has_banned': '✅ Пользователь был успешно забанен!',
    'has_unbanned': '✅ Пользователь успешно был разбанен!',
    'pending': 'Получили! Модерация уже просматривает твое сообщение.',
    'unsupported_format': '❌ Format of your message is not supported and it will not be forwarded.',
    'message_not_found': '❌ It looks like your message was sent more that a day ago. Message to edit was not found!',
    'message_was_not_edited': '❌ Unfortunately you cannot edit images/videos themselves.' 'Please, send a new message.',
    'reply_error': '❌ Please, reply with /ban or /unban only on forwarded from user messages!',
    'help': """ℹ️ <b>Справка по боту-предложке</b>

<b>Кнопки под постами:</b>
🚫 <b>Бан</b> — заблокировать автора поста
🧹 <b>Удалить пост</b> — удалить этот конкретный пост
🗑️ <b>Удалить все посты автора</b> — удалить все посты этого пользователя
📢 <b>Публикация в канал</b> — опубликовать пост в канал

<b>Команды (только для админов):</b>
/clear — удалить все посты в предложке
/banlist — список забаненных пользователей
/ban — забанить автора (ответ на пост),
/unban — разбанить автора (ответ на пост)
/help — показать эту справку"""

}