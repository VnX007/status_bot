from aiogram import Router, types


router = Router()

@router.message()
async def catch_all(message: types.Message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "Невідомий"
    text = message.text or "[без тексту]"

    with open("answers.txt", "a", encoding="utf-8") as f:
        f.write((f"{message.date} | Юзер {message.from_user.id} ({message.from_user.first_name}): {message.text}\n"))