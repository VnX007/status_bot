import asyncio
import os
import logging
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv
from handlers import start
from handlers import backgroud
from handlers import excuses


load_dotenv()

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()
dp.include_router(start.router)
dp.include_router(backgroud.router)
dp.include_router(excuses.router)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    filemode="a",
    filename="galera_logs.txt",
    encoding="utf-8"
)

async def on_startup(bot: Bot):
    backgroud.load_sessions()
    superadmins = backgroud.get_superadmin_ids()
    for admin_id in superadmins:
        try:
            await bot.send_message(admin_id, "✅ Бот в строю.")
            logging.info(f"📢 Повідомлення про запуск надіслано superadmin ID: {admin_id}")
        except Exception as e:
            logging.error(f"❌ Не вдалося надіслати повідомлення про запуск superadmin ID {admin_id}: {e}")

async def on_shutdown(bot: Bot):
    superadmins = backgroud.get_superadmin_ids()
    for admin_id in superadmins:
        try:
            await bot.send_message(admin_id, "⚠️ Сервер перезавантажується / бот зупиняється.")
            logging.info(f"📢 Повідомлення про зупинку надіслано superadmin ID: {admin_id}")
        except Exception as e:
            logging.error(f"❌ Не вдалося надіслати повідомлення про зупинку superadmin ID {admin_id}: {e}")
    backgroud.save_sessions()

dp.startup.register(on_startup)
dp.shutdown.register(on_shutdown)

async def main():
    asyncio.create_task(backgroud.voip_check_statuses(bot))
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())