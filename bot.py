import logging
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ТОКЕН, который ты получил у @BotFather
API_TOKEN = '8511782128:AAEYQsojhFIw_irz-lGtFrrYLt4XmE7Dugw'

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Временное хранилище голосов (сбросится при перезагрузке сервера)
votes = {}

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
    header += "__________________________\n\n"
    
    text = header
    
    # Категории опроса
    categories = [
        ("yes", "Буду 👍"),
        ("no", "Не буду 👎"),
        ("sick", "Болею 😷🤧")
    ]
    
    for status, label in categories:
        # Собираем список имен для конкретного статуса
        users = [name for name, s in data.items() if s == status]
        
        text += f"{label}:\n"
        if users:
            # Нумеруем список
            text += "\n".join([f"{i+1}. {name}" for i, name in enumerate(users)])
        else:
            text += "пока пусто"
        text += "\n\n"
        
    return text

@dp.message_handler(commands=['poll'])
async def start_poll(message: types.Message):
    """Команда /poll создает новый опрос"""
    # Отправляем сообщение с пустым списком и кнопками
    await message.answer(render_text({}), reply_markup=get_keyboard(), parse_mode="Markdown")
    
    # Удаляем само сообщение с командой /poll, чтобы не мешало
    try:
        await message.delete()
    except Exception as e:
        logging.error(f"Не удалось удалить сообщение: {e}")

@dp.callback_query_handler()
async def handle_vote(callback_query: types.CallbackQuery):
    """Обработка нажатий на кнопки"""
    user_name = callback_query.from_user.full_name
    vote_type = callback_query.data
    
    # Записываем или обновляем голос пользователя
    votes[user_name] = vote_type
    
    # Редактируем текущее сообщение, обновляя текст списка
    try:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=render_text(votes),
            reply_markup=get_keyboard(),
            parse_mode="Markdown"
        )
    except Exception as e:
        # Если пользователь нажал ту же кнопку, текст не изменится и Telegram выдаст ошибку
        # Мы её просто игнорируем
        logging.info(f"Текст не изменился: {e}")
    
    # Всплывающее уведомление в Telegram: "Голос принят"
    await callback_query.answer(f"Принято: {user_name}")

if name == 'main':
    # Запуск бота
    executor.start_polling(dp, skip_updates=True)
