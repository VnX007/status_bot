import os
import time
import json
import random
import logging
from aiogram import Router, types
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram import F
from aiogram.fsm.state import StatesGroup, State
from handlers.backgroud import active_session, send_meme, MEMES_DIR

router = Router()

def is_superadmin(user_id: str) -> bool:
    """Перевіряє, чи має користувач роль 'superadmin' у users.json."""
    try:
        with open("users.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        return config.get("operators", {}).get(user_id, {}).get("role") == "superadmin"
    except Exception:
        return False

AVAILABLE_MEME_FOLDERS = [
    ("🚬 Перекур", "Перекур"),
    ("🚽 WC", "WC"),
    ("🥪 Обід", "Обід"),
    ("🎓 Навчання", "Навчання"),
    ("🛠 Технічна", "Технічна"),
    ("📝 Фіксація", "Фіксація"),
    ("🚪 Logout", "Logout"),
    ("🔑 Login", "Login"),
    ("⚠️ NotReady", "NotReady"),
    ("🌟 Special", "Special"),
]

def get_admin_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧪 Тестування стікерів / мемів", callback_data="adm_test_menu")],
        [InlineKeyboardButton(text="🧹 Скинути ліміт матів", callback_data="adm_mat_menu")],
        [InlineKeyboardButton(text="📊 Хто зараз у якому статусі", callback_data="adm_status_menu")],
        [InlineKeyboardButton(text="❌ Закрити меню", callback_data="adm_close")]
    ])

def get_folders_keyboard():
    buttons = []
    for i in range(0, len(AVAILABLE_MEME_FOLDERS), 2):
        row = [InlineKeyboardButton(text=AVAILABLE_MEME_FOLDERS[i][0], callback_data=f"adm_folder_{AVAILABLE_MEME_FOLDERS[i][1]}")]
        if i + 1 < len(AVAILABLE_MEME_FOLDERS):
            row.append(InlineKeyboardButton(text=AVAILABLE_MEME_FOLDERS[i + 1][0], callback_data=f"adm_folder_{AVAILABLE_MEME_FOLDERS[i + 1][1]}"))
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="🎲 Будь-яка випадкова папка", callback_data="adm_folder_RANDOM")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="adm_main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_folder_format_keyboard(folder_name: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎭 Тільки стікер (.tgs / .webm)", callback_data=f"adm_send_{folder_name}_sticker")],
        [InlineKeyboardButton(text="🎬 Тільки GIF / Відео (.gif / .mp4)", callback_data=f"adm_send_{folder_name}_anim")],
        [InlineKeyboardButton(text="🖼 Тільки Фото (.jpg / .png / .webp)", callback_data=f"adm_send_{folder_name}_photo")],
        [InlineKeyboardButton(text="🎲 Будь-який випадковий файл", callback_data=f"adm_send_{folder_name}_any")],
        [InlineKeyboardButton(text="⬅️ До списку папок", callback_data="adm_test_menu")]
    ])
