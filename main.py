import asyncio
import logging
import sys
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web
from config import BOT_TOKEN
from handlers import base_handlers
from database import db_manager

# Web server for Render "Keep-Alive" trick
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render provides PORT environment variable
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"📡 Web server for keep-alive started on port {port}")

async def main():
    if not BOT_TOKEN or "YOUR_TELEGRAM_BOT_TOKEN_HERE" in BOT_TOKEN:
        print("❌ ОШИБКА: Забыли указать BOT_TOKEN в .env файле!")
        return

    # Initialize DB
    if not os.getenv("DATABASE_URL"):
        print("❌ ОШИБКА: DATABASE_URL не установлена!")
        return
    await db_manager.init_db()

    # Start Web Server (for Render)
    asyncio.create_task(start_web_server())

    # Initialize Bot and Dispatcher
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
    dp = Dispatcher()

    # Register handlers
    dp.include_router(base_handlers.router)

    try:
        # Start polling
        logging.basicConfig(level=logging.INFO, stream=sys.stdout)
        print("🚀 Бот ImDram запущен!")
        await dp.start_polling(bot)
    finally:
        await db_manager.close_pool()
        print("🛑 Пул соединений базы данных закрыт.")

if __name__ == "__main__":
    asyncio.run(main())
