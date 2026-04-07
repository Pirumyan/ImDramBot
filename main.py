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
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from utils.locales import get_msg

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

async def daily_reminder(bot: Bot):
    tz = ZoneInfo("Asia/Yerevan")
    while True:
        now = datetime.now(tz)
        target_time = now.replace(hour=21, minute=0, second=0, microsecond=0)
        if now > target_time:
            target_time += timedelta(days=1)
        sleep_seconds = (target_time - now).total_seconds()
        
        logging.info(f"⏰ Следующее напоминание запланировано через {sleep_seconds/3600:.2f} часов.")
        await asyncio.sleep(sleep_seconds)
        
        logging.info("Отправка ежедневных напоминаний...")
        users = await db_manager.get_users_to_remind()
        for u_id, lang in users:
            try:
                await bot.send_message(u_id, get_msg(lang, "reminder"))
                await asyncio.sleep(0.05)
            except Exception as e:
                logging.error(f"Ошибка отправки напоминания пользователю {u_id}: {e}")

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

    # Cleanup leftover temp files from previous sessions
    import shutil
    if os.path.exists("temp"):
        try:
            shutil.rmtree("temp")
        except Exception as e:
            print(f"⚠️ Warning: Could not clean temp directory: {e}")
    os.makedirs("temp", exist_ok=True)

    # Initialize Bot and Dispatcher
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
    dp = Dispatcher()

    # Register handlers
    dp.include_router(base_handlers.router)
    
    # Start reminder task
    asyncio.create_task(daily_reminder(bot))

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
