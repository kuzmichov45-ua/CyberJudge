import logging
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ВСТАВЬ СВОЙ ТОКЕН СЮДА
API_TOKEN = '8511782128:AAEYQsojhFIw_irz-lGtFrrYLt4XmE7Dugw'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Хранилище голосов (пока в памяти бота)
votes = {} 

def get_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("Буду 👍", callback_data="yes"),
        InlineKeyboardButton("Не буду 👎", callback_data="no"),
        InlineKeyboardButton("Болею 😷🤧", callback_data="sick")
    )
    return keyboard

def render_text(data):
    header = "⚽️ ЗАПИСЬ НА ФУТБОЛ ⚽️\n"
    header += "__________________________\n\n"
    text = header
    
    for status, label in [("yes", "Буду 👍"), ("no", "Не буду 👎"), ("sick", "Болею 😷🤧")]:
        users = [name for name, s in data.items() if s == status]
        text += f"{label}:\n"
        if users:
            text += "\n".join([f"{i+1}. {name}" for i, name in enumerate(users)])
        else:
            text += "пока пусто"
        text += "\n\n"
    return text

@dp.message_handler(commands=['poll'])
async def start_poll(message: types.Message):
    # Создаем новый опрос в канале
    await message.answer(render_text({}), reply_markup=get_keyboard(), parse_mode="Markdown")
    try:
        await message.delete() # Удаляем команду /poll, чтобы не мусорить
    except:
        pass

@dp.callback_query_handler()
async def handle_vote(callback_query: types.CallbackQuery):
    user_name = callback_query.from_user.full_name
    vote_type = callback_query.data
    
    # Обновляем голос пользователя
    votes[user_name] = vote_type
    
    try:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=render_text(votes),
            reply_markup=get_keyboard(),
            parse_mode="Markdown"
        )
    except:
        pass # Если текст не изменился (нажали ту же кнопку), игнорируем ошибку
    
    await callback_query.answer(f"Принято: {user_name}")

if name == 'main':
    executor.start_polling(dp, skip_updates=True)
