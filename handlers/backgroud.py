import asyncio
import time
import os
import json
import aiohttp
import random
import logging
from dotenv import load_dotenv
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram import Bot, Router, F

active_session = {}
load_dotenv()
voip_token = os.getenv("VOIP_TOKEN")

SESSIONS_FILE = "sessions.json"

def save_sessions():
    """Зберігає active_session у sessions.json перед вимкненням або періодично."""
    try:
        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(active_session, f, indent=4, ensure_ascii=False)
        logging.info("💾 Сесії збережено в sessions.json")
    except Exception as e:
        logging.error(f"❌ Помилка збереження sessions.json: {e}")

def load_sessions():
    """Завантажує active_session із sessions.json при старті бота."""
    global active_session
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                active_session.clear()
                active_session.update(loaded)
            logging.info(f"📂 Завантажено сесії для {len(active_session)} операторів із sessions.json")
        except Exception as e:
            logging.error(f"❌ Помилка завантаження sessions.json: {e}")

def get_superadmin_ids() -> list[str]:
    """Повертає список Telegram ID користувачів із роллю 'superadmin' з users.json."""
    try:
        with open("users.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        return [
            user_id for user_id, data in config.get("operators", {}).items()
            if data.get("role") == "superadmin"
        ]
    except Exception as e:
        logging.error(f"❌ Помилка отримання superadmin ID: {e}")
        return []

USE_GATHER = True
MEMES_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "memes"
)

router = Router()

async def send_meme(bot: Bot, user_id: str, caption_text: str, folder_name: str = None, reply_markup=None, file_name: str = None):
    target_dir = os.path.join(MEMES_DIR, folder_name) if folder_name else MEMES_DIR
    if os.path.exists(target_dir):
        target_file = None
        if file_name and os.path.exists(os.path.join(target_dir, file_name)):
            target_file = file_name
        else:
            files = [
                f for f in os.listdir(target_dir)
                if f.lower().endswith((".jpg", ".png", ".jpeg", ".gif", ".mp4", ".webp", ".tgs", ".webm"))
            ]
            if files:
                target_file = random.choice(files)

        if target_file:
            file_path = os.path.join(target_dir, target_file)
            media_file = FSInputFile(file_path)

            if target_file.lower().endswith(('.gif', '.mp4')):
                return await bot.send_animation(chat_id=user_id, animation=media_file, caption=caption_text, reply_markup=reply_markup)
            elif target_file.lower().endswith(('.tgs', '.webm')):
                await bot.send_sticker(chat_id=user_id, sticker=media_file)
                if caption_text or reply_markup:
                    text_to_send = caption_text if caption_text else "👆"
                    return await bot.send_message(chat_id=user_id, text=text_to_send, reply_markup=reply_markup)
                return None
            else:
                return await bot.send_photo(chat_id=user_id, photo=media_file, caption=caption_text, reply_markup=reply_markup)
            
    if reply_markup:
        return await bot.send_message(user_id, caption_text, reply_markup=reply_markup)
    else:
        return await bot.send_message(user_id, caption_text)

headers = {
    "Authorization": f"Bearer {voip_token}",
    "Content-Type": "application/json"
}

def get_folder_for_status(status: str) -> str:
    status_lower = status.lower()
    if "навчання" in status_lower: return "Навчання"
    if "обід" in status_lower: return "Обід"
    if "перекур" in status_lower: return "Перекур"
    if "технічна" in status_lower: return "Технічна"
    if "фіксація" in status_lower: return "Фіксація"
    if "login" in status_lower: return "Login"
    if "logout" in status_lower: return "Logout"
    if "not_ready" in status_lower: return "NotReady"
    if "wc" in status_lower: return "WC"
    return ""

# Підписи, які ви можете редагувати самостійно:
LOGOUT_CAPTION = "LOGOUT"  # Підпис для картинки логауту (без 'Увага! Твій статус зараз...')
HELP_LOGOUT_CAPTION = ""  # Підпис для картинки з Special на кнопку 'боже поможи'
LUNCH_CAPTION = "Обід скінчився"  # Підпис для картинки про закінчення обіду

def get_snooze_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Нагадати через 10 хв", callback_data="snooze_10"),
                InlineKeyboardButton(text="Нагадати через 20 хв", callback_data="snooze_20")
            ]
        ]
    )

def get_logout_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Боже поможи", callback_data="help_logout")
            ]
        ]
    )

