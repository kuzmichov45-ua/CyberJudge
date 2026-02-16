import threading
import logging
import time
from aiogram import types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Импортируем наше разделение из других файлов
from config import dp, bot, app, run
from database import load_votes, save_votes

# Загружаем голоса и устанавливаем лимит по умолчанию
votes = load_votes()
# Глобальная переменная для лимита (сбрасывается при новом /poll)
current_limit = 12

def get_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("Буду 🔥", callback_data="yes"),
        InlineKeyboardButton("Не буду 👎", callback_data="no"),
        InlineKeyboardButton("Болею 🤧", callback_data="sick"),
        InlineKeyboardButton("Под вопросом ⏳", callback_data="maybe")
    )
    return keyboard

def render_text(data, limit):
    header = f"⚽️ ЗАПИСЬ НА ФУТБОЛ ⚽️\n"
    header += f"ОСНОВНОЙ СОСТАВ: {limit} мест\n"
    header += "———————\n\n"
    
    if not data:
        return header + "Пока никто не записался. Будешь первым?"
    
    # Сортируем всех, кто нажал "Буду", по времени нажатия
    all_yes = []
    sections = {'no': [], 'sick': [], 'maybe': []}
    
    for user_id, info in data.items():
        ans = info.get('answer')
        name = info.get('name', 'Аноним')
        timestamp = info.get('time', 0)
        
        if ans == 'yes':
            all_yes.append({'name': name, 'time': timestamp})
        elif ans in sections:
            sections[ans].append(name)
            
    # Сортировка по времени (кто раньше нажал, тот выше в списке)
    all_yes.sort(key=lambda x: x['time'])
    
    # Делим "Буду" на Основу и Резерв
    main_team = all_yes[:limit]
    reserve_team = all_yes[limit:]

    res = header
    res += f"Буду 🔥 ({len(main_team)}/{limit}):\n"
    for i, p in enumerate(main_team, 1):
        res += f"{i}. {p['name']}\n"
        
    if reserve_team:
        res += f"\n🟠 РЕЗЕРВ ({len(reserve_team)}):\n"
        for i, p in enumerate(reserve_team, 1):
            res += f"{i}. {p['name']}\n"

    res += f"\n⏳ ПОД ВОПРОСОМ:\n"
    for i, name in enumerate(sections['maybe'], 1):
        res += f"{i}. {name}\n"

    res += f"\n👎 НЕ БУДУ / 🤧 БОЛЕЮ:\n"
    others = sections['no'] + sections['sick']
    for i, name in enumerate(others, 1):
        res += f"{i}. {name}\n"
        
    return res

@dp.message_handler(commands=['poll'])
async def start_poll(message: types.Message):
    global current_limit, votes
    member = await message.chat.get_member(message.from_user.id)
    if not member.is_chat_admin():
        return await message.reply("❌ Только админы могут запускать опрос.")

    # Проверяем, указал ли админ лимит (например /poll 14)
    args = message.get_args()
    if args.isdigit():
        current_limit = int(args)
    else:
        current_limit = 12

    votes = {} # Сбрасываем список при новом опросе
    save_votes(votes)

    await bot.send_message(
        chat_id=message.chat.id,
        text=render_text({}, current_limit),
        reply_markup=get_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await message.delete()
    except:
        pass

@dp.callback_query_handler()
async def handle_vote(callback_query: types.CallbackQuery):
    global votes
    user_id = str(callback_query.from_user.id)
    user_full_name = callback_query.from_user.full_name
    vote_type = callback_query.data
    
    # Сохраняем голос с меткой времени (важно для очереди в резерв)
    votes[user_id] = {
        'name': user_full_name, 
        'answer': vote_type, 
        'time': time.time()
    }
    save_votes(votes)

    try:
        # Пытаемся удалить старое, чтобы опрос всегда был внизу
        await callback_query.message.delete()
        await bot.send_message(
            chat_id=callback_query.message.chat.id,
            text=render_text(votes, current_limit),
            reply_markup=get_keyboard(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Ошибка перемещения: {e}")

    await callback_query.answer(f"Выбрано: {vote_type}")

@dp.message_handler(commands=['reset'])
async def cmd_reset(message: types.Message):
    member = await message.chat.get_member(message.from_user.id)
    if not member.is_chat_admin():
        return await message.reply("❌ Только админы могут сбрасывать список.")

    global votes
    votes = {}
    save_votes(votes)
    await message.answer("✅ Список очищен!")

if __name__ == "__main__":
    threading.Thread(target=run, daemon=True).start()
    executor.start_polling(dp, skip_updates=True)
