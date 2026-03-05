import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import BOT_TOKEN
from handlers import base_handlers
from database import db_manager

async def main():
    if not BOT_TOKEN or "YOUR_TELEGRAM_BOT_TOKEN_HERE" in BOT_TOKEN:
        print("❌ ОШИБКА: Забыли указать BOT_TOKEN в .env файле!")
        return

    # Initialize DB
    await db_manager.init_db()

    # Initialize Bot and Dispatcher
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
    dp = Dispatcher()

    # Register handlers
    dp.include_router(base_handlers.router)

    # Start polling
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    print("🚀 Бот ImDram запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
