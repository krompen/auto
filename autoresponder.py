import os
import json
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from google import genai
from google.genai import types as genai_types
import asyncio

# --- ВАШИ КЛЮЧИ ---
BOT_TOKEN = "8595895020:AAFL-NEnwa83eoh2vaMZUvG7zRdHWlIcoOA" # Убедитесь, что токен верный!
ADMIN_ID = 8724732477
GEMINI_API_KEY = "AQ.Ab8RN6LYpE-r7eLaoVZUe4hx7djOMa_3GJqFSGRuBz0dAas4gQ" 

# --- НАСТРОЙКИ ИИ ---
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# Отключаем цензуру Google
safety_settings = [
    genai_types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
    genai_types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
    genai_types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
    genai_types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
]

# --- ИНИЦИАЛИЗАЦИЯ БОТА ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

DATA_DIR = "data"
SETTINGS_FILE = f"{DATA_DIR}/settings.json"

DEFAULT_SETTINGS = {
    "is_active": False,
    "system_prompt": "Отвечай кратко и вежливо, что сейчас я занят и не могу общаться.",
}

def load_settings():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_SETTINGS, f, ensure_ascii=False, indent=4)
        return DEFAULT_SETTINGS
    with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_settings(settings):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=4)

waiting_for_prompt = False

# --- ФУНКЦИИ ИИ ---
async def generate_reply(text, system_prompt):
    try:
        full_prompt = (
            f"Инструкция: {system_prompt}\n\n"
            f"Сообщение от пользователя: '{text}'\n\n"
            f"Сгенерируй только текст ответа. Если на это сообщение отвечать не нужно по инструкции, напиши ровно одно слово: IGNORE"
        )
        response = gemini_client.models.generate_content(
            model='gemini-1.5-flash',
            contents=full_prompt,
            config=genai_types.GenerateContentConfig(
                safety_settings=safety_settings
            )
        )
        reply = response.text.strip()
        print(f"-> Нейросеть сгенерировала: {reply}")
        if reply == "IGNORE":
            return None
        return reply
    except Exception as e:
        print(f"❌ Ошибка Gemini (возможно, блокировка): {e}")
        return None

# --- АДМИН ПАНЕЛЬ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    settings = load_settings()
    status_text = "🟢 Включен" if settings["is_active"] else "🔴 Выключен"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Статус автоответчика: {status_text}", callback_data="toggle_status")],
        [InlineKeyboardButton(text="📝 Изменить промпт ИИ", callback_data="edit_prompt")],
        [InlineKeyboardButton(text="Текущий промпт", callback_data="show_prompt")]
    ])
    
    await message.answer("🛠 **Панель управления ИИ-Автоответчиком**", reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(F.data == "toggle_status")
async def process_toggle(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    
    settings = load_settings()
    settings["is_active"] = not settings["is_active"]
    save_settings(settings)
    
    status_text = "🟢 Включен" if settings["is_active"] else "🔴 Выключен"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Статус: {status_text}", callback_data="toggle_status")],
        [InlineKeyboardButton(text="📝 Изменить промпт ИИ", callback_data="edit_prompt")],
        [InlineKeyboardButton(text="Текущий промпт", callback_data="show_prompt")]
    ])
    
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer(f"Статус изменен на: {status_text}")

@dp.callback_query(F.data == "show_prompt")
async def process_show_prompt(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    settings = load_settings()
    await callback.message.answer(f"📝 **Ваш текущий промпт:**\n\n{settings['system_prompt']}")
    await callback.answer()

@dp.callback_query(F.data == "edit_prompt")
async def process_edit_prompt(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    global waiting_for_prompt
    waiting_for_prompt = True
    await callback.message.answer("✍️ Отправьте следующим сообщением новую инструкцию для ИИ (промпт):")
    await callback.answer()

@dp.message(F.text & (F.from_user.id == ADMIN_ID))
async def handle_admin_text(message: types.Message):
    global waiting_for_prompt
    if waiting_for_prompt:
        settings = load_settings()
        settings["system_prompt"] = message.text
        save_settings(settings)
        waiting_for_prompt = False
        await message.answer("✅ Новый промпт успешно сохранен!")

# --- ЛОГИКА АВТООТВЕТЧИКА ---
@dp.business_message()
async def handle_business_message(message: types.Message):
    settings = load_settings()
    
    if not settings["is_active"]:
        print(f"[-] Пришло сообщение, но автоответчик ВЫКЛЮЧЕН в панели.")
        return
        
    if not message.text:
        return
        
    print(f"[+] Получено сообщение для анализа от {message.from_user.id}: {message.text}")
    
    ai_reply = await generate_reply(message.text, settings["system_prompt"])
    
    if ai_reply:
        try:
            await bot.send_message(
                chat_id=message.chat.id,
                text=ai_reply,
                business_connection_id=message.business_connection_id
            )
            print(f"[+] Сообщение успешно отправлено в чат!")
        except Exception as e:
            print(f"❌ Ошибка при отправке в Telegram: {e}")

# --- ЗАПУСК ---
async def main():
    print("Бот запускается...")
    await bot.delete_webhook(drop_pending_updates=True) 
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
