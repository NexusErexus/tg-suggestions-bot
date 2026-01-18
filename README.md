## How bot works

1. User sends a message to the bot
2. Bot forwards the message to the chat
3. Chat participant replies to the forwarded message
4. Bot copies the answer and sends it to user

## Features

- __Text, Photos, Videos, Documents, GIFs, Voice Messages__ and __Geolocation__ are supported
- Customisable messages for bot to answer
- Ban/unban users using reply
- Messages editing. Changes would be displayed in private/group chat

> ❗ __Note: changing pictures/videos is not possible, only their captions__

### Banning/unbanning

To ban spamming/unfriendly users, you should reply on forwarded from user message like this: `/ban` or like this: `/ban <reason>`, 
where the reason will be displayed to user if he would try to send something again. Then, bot will reply to you whether 
it was successful or not.

In contrast, to unban users, you should reply on user's message with `/unban` and bot will notify on command success 
or failure.

### Message editing

Message editing is implemented using SQL table. When a message is being sent - bot inserts original message id and
forwarded message id into SQL table. For storage optimization purposes in the table a script was written, which deletes 
row after some time passes, which can be found in [`create_bot.py`](https://github.com/NexusErexus/tg-suggestions-bot/blob/main/create_bot.py) 
To configure time interval after which added entry is to be deleted (1 day by default), edit `.env` variable 
`ROW_REMOVAL_INTERVAL` according to time standards in SQL.

## Config and environment

To setup a bot for your own usage, you should specify those variables in 
[`.env`](https://github.com/NexusErexus/tg-suggestions-bot/blob/main/.env).

``` bash
COMPOSE_FILE=docker-compose.yml

# Bot Data
TELEGRAM_TOKEN="<YOUR BOT TOKEN>" # your bot's token
CHAT_ID=0 # chat id where the bot will forward users' messages

# Database Data
POSTGRES_HOST="<YOUR HOST>" # host of sql database
POSTGRES_PASSWORD="<YOUR PASSWORD>" # password to access database
POSTGRES_DB="<YOUR DATABASE NAME>" # database name
POSTGRES_USER="<USER>" # username to log in 
POSTGRES_PORT=5432 # port to connect to database
PGDATA=/var/lib/postgresql/data
ROW_REMOVAL_INTERVAL="1 days" # interval after which an entry is removed from the message table
```

To change default text to your custom, redefine values of the dictionary for each phrase in 
[`config.py`](https://github.com/NexusErexus/tg-suggestions-bot/blob/main/config.py).

``` bash
# Predefined text to send
TEXT_MESSAGES = {
    'start': 'Welcome to Suggestions Bot 👋 \n\n Please, send your message and we will process your request.',
    'message_template': '<i>Message from: <b>@{0}</b>.</i>\n\n{1}<b>id: {2}</b>',
    'is_banned': '❌ User is banned!', 'has_banned': '✅ User has been successfully banned!',
    'already_banned': '❌ User is already banned!', 'has_unbanned': '✅ User has been successfully un-banned!',
    'not_banned': '❌ There is no such user in the ban list!',
    'user_banned': '🚫 You cannot send messages to this bot!',
    'user_unbanned': '🥳 You have proven your innocence, and now you can write to this bot again!',
    'user_reason_banned': '🚫 You cannot send messages to this bot due to the reason: <i>{}</i>.',
    'pending': 'Thank you for your request! We are already into processing it.',
    'unsupported_format': '❌ Format of your message is not supported and it will not be forwarded.',
    'message_not_found': '❌ It looks like your message was sent more that a day ago. Message to edit was not found!',
    'message_was_not_edited': '❌ Unfortunately you cannot edit images/videos themselves.'
                              'Please, send a new message.',
    'reply_error': '❌ Please, reply with /ban or /unban only on forwarded from user messages!'
}
```

## Installation guide

1. Clone this repository using terminal or tools in your IDE: 
`git clone https://github.com/NexusErexus/tg-suggestions-bot.git`
2. Change directory in terminal `cd $repository-direcory`
3. Download requirements `pip install -r requirements.txt`
4. Edit and update [`.env`](https://github.com/NexusErexus/tg-suggestions-bot/blob/main/.env) and/or 
[`config.py`](https://github.com/NexusErexus/tg-suggestions-bot/blob/main/config.py)
5. Launch Docker
6. Run the bot with `docker compose up --build` or with [GNU Make](https://www.gnu.org/software/make/):
`make up`


## Как работает бот

1. Пользователь отправляет сообщение боту
2. Бот пересылает сообщение в чат
3. Участник чата отвечает на пересланное сообщение
4. Бот копирует ответ и отправляет его пользователю

## Особенности
- Поддерживаются Текст, Изображения, Видео, Документы, GIF, Голосовые сообщения и Геолокация
- Кастомизация стандартных ответов бота на триггеры или команды
- Бан/разбан пользователей с помощью ответа на сообщение
- Редактирование сообщений. Изменения будут отображаться в приватном/групповом чате

>❗ Примечание: изменить изображение/видео невозможно, только подпись

### Бан / разбан

Для того чтобы забанить пользователей, которые спамят или ведут себя недружелюбно, вам нужно ответить на сообщение
пользователя так: /ban или так: /ban <причина>, где причина будет отображаться, если этот пользователь снова попытается
что-то отправить. После этого бот ответит статусом выполнения операции.

В свою очередь, чтобы разбанить пользователя, нужно ответить на сообщение пользователя /unban, и бот ответит,
выполнилась ли команда успешно или нет.

### Редактирование сообщений

Редактирование сообщений реализовано с помощью SQL-таблицы. Когда приходит сообщение — бот вставляет
в таблицу id оригинального сообщения и id пересланного сообщения. Для оптимизации места в таблице был
написан триггер, который удаляет строку через некоторое время (проверка времени осуществляется, когда новый элемент добавляется
в таблицу). Триггер устанавливается в create_bot.py.
Чтобы изменить время до удаления записи (по умолчанию 1 день), настройте переменную окружения
ROW_REMOVAL_INTERVAL согласно формату времени SQL.

## Config и переменные окружения

Чтобы изменить стандартный текст ответов бота на свой собственный, измените значения в словаре для каждой фразы в 
[`.env`](https://github.com/NexusErexus/tg-suggestions-bot/blob/main/.env)

``` bash
COMPOSE_FILE=docker-compose.yml

# Bot Data
TELEGRAM_TOKEN="<YOUR BOT TOKEN>" # токен вашего бота
CHAT_ID=0 # id чата, куда бот будет пересылать сообщения от пользователей

# Database Data
POSTGRES_HOST="<YOUR HOST>" # хост sql базы данных
POSTGRES_PASSWORD="<YOUR PASSWORD>" # # пароль для базы данных
POSTGRES_DB="<YOUR DATABASE NAME>" # имя базы данных
POSTGRES_USER="<USER>" # username для входа в базу данных
POSTGRES_PORT=5432 # порт для подключения к базе данных
PGDATA=/var/lib/postgresql/data
ROW_REMOVAL_INTERVAL="1 days" # интервал, после которого запись о сообщении удаляется из таблицы
```

Чтобы изменить стандартный текст ответов бота на свой собственный, измените значения в словаре для каждой фразы в 
[`config.py`](https://github.com/NexusErexus/tg-suggestions-bot/blob/main/config.py)

``` bash
# Predefined text to send
TEXT_MESSAGES = {
    'start': 'Добро пожаловать 👋\n\nНапишите свой вопрос / предложение, и мы ответим Вам в ближайшее время.',
    'message_template': '<i>Сообщение от: <b>@{0}</b>.</i>\n\n{1}<b>id: {2}</b>',
    'is_banned': '❌ Пользователь забанен!',
    'has_banned': '✅ Пользователь был успешно забанен!',
    'already_banned': '❌ Пользователь уже забанен!',
    'has_unbanned': '✅ Пользователь был успешно разбанен!',
    'not_banned': '❌ Такого пользователя нет в бан-листе!',
    'user_banned': '🚫 Вы больше не можете писать в бот предложений!',
    'user_reason_banned': '🚫 Вы больше не можете писать в бот предложений по причине: <i>{}</i>.',
    'user_unbanned': '🥳 Благодать снизошла с небес, и теперь вы снова можете писать в бот предложений!',
    'pending': 'Спасибо за ваше обращение. Мы уже обрабатываем ваш запрос!',
    'unsupported_format': '❌ Формат вашего сообщения не поддерживается, оно не будет переслано.',
    'message_not_found': '❌ Похоже, что вы отправляли сообщение более трёх суток назад, сообщение не было найдено!',
    'message_was_not_edited': '❌ К сожалению, нельзя редактировать изображения в сообщениях. '
                              'Пожалуйста, отправьте новое изображение',
    'reply_error': '❌ Пожалуйста, отвечайте командами /ban или /unban только на пересланные от пользователей сообщения!'
}
```

## Керівництво по встановленню

1. Клонируйте репозиторий с помощью терминала или инструментов в вашей IDE: `git clone https://github.com/NexusErexus/tg-suggestions-bot.git`
2. Перейдите в папку в терминале `cd $repository-directory`
3. Установите зависимости `pip install -r requirements.txt`
4. Отредактируйте и обновите [`.env`](https://github.com/NexusErexus/tg-suggestions-bot/blob/main/.env) и/или
[`config.py`](https://github.com/NexusErexus/tg-suggestions-bot/blob/main/config.py)
5. Запустите Docker
6. Запустите бота в терминале `docker compose up --build` или с помощью [GNU Make](https://www.gnu.org/software/make/):
`make up`
