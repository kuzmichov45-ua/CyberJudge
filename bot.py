import logging
import json
import os
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from flask import Flask
import threading

app = Flask('')

@app.route('/')
def home():
    return "I am alive"

def run():
    app.run(host='0.0.0.0', port=10000)
# Настройка сохранения
DB_FILE = 'votes.json'

def save_votes(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_votes():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

# ТВОЙ НОВЫЙ ТОКЕН
API_TOKEN = os.getenv("TOKEN")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Загружаем голоса
votes = load_votes()

def get_keyboard():
    """Создает кнопки под сообщением"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("Буду 👍", callback_data="yes"),
        InlineKeyboardButton("Не буду 👎", callback_data="no"),
        InlineKeyboardButton("Болею 😷🤧", callback_data="sick")
    )
    return keyboard

def render_text(data):
    """Формирует текст списка участников"""
    header = "⚽️ ЗАПИСЬ НА ФУТБОЛ ⚽️\n"
    header += "______\n\n"
    
    # Если данных еще нет (никто не нажал кнопку), возвращаем заголовок с призывом
    if not data:
        return header + "Пока никто не записался. Будешь первым?"

    text = header
    
    # Категории опроса
    categories = [
        ("yes", "Буду 👍"),
        ("no", "Не буду 👎"),
        ("sick", "Болею 😷🤧")
    ]
    
    sections = {'yes': [], 'no': [], 'sick': []}
    for user_id, data in data.items():
        name = data.get('name', 'Аноним')
        status = data.get('answer')
        if status in sections:
            sections[status].append(name)

    text = "⚽️ ЗАПИСЬ НА ФУТБОЛ ⚽️\n\n"
    text += "Буду 👍:\n" + ("\n".join([f"{i+1}. {n}" for i, n in enumerate(sections['yes'])]) if sections['yes'] else "пока пусто") + "\n\n"
    text += "Не буду 👎:\n" + ("\n".join([f"{i+1}. {n}" for i, n in enumerate(sections['no'])]) if sections['no'] else "пока пусто") + "\n\n"
    text += "Болею 🤧🩹:\n" + ("\n".join([f"{i+1}. {n}" for i, n in enumerate(sections['sick'])]) if sections['sick'] else "пока пусто")

@dp.message_handler(commands=['poll'])
@dp.channel_post_handler(lambda message: message.text and message.text.startswith('/poll'))
async def start_poll(message: types.Message):
    """Команда /poll создает новый опрос"""
    await bot.send_message(
        chat_id=message.chat.id,
        text=render_text({}),
        reply_markup=get_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await message.delete()
    except Exception as e:
        logging.error(f"Ошибка удаления: {e}")

@dp.callback_query_handler()
async def handle_vote(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user_full_name = callback_query.from_user.full_name
    vote_type = callback_query.data

    # Сохраняем голос по ID пользователя (цифры), а не по имени
    # Это гарантирует, что каждый игрок — это отдельная запись
    votes[user_id] = {'name': user_full_name, 'answer': vote_type}

    # 1. Сохраняем голос, чтобы данные не терялись при перезапуске
    save_votes(votes)

try:
        # 1. Сохраняем ID чата
        chat_id = callback_query.message.chat.id

        # 2. Удаляем старое сообщение
        try:
            await callback_query.message.delete()
        except Exception:
            pass

        # 3. Отправляем НОВОЕ сообщение (без Markdown для надежности)
        await bot.send_message(
            chat_id=chat_id,
            text=render_text(votes),
            reply_markup=get_keyboard()
        )
    except Exception as e:
        logging.error(f"Ошибка перемещения сообщения: {e}")

    # 4. Всплывающее уведомление
    await callback_query.answer(f"Принято: {user_full_name}")

if __name__ == "__main__":
    # Запуск Flask и бота
    threading.Thread(target=run, daemon=True).start()
    bot.delete_webhook(drop_pending_updates=True)
    executor.start_polling(dp, skip_updates=True)
