import json
from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove
from aiogram import F
from aiogram.fsm.state import StatesGroup, State

router = Router()
class UserAuth(StatesGroup):
    waiting_for_login = State()

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    await message.answer(
        f"👋 Привіт! Твій Telegram ID: `{user_id}`\n\n"
    )
    await message.answer("А поки адміністратор перевіряє, надішли сюди свій логін:",
        reply_markup=ReplyKeyboardRemove())
    await state.set_state(UserAuth.waiting_for_login)

@router.message(UserAuth.waiting_for_login)
async def cmd_login(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    user_login = message.text.strip()

    with open("users.json", "r", encoding="utf-8") as file:
        config = json.load(file)

        operators = config.get("operators", {})
        found_key = None
        operator_data = None

    for key, value in operators.items():
        if value.get("login") == user_login:
           found_key = key
           operator_data = value
           break

    if operator_data:
        operators[user_id] = operator_data

        if found_key and found_key != user_id:
            del operators[found_key]
            #operators[user_id]["shift_start"] = time.time()

        with open("users.json", "w", encoding="utf-8") as file:
            json.dump(config, file, indent=4, ensure_ascii=False)

        await message.answer("✅ Тебе успішно авторизовано!")

    else:
        await message.answer("❌ Такого логіна немає в базі.")

    await state.clear()

@router.message(F.text.lower().contains("дякую"))
async def reply_to_thanks(message: types.Message):
    await message.reply("Твоє «дякую» в статуси не запишеш!")