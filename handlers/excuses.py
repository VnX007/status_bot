import os
import time
import logging
from aiogram import Router, types
from handlers.backgroud import send_meme, active_session

router = Router()

PROFANITY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "profanity_words.txt"
)

def load_profanity_words() -> list[str]:
    """Завантажує список слів для фільтрації з окремого файлу profanity_words.txt."""
    if not os.path.exists(PROFANITY_FILE):
        return []
    try:
        with open(PROFANITY_FILE, "r", encoding="utf-8") as f:
            return [line.strip().lower() for line in f if line.strip()]
    except Exception as e:
        logging.error(f"❌ Помилка читання {PROFANITY_FILE}: {e}")
        return []

MAT_LIMIT = 3
MAT_WINDOW = 86400  # 24 години в секундах

@router.message()
async def catch_all(message: types.Message):
    user_id = str(message.from_user.id)
    text = message.text or "[без тексту]"
    text_lower = text.lower()
    user_name = (f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name) or user_id

    with open("answers.txt", "a", encoding="utf-8") as f:
        f.write((f"{message.date} | Юзер {user_id} ({message.from_user.first_name}): {text}\n"))

    profanity_words = load_profanity_words()
    if any(word in text_lower for word in profanity_words):
        now = time.time()

        # Ініціалізуємо сесію юзера якщо немає
        if user_id not in active_session:
            active_session[user_id] = {}

        # Отримуємо список часових міток матів і чистимо старші 24год
        timestamps = active_session[user_id].get("profanity_timestamps", [])
        timestamps = [t for t in timestamps if now - t < MAT_WINDOW]

        if len(timestamps) < MAT_LIMIT:
            # Ліміт не перевищений — надсилаємо мем
            timestamps.append(now)
            active_session[user_id]["profanity_timestamps"] = timestamps
            count = len(timestamps)
            logging.info(f"🤬 Оператор {user_name} (ID: {user_id}) написав нецензурне: '{text}' -> надіслано мем зі Special ({count}/{MAT_LIMIT} за 24год)")
            await send_meme(message.bot, user_id, "Без матів, будь ласка! 🤬", folder_name="Special")
        else:
            # Ліміт перевищений — ігноруємо
            active_session[user_id]["profanity_timestamps"] = timestamps
            logging.info(f"🚫 Оператор {user_name} (ID: {user_id}) перевищив ліміт матів ({MAT_LIMIT}/24год). Ігнорується.")