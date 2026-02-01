from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


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
        # [
        #     InlineKeyboardButton(
        #         text="👤 Профиль",
        #         callback_data="profile",
        #         url=f"tg://user?id={user_id}"
        #     )
        # ]
    ])