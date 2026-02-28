from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def post_moderation_keyboard(user_id: int, username: str = None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="🚫 Бан", callback_data=f"ban:{user_id}",style="danger"),
            InlineKeyboardButton(text="🧹 Удалить пост", callback_data="delete_post", style="primary"),
        ],
    ]
     # Кнопка профиля появляется только если у пользователя есть username
    if username:
        rows.append([
            InlineKeyboardButton(text="👤 Профиль", url=f"https://t.me/{username}", style="success"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# Подтверждение /clear
def clear_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить все", callback_data="clear_confirm", style="success"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="clear_cancel", style="danger"),
        ]
    ])


# Список забаненых: страница со списком + навигация
def banlist_keyboard(users: list[tuple], page: int, total_pages: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    # Кнопки забаненых пользователей
    for user_id, full_name in users:
        label = full_name if full_name else f"ID: {user_id}"
        builder.button(text=label, callback_data=f"banlist_user:{user_id}")
    builder.adjust(1)

    # Навигация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"banlist_page:{page - 1}", style="primary"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"banlist_page:{page + 1}", style="primary"))
    if nav_buttons:
        builder.row(*nav_buttons)
       
    builder.row(InlineKeyboardButton(text="❌ Закрыть", callback_data="banlist_close", style="danger"))

    return builder.as_markup()


# Подтверждение разбана конкретного юзера
def unban_confirm_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, разблокировать", callback_data=f"unban_confirm:{user_id}", style="success"),
            InlineKeyboardButton(text="❌ Назад", callback_data="banlist_page:0", style="danger"),
        ]
    ])

def admin_menu_keyboard() -> ReplyKeyboardMarkup:
    admin_builder = ReplyKeyboardBuilder()

    # Добавляем кнопки
    admin_builder.button(text="🗑️ Очистить предложку")
    admin_builder.button(text="📋 Банлист")
    admin_builder.button(text="ℹ️ Помощь")

    # Настраиваем расположение
    admin_builder.adjust(1, 2)  

    return admin_builder.as_markup(resize_keyboard=True)