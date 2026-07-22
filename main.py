import asyncio
import os
import logging
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv
from handlers import start
from handlers import backgroud


load_dotenv()

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()
dp.include_router(start.router)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO, filemode="a", filename="galera_logs.txt"
)


async def main():
    asyncio.create_task(backgroud.voip_check_statuses(bot))
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())