import asyncio
import os
import json
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import google.generativeai as genai

# ==============================================================================
# НАСТРОЙКИ КЛЮЧЕЙ (Вшиты прямо в код)
# ==============================================================================
BOT_TOKEN = "8595895020:AAFL-NEnwa83eoh2vaMZUvG7zRdHWlIcoOA"
GEMINI_API_KEY = "AQ.Ab8RN6LYpE-r7eLaoVZUe4hx7djOMa_3GJqFSGRuBz0dAas4gQ"
ADMIN_ID = 8724732477

# Инициализируем бота, диспетчер и ИИ
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
genai.configure(api_key=GEMINI_API_KEY)

# ==============================================================================
# ХРАНИЛИЩЕ НАСТРОЕК (JSON) И СОСТОЯНИЯ (FSM)
# ==============================================================================
DATA_DIR = "data"
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

# Настройки по умолчанию
default_settings = {
    "is_active": False,
    "prompt": "Ты мой личный ассистент. Отклоняй любые предложения о покупке рекламы, курсов, криптовалюты или инвестиций. Будь краток, вежлив, но категоричен. Отвечай от моего лица.",
    "work_start": 0,  # 00:00 (Начало времени, когда бот отвечает)
    "work_end": 24,   # 24:00 (Конец времени)
}

def load_settings():
    # Автоматическое создание папки и файла при запуске на хостинге, если их нет
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_settings, f, ensure_ascii=False, indent=4)
        return default_settings.copy()
    
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return default_settings.copy()

def save_settings(settings_data):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings_data, f, ensure_ascii=False, indent=4)

# Загружаем настройки при старте
settings = load_settings()

# Состояния для ввода текста с клавиатуры
class SettingsState(StatesGroup):
    waiting_for_prompt = State()
    waiting_for_start_time = State()
    waiting_for_end_time = State()

# ==============================================================================
# КЛАВИАТУРЫ (КНОПКИ)
# ==============================================================================
def get_main_keyboard():
    status_text = "🟢 БОТ ВКЛЮЧЕН" if settings["is_active"] else "🔴 БОТ ВЫКЛЮЧЕН"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=status_text, callback_data="toggle_status")],
        [InlineKeyboardButton(text="📝 Изменить системный Промпт", callback_data="edit_prompt")],
        [InlineKeyboardButton(text="🕒 Настроить время работы", callback_data="edit_time")],
        [InlineKeyboardButton(text="📋 Текущие настройки", callback_data="show_settings")]
    ])
    return keyboard

# ==============================================================================
# ЛОГИКА АДМИН-ПАНЕЛИ (Взаимодействие бота с вами)
# ==============================================================================
@dp.message(CommandStart())
async def cmd_start(message: Message):
    if message.from_user.id != ADMIN_ID:
        return # Игнорируем чужих, админ-панель только для владельца
    
    await message.answer(
        "👋 Привет! Это панель управления ИИ-Автоответчиком.\n"
        "Настраивай логику работы с помощью кнопок ниже:",
        reply_markup=get_main_keyboard()
    )

@dp.callback_query(F.data == "toggle_status")
async def toggle_status(callback: CallbackQuery):
    settings["is_active"] = not settings["is_active"]
    save_settings(settings)
    await callback.message.edit_reply_markup(reply_markup=get_main_keyboard())
    await callback.answer("Статус изменен!")

@dp.callback_query(F.data == "show_settings")
async def show_settings(callback: CallbackQuery):
    text = (
        f"📋 **Текущие настройки:**\n\n"
        f"**Статус:** {'Включен' if settings['is_active'] else 'Выключен'}\n"
        f"**Время работы:** с {settings['work_start']}:00 до {settings['work_end']}:00\n\n"
        f"**Промпт ИИ:**\n`{settings['prompt']}`"
    )
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "edit_prompt")
async def edit_prompt(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Отправь мне новый системный промпт (инструкцию) для ИИ:")
    await state.set_state(SettingsState.waiting_for_prompt)
    await callback.answer()

@dp.message(StateFilter(SettingsState.waiting_for_prompt))
async def save_prompt(message: Message, state: FSMContext):
    settings["prompt"] = message.text
    save_settings(settings)
    await state.clear()
    await message.answer("✅ Промпт успешно обновлен!", reply_markup=get_main_keyboard())

@dp.callback_query(F.data == "edit_time")
async def edit_time_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введи час НАЧАЛА работы автоответчика (число от 0 до 23):")
    await state.set_state(SettingsState.waiting_for_start_time)
    await callback.answer()

@dp.message(StateFilter(SettingsState.waiting_for_start_time))
async def save_start_time(message: Message, state: FSMContext):
    if message.text.isdigit() and 0 <= int(message.text) <= 23:
        settings["work_start"] = int(message.text)
        save_settings(settings)
        await message.answer("Теперь введи час ОКОНЧАНИЯ работы (число от 0 до 24):")
        await state.set_state(SettingsState.waiting_for_end_time)
    else:
        await message.answer("Пожалуйста, введи только число от 0 до 23.")

@dp.message(StateFilter(SettingsState.waiting_for_end_time))
async def save_end_time(message: Message, state: FSMContext):
    if message.text.isdigit() and 0 <= int(message.text) <= 24:
        settings["work_end"] = int(message.text)
        save_settings(settings)
        await state.clear()
        await message.answer("✅ Время работы успешно обновлено!", reply_markup=get_main_keyboard())
    else:
        await message.answer("Пожалуйста, введи только число от 0 до 24.")

# ==============================================================================
# ЛОГИКА АВТООТВЕТЧИКА BUSINESS (Анализ сообщений через ИИ)
# ==============================================================================
@dp.business_message()
async def handle_business_messages(message: Message):
    # 1. Проверяем, включен ли бот
    if not settings["is_active"]:
        return

    # 2. Проверяем время работы
    current_hour = datetime.now().hour
    start_h, end_h = settings["work_start"], settings["work_end"]
    
    # Логика: если сейчас не рабочие часы - игнорируем
    if not (start_h <= current_hour < end_h):
        return

    text = message.text
    if not text:
        return

    # 3. Отправляем сообщение пользователя в ИИ (Gemini) для анализа
    try:
        # Настраиваем модель с вашим кастомным промптом
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=settings["prompt"]
        )
        
        # Просим ИИ проанализировать и ответить
        ai_prompt = f"Сообщение от собеседника: '{text}'. Сгенерируй ответ согласно твоим инструкциям. Если по инструкциям отвечать не нужно, ответь просто словом 'IGNORE'."
        
        response = model.generate_content(ai_prompt)
        ai_reply = response.text.strip()

        # Если ИИ решил, что на это сообщение отвечать не нужно (например, это не спам)
        if "IGNORE" in ai_reply.upper():
            print(f"ИИ проигнорировал сообщение: {text}")
            return
            
        # 4. Отправляем ответ ИИ от вашего лица
        print(f"Сгенерирован ответ: {ai_reply}")
        await message.answer(ai_reply)

    except Exception as e:
        print(f"Ошибка при обращении к ИИ: {e}")

# Запуск
async def main():
    print("ИИ-Бот запущен. Напишите /start боту для открытия админ-панели.")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
