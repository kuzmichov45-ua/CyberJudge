import os
import logging
from aiogram import Bot, Dispatcher
from flask import Flask
from dotenv import load_dotenv

load_dotenv()

# Настройки логирования
logging.basicConfig(level=logging.INFO)

# Токен и инициализация
API_TOKEN = os.getenv("TOKEN")
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Flask для Render
app = Flask('')

@app.route('/')
def home():
    return "I am alive"

def run():
    app.run(host='0.0.0.0', port=10000)
