import asyncio
import logging

logging.basicConfig(level=logging.INFO)

from create_bot import dp, bot
from handlers import main_handler, admin_handler

# Register routers
dp.include_routers(main_handler.router, admin_handler.router)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())