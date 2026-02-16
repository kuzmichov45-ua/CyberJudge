import threading
import logging
from aiogram import types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Импортируем наше разделение
from config import dp, bot, app, run
from database import load_votes, save_votes

# Загружаем голоса при старте
votes = load_votes()

def get_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("Буду 🔥", callback_data="yes"),
        InlineKeyboardButton("Не буду 👎", callback_data="no"),
        InlineKeyboardButton("Болею 🤧", callback_data="sick")
    )
    return keyboard

def render_text(data):
    header = "⚽️ ЗАПИСЬ НА ФУТБОЛ ⚽️\n"
    header += "———————\n\n"
    if not data:
        return header + "Пока никто не записался. Будешь первым?"
    
    sections = {'yes': [], 'no': [], 'sick': []}
    for user_info in data.values():
        status = user_info.get('answer')
        name = user_info.get('name', 'Аноним')
        if status in sections:
            sections[status].append(name)

    res = header
    res += f"Буду 🔥 : {len(sections['yes'])}\n"
    for i, name in enumerate(sections['yes'], 1):
        res += f"{i}. {name}\n"
        
    res += f"\nНе буду 👎 : {len(sections['no'])}\n"
    for i, name in enumerate(sections['no'], 1):
        res += f"{i}. {name}\n"

    res += f"\nБолею 🤧 : {len(sections['sick'])}\n"
    for i, name in enumerate(sections['sick'], 1):
        res += f"{i}. {name}\n"
    return res

@dp.message_handler(commands=['poll'])
async def start_poll(message: types.Message):
    member = await message.chat.get_member(message.from_user.id)
    if not member.is_chat_admin():
        return await message.reply("❌ Только админы могут запускать опрос.")

    await bot.send_message(
        chat_id=message.chat.id,
        text=render_text({}),
        reply_markup=get_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await message.delete()
    except:
        pass

@dp.callback_query_handler()
async def handle_vote(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    user_full_name = callback_query.from_user.full_name
    vote_type = callback_query.data
    
    votes[user_id] = {'name': user_full_name, 'answer': vote_type}
    save_votes(votes)

    try:
        await callback_query.message.delete()
        await bot.send_message(
            chat_id=callback_query.message.chat.id,
            text=render_text(votes),
            reply_markup=get_keyboard(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Ошибка перемещения: {e}")

    await callback_query.answer(f"Принято: {user_full_name}")

@dp.message_handler(commands=['reset'])
async def cmd_reset(message: types.Message):
    member = await message.chat.get_member(message.from_user.id)
    if not member.is_chat_admin():
        return await message.reply("❌ Только админы могут сбрасывать список.")

    try:
        await message.delete()
    except:
        pass

    global votes
    votes = {}
    save_votes(votes)
    await message.answer("✅ Список очищен! Теперь можно запускать новый сбор")

if __name__ == "__main__":
    threading.Thread(target=run, daemon=True).start()
    executor.start_polling(dp, skip_updates=True)