class UserAuth(StatesGroup):
    waiting_for_login = State()

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    admin_hint = "👑 Ти маєш статус <b>суперадміна</b>! Тобі доступна адмін-панель: /admin\n\n" if is_superadmin(str(user_id)) else ""
    await message.answer(
        f"👋 Привіт! Твій Telegram ID: `{user_id}`\n\n"
        f"{admin_hint}",
        parse_mode="HTML"
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
        logging.info(f"🔑 Оператор {user_login} успішно прив'язав Telegram ID: {user_id}")

    else:
        await message.answer("❌ Такого логіна немає в базі.")
        logging.warning(f"⚠️ Невідома спроба входу з логіном '{user_login}' від ID: {user_id}")

    await state.clear()

@router.message(F.text.lower().contains("дякую"))
async def reply_to_thanks(message: types.Message):
    await message.reply("Твоє «дякую» в статуси не запишеш!")

@router.message(Command("reset_mat"))
async def cmd_reset_mat(message: types.Message, command: CommandObject):
    user_id = str(message.from_user.id)
    with open("users.json", "r", encoding="utf-8") as file:
        config = json.load(file)

    operators = config.get("operators", {})
    user_data = operators.get(user_id, {})
    role = user_data.get("role", "operator")

    if role not in ["superadmin", "admin"]:
        await message.reply("⛔ У тебе немає прав для використання цієї команди.")
        return

    target = (command.args or "").strip()
    if not target:
        await message.reply(
            "ℹ️ Вкажи логін або Telegram ID оператора:\n"
            "Наприклад: <code>/reset_mat vnanovska</code> або <code>/reset_mat 831989652</code>",
            parse_mode="HTML"
        )
        return

    target_id = None
    target_login = target

    # Пошук оператора за ID або логіном
    if target in operators:
        target_id = target
        target_login = operators[target].get("login", target)
    else:
        for op_id, op_info in operators.items():
            if op_info.get("login", "").lower() == target.lower():
                target_id = op_id
                target_login = op_info.get("login")
                break

    if not target_id and target in active_session:
        target_id = target

    if not target_id:
        await message.reply(f"❌ Оператора '{target}' не знайдено в базі.")
        return

    if target_id not in active_session:
        active_session[target_id] = {}

    active_session[target_id]["profanity_timestamps"] = []
    await message.reply(f"✅ Ліміт матів для <b>{target_login}</b> скинуто! (доступно знову 3/3)", parse_mode="HTML")
    admin_name = user_data.get("login") or message.from_user.username or user_id
    logging.info(f"🛠 Адмін {admin_name} скинув ліміт матів для оператора {target_login} (ID: {target_id})")

# ==========================================
# 👑 АДМІН-ПАНЕЛЬ СУПЕРАДМІНА (/admin)
# ==========================================

@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    user_id = str(message.from_user.id)
    if not is_superadmin(user_id):
        await message.reply("⛔ У тебе немає прав доступу до панелі адміністратора.")
        return

    text = "Оберіть потрібну дію:"
    await message.answer(text, reply_markup=get_admin_menu_keyboard(), parse_mode="HTML")

@router.callback_query(F.data == "adm_main_menu")
async def adm_main_menu_handler(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    if not is_superadmin(user_id):
        await callback.answer("⛔ Немає доступу", show_alert=True)
        return
    text = "Оберіть потрібну дію:"
    try:
        await callback.message.edit_text(text, reply_markup=get_admin_menu_keyboard(), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()

@router.callback_query(F.data == "adm_close")
async def adm_close_handler(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer("Панель закрито.")

# --- 🧪 1. ТЕСТУВАННЯ СТІКЕРІВ ТА МЕМІВ ---

@router.callback_query(F.data == "adm_test_menu")
async def adm_test_menu_handler(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    if not is_superadmin(user_id):
        await callback.answer("⛔ Немає доступу", show_alert=True)
        return
    text = "🧪 <b>Тестування стікерів та мемів:</b>\nОберіть папку, з якої надіслати файл:"
    try:
        await callback.message.edit_text(text, reply_markup=get_folders_keyboard(), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()

@router.callback_query(F.data.startswith("adm_folder_"))
async def adm_folder_handler(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    if not is_superadmin(user_id):
        await callback.answer("⛔ Немає доступу", show_alert=True)
        return

    folder_name = callback.data.replace("adm_folder_", "")
    if folder_name == "RANDOM":
        folder_name = random.choice([f[1] for f in AVAILABLE_MEME_FOLDERS])

    folder_path = os.path.join(MEMES_DIR, folder_name)
    if not os.path.exists(folder_path):
        await callback.answer(f"❌ Папка '{folder_name}' не знайдена на диску!", show_alert=True)
        return

    all_files = os.listdir(folder_path)
    stickers_cnt = len([f for f in all_files if f.lower().endswith((".tgs", ".webm"))])
    anim_cnt = len([f for f in all_files if f.lower().endswith((".gif", ".mp4"))])
    photo_cnt = len([f for f in all_files if f.lower().endswith((".jpg", ".png", ".jpeg", ".webp"))])
    total_cnt = len(all_files)

    text = (
        f"📂 <b>Папка:</b> <code>{folder_name}</code>\n"
        f"Всього файлів: <b>{total_cnt}</b>\n"
        f"• 🎭 Стікерів (.tgs, .webm): <b>{stickers_cnt}</b>\n"
        f"• 🎬 Анімацій (.gif, .mp4): <b>{anim_cnt}</b>\n"
        f"• 🖼 Фотографій: <b>{photo_cnt}</b>\n\n"
        f"Оберіть, який саме формат протестувати:"
    )

    try:
        await callback.message.edit_text(text, reply_markup=get_folder_format_keyboard(folder_name), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()

@router.callback_query(F.data.startswith("adm_send_"))
async def adm_send_handler(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    if not is_superadmin(user_id):
        await callback.answer("⛔ Немає доступу", show_alert=True)
        return

    parts = callback.data.split("_")
    fmt = parts[-1]
    folder_name = "_".join(parts[2:-1])

    if folder_name == "RANDOM":
        folder_name = random.choice([f[1] for f in AVAILABLE_MEME_FOLDERS])

    folder_path = os.path.join(MEMES_DIR, folder_name)
    if not os.path.exists(folder_path):
        await callback.answer(f"❌ Папка '{folder_name}' не знайдена!", show_alert=True)
        return

    exts = {
        "sticker": (".tgs", ".webm"),
        "anim": (".gif", ".mp4"),
        "photo": (".jpg", ".png", ".jpeg", ".webp"),
        "any": (".jpg", ".png", ".jpeg", ".gif", ".mp4", ".webp", ".tgs", ".webm")
    }.get(fmt, (".jpg", ".png", ".jpeg", ".gif", ".mp4", ".webp", ".tgs", ".webm"))

    matching_files = [
        f for f in os.listdir(folder_path)
        if f.lower().endswith(exts)
    ]

    if not matching_files:
        format_names = {
            "sticker": "стікерів (.tgs / .webm)",
            "anim": "анімацій / відео (.gif / .mp4)",
            "photo": "фотографій (.jpg / .png / .webp)",
            "any": "файлів"
        }
        await callback.answer(f"⚠️ У папці '{folder_name}' немає {format_names.get(fmt, 'файлів')}!", show_alert=True)
        return

    chosen_file = random.choice(matching_files)
    file_ext = os.path.splitext(chosen_file)[1].lower()
    type_label = "🎭 Анімований стікер" if file_ext in [".tgs", ".webm"] else ("🎬 GIF / Відео" if file_ext in [".gif", ".mp4"] else "🖼 Фотографія")

    caption = (
        f"🧪 <b>Тест медіа:</b>\n"
        f"📂 Папка: <code>{folder_name}</code>\n"
        f"📄 Файл: <code>{chosen_file}</code> ({type_label})"
    )

    repeat_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Ще один такий", callback_data=f"adm_send_{folder_name}_{fmt}"),
            InlineKeyboardButton(text="📁 Інший формат", callback_data=f"adm_folder_{folder_name}")
        ],
        [
            InlineKeyboardButton(text="⬅️ До списку папок", callback_data="adm_test_menu"),
            InlineKeyboardButton(text="👑 В адмінку", callback_data="adm_main_menu")
        ]
    ])

    await callback.answer(f"Надсилаю {chosen_file}...")
    await send_meme(callback.bot, user_id, caption_text=caption, folder_name=folder_name, reply_markup=repeat_kb, file_name=chosen_file)

# --- 🧹 2. СКИДАННЯ ЛІМІТУ МАТІВ КНОПКАМИ ---

@router.callback_query(F.data == "adm_mat_menu")
async def adm_mat_menu_handler(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    if not is_superadmin(user_id):
        await callback.answer("⛔ Немає доступу", show_alert=True)
        return

    with open("users.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    operators = config.get("operators", {})
    now = time.time()

    buttons = []
    for op_id, op_info in operators.items():
        login = op_info.get("login", op_id)
        timestamps = active_session.get(op_id, {}).get("profanity_timestamps", [])
        active_mats = len([t for t in timestamps if now - t < 86400])
        status_icon = "🤬" if active_mats >= 3 else ("⚠️" if active_mats > 0 else "✅")
        buttons.append([InlineKeyboardButton(text=f"{status_icon} {login} ({active_mats}/3 матів) ➔ Скинути", callback_data=f"adm_resetmat_{op_id}")])

    buttons.append([InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="adm_main_menu")])

    text = "🧹 <b>Скидання ліміту матів:</b>\nНатисніть на оператора, щоб миттєво обнулити його лічильник:"
    try:
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()

@router.callback_query(F.data.startswith("adm_resetmat_"))
async def adm_resetmat_action(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    if not is_superadmin(user_id):
        await callback.answer("⛔ Немає доступу", show_alert=True)
        return

    target_id = callback.data.replace("adm_resetmat_", "")
    if target_id not in active_session:
        active_session[target_id] = {}
    active_session[target_id]["profanity_timestamps"] = []

    with open("users.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    login = config.get("operators", {}).get(target_id, {}).get("login", target_id)

    logging.info(f"🛠 Суперадмін скинув ліміт матів для {login} (ID: {target_id}) через кнопку в меню")
    await callback.answer(f"✅ Ліміт для {login} успішно скинуто! (0/3)", show_alert=True)
    await adm_mat_menu_handler(callback)

# --- 📊 3. ХТО В ЯКОМУ СТАТУСІ ---

@router.callback_query(F.data == "adm_status_menu")
async def adm_status_menu_handler(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    if not is_superadmin(user_id):
        await callback.answer("⛔ Немає доступу", show_alert=True)
        return

    with open("users.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    operators = config.get("operators", {})
    now = time.time()

    text_lines = ["📊 <b>Поточний стан операторів:</b>\n"]
    for op_id, op_info in operators.items():
        login = op_info.get("login", op_id)
        role = op_info.get("role", "operator")
        sess = active_session.get(op_id, {})
        status = sess.get("last_status", "Немає даних (ще не опитувався)")
        nag = sess.get("nag_count", 0)
        snooze_until = sess.get("snooze_until", 0)

        snooze_text = ""
        if now < snooze_until:
            rem_min = int((snooze_until - now) / 60) + 1
            snooze_text = f" | ⏳ Пауза ще {rem_min} хв"

        timestamps = sess.get("profanity_timestamps", [])
        mats_cnt = len([t for t in timestamps if now - t < 86400])

        text_lines.append(
            f"👤 <b>{login}</b> (роль: <code>{role}</code>)\n"
            f"   • Статус: <code>{status}</code>\n"
            f"   • Нагадувань: <b>{nag}</b>{snooze_text}\n"
            f"   • Мати: <b>{mats_cnt}/3</b> за 24 год\n"
        )

    buttons = [
        [InlineKeyboardButton(text="🔄 Оновити дані", callback_data="adm_status_menu")],
        [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="adm_main_menu")]
    ]

    try:
        await callback.message.edit_text("\n".join(text_lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()