async def remove_old_buttons(bot: Bot, user_id: str):
    """Видаляє інлайн-кнопки зі старого повідомлення оператора, щоб вони більше не працювали."""
    user_session = active_session.get(user_id, {})
    old_msg_id = user_session.get("last_button_msg_id")
    if old_msg_id:
        try:
            await bot.edit_message_reply_markup(chat_id=user_id, message_id=old_msg_id, reply_markup=None)
        except Exception:
            pass
        user_session["last_button_msg_id"] = None

@router.callback_query(F.data.startswith("snooze_"))
async def process_snooze(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    if user_id not in active_session:
        active_session[user_id] = {}
    user_session = active_session[user_id]
    op_name = user_session.get("login") or (f"@{callback.from_user.username}" if callback.from_user.username else callback.from_user.first_name) or user_id

    # Перевірка: якщо натиснули на стару кнопку з попереднього повідомлення
    last_btn_id = user_session.get("last_button_msg_id")
    if last_btn_id and callback.message.message_id != last_btn_id:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await callback.answer("⚠️ Ця кнопка вже застаріла!", show_alert=True)
        return

    minutes = int(callback.data.split("_")[1])
    user_session["snooze_until"] = time.time() + (minutes * 60)
    user_session["nag_count"] = 0
    user_session["last_button_msg_id"] = None
    
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer(f"⏳ Окей, нагадаю через {minutes} хвилин!", show_alert=True)
    await callback.message.reply(f"Окей, мовчу {minutes} хвилин 🤫")
    logging.info(f"⏳ Оператор {op_name} натиснув паузу на {minutes} хв.")

@router.callback_query(F.data == "help_logout")
async def process_help_logout(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    if user_id not in active_session:
        active_session[user_id] = {}
    user_session = active_session[user_id]
    op_name = user_session.get("login") or (f"@{callback.from_user.username}" if callback.from_user.username else callback.from_user.first_name) or user_id

    # Перевірка: якщо кнопка застаріла
    last_btn_id = user_session.get("last_button_msg_id")
    if last_btn_id and callback.message.message_id != last_btn_id:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await callback.answer("⚠️ Ця кнопка вже застаріла!", show_alert=True)
        return

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    user_session["last_button_msg_id"] = None

    # Відправляємо саме no_help.jpg з папки Special
    await send_meme(callback.bot, user_id, caption_text=HELP_LOGOUT_CAPTION, folder_name="Special", file_name="no_help.jpg")
    await callback.answer()
    logging.info(f"🆘 Оператор {op_name} натиснув 'Боже поможи' -> надіслано no_help.jpg.")

async def check_single_operor(session: aiohttp.ClientSession, user_id: str, operator_data: dict, limits: dict,
                              bot: Bot, is_first_check: bool = False):
    if user_id not in active_session:
        active_session[user_id] = {}
    user_session = active_session[user_id]

    voip_id = operator_data.get("voip_id")
    op_name = operator_data.get("login", user_id)
    user_session["login"] = op_name

    if not voip_id:
        return
        
    snooze_until = user_session.get("snooze_until", 0)
    if time.time() < snooze_until:
        return 
        
    url = f"https://astra-voip.astra.in.ua/api/v2/user-statistics/detailed?userIds={voip_id}&limit=5"
    try:
        async with session.get(url, headers=headers, ssl=False) as response:
            if response.status == 200:
                history = await response.json()
                if history.get("data"):
                    latest_record = max(history["data"], key=lambda x: x.get("startedAt", 0))
                    latest_status = latest_record.get("actionDescription")
                    started_at_ms = latest_record.get("startedAt")
                    max_seconds = limits.get(latest_status)
                    logging.info(
                        f"🔍 {op_name}: status={latest_status}, "
                        f"startedAt={started_at_ms}"
                    )

                    # Фіксація зміни статусу оператора в логах
                    last_status = user_session.get("last_status")
                    if last_status is not None and last_status != latest_status:
                        logging.info(f"🔄 Оператор {op_name} змінив статус: [{last_status}] ➔ [{latest_status}]")
                    elif last_status is None:
                        logging.info(f"ℹ️ Оператор {op_name} початковий статус: [{latest_status}]")
                    user_session["last_status"] = latest_status

                    if max_seconds:
                        current_time = time.time()
                        time_spent = current_time - (started_at_ms / 1000)

                        if time_spent > max_seconds:
                            status_lower = latest_status.lower()

                            # 🤫 ТИХИЙ СТАРТ (тільки для LOGOUT): після рестарту бота не повторюємо логаут,
                            # який оператор отримав (або міг отримати) раніше. Усі інші статуси (LOGIN, NOT_READY,
                            # перерви, обід) після рестарту обробляються як зазвичай, за лімітами з users.json.
                            if is_first_check and "logout" in status_lower:
                                user_session["last_warned_at"] = started_at_ms
                                user_session["last_nag_time"] = current_time
                                logging.info(f"🤫 [Тихий старт] Оператор {op_name}: старий LOGOUT, пропускаємо.")
                                active_session[user_id] = user_session
                                return

                            nag_count = user_session.get("nag_count", 0)
                            over_seconds = int(time_spent - max_seconds)
                            
                            # 1. ПЕРШИЙ УДАР БАТОГОМ (1 раз випадковий мем)
                            if user_session.get("last_warned_at") != started_at_ms:
                                await remove_old_buttons(bot, user_id)
                                sent_msg = None
                                try:
                                    folder = get_folder_for_status(latest_status)
                                    status_lower = latest_status.lower()
                                    is_break = any(w in status_lower for w in ["навчання", "перерва", "технічна", "фіксація", "перекур", "wc"])

                                    if "logout" in status_lower:
                                        # Лиш одна картинка ОДИН РАЗ і кнопка "боже помоджи"
                                        sent_msg = await send_meme(bot, user_id, LOGOUT_CAPTION, folder_name=folder, reply_markup=get_logout_keyboard())
                                        logging.info(f"📨 Оператору {op_name} надіслано логаут (мем із '{folder}', підпис: '{LOGOUT_CAPTION}')")
                                    elif "обід" in status_lower:
                                        # Лиш 1 раз після 30 хв: мем із папки 'Обід', підпис 'Обід скінчився', без кнопок
                                        sent_msg = await send_meme(bot, user_id, LUNCH_CAPTION, folder_name=folder)
                                        logging.info(f"📨 Оператору {op_name} надіслано сповіщення про обід (мем із '{folder}', підпис: '{LUNCH_CAPTION}')")
                                    else:
                                        # Для всіх інших статусів (перерви, login, bare NOT_READY) на 1-му попередженні кнопок немає
                                        text = f"⚠️ Увага! Твій статус зараз {latest_status}!"
                                        sent_msg = await send_meme(bot, user_id, text, folder_name=folder)
                                        logging.info(f"📨 Оператору {op_name} надіслано перше попередження (мем із '{folder}', без кнопок) | Статус: {latest_status} (перевищено на {over_seconds}с)")
                                except Exception as e:
                                    logging.error(f"❌ Помилка надсилання {op_name}: {e}")

                                if sent_msg and hasattr(sent_msg, "reply_markup") and sent_msg.reply_markup:
                                    user_session["last_button_msg_id"] = sent_msg.message_id
                                else:
                                    user_session["last_button_msg_id"] = None

                                user_session["last_warned_at"] = started_at_ms
                                user_session["last_nag_time"] = time.time()
                                user_session["nag_count"] = 1
                                active_session[user_id] = user_session

                            # 2. РЕЖИМ "ДЯТЕЛ" (повторні нагадування)
                            else:
                                # Статуси Logout та Обід повідомляються РІВНО 1 РАЗ — жодних повторів!
                                if "logout" in latest_status.lower() or "обід" in latest_status.lower():
                                    return

                                last_nag = user_session.get("last_nag_time", 0)
                                is_break = any(w in latest_status.lower() for w in ["навчання", "перерва", "технічна", "фіксація", "перекур", "wc"])

                                # СТАТУСИ-ПЕРЕРВИ (Навчання, Технічна, Фіксація, Перекур, WC):
                                # 1-й раз: на 7-й хв (420с ліміту). 
                                # 2-й раз: через 8 хв (480с) після 1-го попередження (в сумі 7 + 8 = 15 хв).
                                # Після 2-го попередження — ВСЕ (більше не пишемо)! Кнопок немає.
                                if is_break:
                                    if nag_count >= 2:
                                        return  # Більше не спамимо взагалі!

                                    # Чекаємо рівно 8 хвилин (480 секунд) від першого попередження
                                    if time.time() - last_nag >= 480:
                                        sent_msg = None
                                        try:
                                            msg_text = f"👉👈 твій {latest_status} затягнувся."
                                            await remove_old_buttons(bot, user_id)
                                            sent_msg = await bot.send_message(user_id, msg_text)
                                            logging.info(f"🔨 [Дятел #2 (Останнє через 8 хв)] Оператору {op_name} надіслано: '{msg_text}' | Статус: {latest_status} (перевищено на {over_seconds}с)")
                                        except Exception as e:
                                            logging.error(f"❌ Помилка повторного нагадування для {op_name}: {e}")

                                        user_session["last_button_msg_id"] = None
                                        user_session["last_nag_time"] = time.time()
                                        user_session["nag_count"] = 2
                                        active_session[user_id] = user_session
                                    return

                                # СТАТУСИ LOGIN ТА ГОЛИЙ NOT_READY:
                                # Повідомляються 5 разів (кожні 80с).
                                # На 5-й (останній) раз додаються кнопки відкладення на 10 та 20 хвилин!
                                if time.time() - last_nag >= 80:
                                    if nag_count >= 5:
                                        # Якщо вже було 5 нагадувань і минуло ще 80с без реакції — авто-пауза на 15 хв
                                        await remove_old_buttons(bot, user_id)
                                        user_session["snooze_until"] = time.time() + 900
                                        user_session["nag_count"] = 0
                                        try:
                                            await bot.send_message(user_id, "🤖 Ти не реагуєш, тому я роблю паузу на 15 хвилин, щоб не спамити безкінечно.")
                                            logging.info(f"🤖 Оператор {op_name} проігнорував 5 нагадувань {latest_status}. Увімкнено авто-паузу на 15 хв.")
                                        except Exception as e:
                                            logging.error(f"❌ Помилка авто-паузи {op_name}: {e}")
                                    elif nag_count == 4:
                                        # 5-те нагадування (ОСТАННЄ) — додаємо кнопки снузу на 10 та 20 хв
                                        sent_msg = None
                                        try:
                                            await remove_old_buttons(bot, user_id)
                                            if "login" in latest_status.lower():
                                                msg_text = "⚠️ Останнє попередження! Не забудь змінити статус на READY. Можеш відкласти сповіщення:"
                                            else:
                                                msg_text = "🤬 Ану стань в нормальний статус! Останнє попередження, можеш відкласти:"
                                            sent_msg = await bot.send_message(user_id, msg_text, reply_markup=get_snooze_keyboard())
                                            logging.info(f"🔨 [Дятел #5 (Останнє з кнопками 10/20 хв)] Оператору {op_name} надіслано: '{msg_text}' | Статус: {latest_status} (перевищено на {over_seconds}с)")
                                        except Exception as e:
                                            logging.error(f"❌ Помилка надсилання 5-го нагадування для {op_name}: {e}")

                                        if sent_msg and hasattr(sent_msg, "message_id"):
                                            user_session["last_button_msg_id"] = sent_msg.message_id

                                        user_session["last_nag_time"] = time.time()
                                        user_session["nag_count"] = 5
                                    else:
                                        # 2-ге, 3-тє, 4-те нагадування — БЕЗ кнопок
                                        sent_msg = None
                                        try:
                                            await remove_old_buttons(bot, user_id)
                                            if "login" in latest_status.lower():
                                                msg_text = "Не забудь змінити статус на READY."
                                            else:
                                                msg_text = "🤬 Ану стань в нормальний статус!"
                                            sent_msg = await bot.send_message(user_id, msg_text)
                                            logging.info(f"🔨 [Дятел #{nag_count + 1}] Оператору {op_name} надіслано: '{msg_text}' | Статус: {latest_status} (перевищено на {over_seconds}с)")
                                        except Exception as e:
                                            logging.error(f"❌ Помилка дятла для {op_name}: {e}")

                                        user_session["last_button_msg_id"] = None
                                        user_session["last_nag_time"] = time.time()
                                        user_session["nag_count"] = nag_count + 1

                                    active_session[user_id] = user_session

            await asyncio.sleep(1)
    except aiohttp.ClientError as e:
        logging.error(f"🌐 Помилка мережі/DNS для {user_id}: {e}")
    except Exception as e:
        logging.error(f"💥 Несподівана помилка у перевірці {user_id}: {e}")

async def voip_check_statuses(bot: Bot):
    is_first_check = True
    while True:
        try:
            with open("users.json", "r", encoding="utf-8") as file:
                config = json.load(file)
        except FileNotFoundError:
            await asyncio.sleep(30)
            continue

        operators = config.get("operators", {})
        limits = config.get("status_limits", {})

        async with aiohttp.ClientSession() as session:
            if USE_GATHER:
                tasks = [
                    check_single_operor(session, user_id, operator_data, limits, bot, is_first_check=is_first_check)
                    for user_id, operator_data in operators.items()
                ]
                await asyncio.gather(*tasks)
            else:
                for user_id, operator_data in operators.items():
                    await check_single_operor(session, user_id, operator_data, limits, bot, is_first_check=is_first_check)

        # Якщо це було перше коло (тихий старт) — вимикаємо тихий режим
        if is_first_check:
            is_first_check = False
            logging.info("🚀 [Тихий старт] Перше коло перевірки завершено, активовано активний моніторинг.")

        # Періодично оновлюємо sessions.json для збереження прогресу
        save_sessions()

        await asyncio.sleep(30)
