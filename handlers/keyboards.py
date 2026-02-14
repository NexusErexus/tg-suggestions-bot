from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


def post_moderation_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🚫 Бан",
                callback_data=f"ban:{user_id}"
            ),
            InlineKeyboardButton(
                text="🧹 Удалить пост",
                callback_data="delete_post"
            ),
        ],
        [
            InlineKeyboardButton(
                text="🗑️ Удалить все посты автора",
                callback_data=f"delete_all:{user_id}"
            ),
            InlineKeyboardButton(
                text="📢 Публикация в канал",
                callback_data="publish"
            ),
        ],
        [
            InlineKeyboardButton(
                text="👤 Профиль",
                callback_data=f"profile:{user_id}"
            ),
        ],
    ])

# Подтверждение /clear
def clear_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить все", callback_data="clear_confirm"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="clear_cancel"),
        ]
    ])


# Список забаненых: страница со списком + навигация
def banlist_keyboard(users: list[tuple], page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows = []

    # Кнопки забаненых пользователей
    for user_id, full_name in users:
        label = full_name if full_name else f"ID: {user_id}"
        rows.append([
            InlineKeyboardButton(text=label, callback_data=f"banlist_user:{user_id}")
        ])

    # Навигация
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"banlist_page:{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"banlist_page:{page + 1}"))
    if nav:
        rows.append(nav)

    # Закрыть
    rows.append([
        InlineKeyboardButton(text="❌ Закрыть", callback_data="banlist_close")
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


# Подтверждение разбана конкретного юзера
def unban_confirm_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, разблокировать", callback_data=f"unban_confirm:{user_id}"),
            InlineKeyboardButton(text="❌ Назад", callback_data="banlist_page:0"),
        ]
    ])



# Меню для админов в группе (ReplyKeyboard)
def admin_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🗑️ Очистить предложку"),
            ],
            [
                KeyboardButton(text="📋 Банлист"),
                KeyboardButton(text="ℹ️ Помощь"),
            ]
        ],
        resize_keyboard=True
    )
