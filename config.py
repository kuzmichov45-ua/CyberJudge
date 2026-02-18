import os
import logging
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

load_dotenv()

# Настройки логирования
logging.basicConfig(level=logging.INFO)

# Токен и инициализация
API_TOKEN = os.getenv("TOKEN")
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

def run():
    pass
