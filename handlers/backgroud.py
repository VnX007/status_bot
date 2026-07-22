import asyncio
import time
import os
import json
import aiohttp
import logging
from dotenv import load_dotenv
from aiogram import Bot

active_session = {}
load_dotenv()
voip_token = os.getenv("VOIP_TOKEN")

headers = {
    "Authorization": f"Bearer {voip_token}",
    "Content-Type": "application/json"
}

async def voip_check_statuses(bot: Bot):
    while True:
        try:
            with open("users.json", "r", encoding="utf-8") as file:
                config = json.load(file)
        except FileNotFoundError:
            await asyncio.sleep(60)
            continue

        operators = config.get("operators", {})
        limits = config.get("status_limits", {})


        async with aiohttp.ClientSession() as session:
            for user_id, operator_data in operators.items():
                voip_id = operator_data.get("voip_id")

                if not voip_id:
                    continue
                url = f"https://astra-voip.astra.in.ua/api/v2/user-statistics/detailed?userIds={voip_id}&limit=5"
                async with session.get(url , headers=headers) as response:
                    if response.status == 200:
                        history = await response.json()
                        if  history.get("data"):
                            latest_record = history["data"][0]
                            latest_status = latest_record.get("actionDescription") # Напр: "NOT_READY [Перекур]"
                            started_at_ms = latest_record.get("startedAt")
                            max_seconds = limits.get(latest_status)

                            if max_seconds:
                                current_time = time.time()
                                time_spent = current_time - (started_at_ms / 1000)

                                if time_spent > max_seconds:
                                    user_session = active_session.get(user_id, {})

                                    # 1. ПЕРШИЙ УДАР БАТОГОМ
                                    if user_session.get("last_warned_at") != started_at_ms:
                                        try:
                                            await bot.send_message(user_id,
                                                                   f"⚠️ Увага! Твій твій статус зараз {latest_status}!")
                                        except Exception as e:
                                            print(f"❌ Фейл з {user_id}: {e}")

                                        # Запам'ятовуємо цей статус і час, коли сварилися
                                        user_session["last_warned_at"] = started_at_ms
                                        user_session["last_nag_time"] = time.time()
                                        active_session[user_id] = user_session

                                    # 2. РЕЖИМ "ДЯТЕЛ" (тільки для голого NOT_READY)
                                    else:
                                        if latest_status == "NOT_READY":
                                            last_nag = user_session.get("last_nag_time", 0)

                                            # Якщо з минулого мата пройшло більше 60 секунд — лупимо ще раз!
                                            if time.time() - last_nag > 60:
                                                try:
                                                    await bot.send_message(user_id,
                                                                           "🤬 Ану стань в нормальний статус!")
                                                    logging.info(f"Удар батогом! Юзеру {user_id} відправлено: Ану стань в нормальний статус!")
                                                except Exception as e:
                                                    print(f"❌ Фейл дятла: {e}")

                                                user_session["last_nag_time"] = time.time()

                                        elif latest_status == "LOGIN":
                                            if time.time() - last_nag > 60:
                                                try:
                                                    await bot.send_message(user_id,
                                                                           "Зміни будь ласка якийсь статус")
                                                    logging.info(
                                                        f"Удар батогом! Юзеру {user_id} відправлено: Зміни будь ласка якийсь статус")
                                                except Exception as e:
                                                    print(f"❌ Фейл дятла 2: {e}")

                                                user_session["last_nag_time"] = time.time()

                                        elif latest_status in ["NOT_READY [Перекур]", "NOT_READY [WS_]",
                                                                       "NOT_READY [Навчання]",
                                                                       "NOT_READY [Технічна перерва]",
                                                                       "NOT_READY [Фіксація заявки]"]:
                                            if time.time() - last_nag > 480:
                                                try:
                                                    await bot.send_message(user_id,
                                                                               f" 👉👈 , твій {latest_status} затягнувся.")
                                                    logging.info(
                                                        f"Удар батогом! Юзеру {user_id} відправлено: твій {latest_status} затягнувся.")
                                                except Exception as e:
                                                        print(f"❌ Фейл дятла 3: {e}")

                                                # Оновлюємо таймер, щоб не спамити щосекунди
                                                user_session["last_nag_time"] = time.time()
                                                active_session[user_id] = user_session

                await asyncio.sleep(3)

    await asyncio.sleep(60)