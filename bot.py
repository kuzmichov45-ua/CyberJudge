import threading
import logging
import time
import pandas as pd
import io
from aiogram import types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Импорт твоих настроек
from config import dp, bot, app, run
from database import load_votes, save_votes

votes = load_votes()
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
    header = f"⚽️ ЗАПИСЬ НА ФУТБОЛ ⚽️\nОСНОВНОЙ СОСТАВ: {limit} мест\n———————\n\n"
    if not data: return header + "Пока никто не записался."
    
    all_yes = []
    sections = {'no': [], 'sick': [], 'maybe': []}
    
    for uid, info in data.items():
        ans = info.get('answer')
        if ans == 'yes':
            all_yes.append({'id': uid, 'name': info.get('name'), 'time': info.get('time', 0)})
        elif ans in sections:
            sections[ans].append(info.get('name'))
            
    # Сортировка по времени для формирования основы и резерва
    all_yes.sort(key=lambda x: x['time'])
    main_team = all_yes[:limit]
    reserve_team = all_yes[limit:]

    res = header + f"Буду 🔥 ({len(main_team)}/{limit}):\n"
    for i, p in enumerate(main_team, 1):
        res += f"{i}. {p['name']}\n"
        
    if reserve_team:
        res += f"\n🟠 РЕЗЕРВ ({len(reserve_team)}):\n"
        for i, p in enumerate(reserve_team, 1):
            res += f"{i}. {p['name']}\n"

    res += f"\n⏳ ПОД ВОПРОСОМ:\n"
    for i, n in enumerate(sections['maybe'], 1):
        res += f"{i}. {n}\n"

    # РАЗДЕЛЕННЫЕ СПИСКИ
    res += f"\n👎 НЕ БУДУ:\n"
    for i, n in enumerate(sections['no'], 1):
        res += f"{i}. {n}\n"

    res += f"\n🤧 БОЛЕЮ:\n"
    for i, n in enumerate(sections['sick'], 1):
        res += f"{i}. {n}\n"
    return res

@dp.message_handler(commands=['poll'])
async def start_poll(message: types.Message):
    global current_limit, votes
    member = await message.chat.get_member(message.from_user.id)
    if not member.is_chat_admin(): return
    
    args = message.get_args()
    current_limit = int(args) if args.isdigit() else 12
    votes = {} 
    save_votes(votes)
    await message.answer(render_text(votes, current_limit), reply_markup=get_keyboard())

@dp.message_handler(commands=['up'])
async def up_player(message: types.Message):
    global votes
    member = await message.chat.get_member(message.from_user.id)
    if not member.is_chat_admin(): return
    
    # Получаем список тех, кто в резерве
    all_yes = sorted([{'id': k, **v} for k, v in votes.items() if v['answer'] == 'yes'], key=lambda x: x['time'])
    if len(all_yes) <= current_limit:
        return await message.reply("В резерве пока никого нет.")
        
    reserve = all_yes[current_limit:]
    args = message.get_args()
    
    if args.isdigit() and 0 < int(args) <= len(reserve):
        target_player = reserve[int(args)-1]
        last_in_main = all_yes[current_limit-1]
        
        # Меняем их время местами, чтобы таргет стал чуть раньше "последнего в основе"
        votes[target_player['id']]['time'] = last_in_main['time'] - 0.1
        save_votes(votes)
        
        await message.answer(f"✅ {target_player['name']} поднят в основной состав!")
        # Перерисовываем опрос
        await message.answer(render_text(votes, current_limit), reply_markup=get_keyboard())
    else:
        await message.reply(f"Укажи номер игрока из резерва. Пример: /up 1")

@dp.message_handler(commands=['excel'])
async def get_excel(message: types.Message):
    member = await message.chat.get_member(message.from_user.id)
    if not member.is_chat_admin(): return
    
    if not votes:
        return await message.reply("Список пока пуст.")

# Создаем таблицу
    data = []
    for uid, info in votes.items():
        data.append({'Имя': info['name'], 'Статус': info['answer'], 'Время записи': time.ctime(info['time'])})
    
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Футбол')
    output.seek(0)
    
    await message.answer_document(types.InputFile(output, filename="football_list.xlsx"), caption="📊 Актуальный список игроков")

@dp.callback_query_handler()
async def handle_vote(callback_query: types.CallbackQuery):
    global votes
    user_id = str(callback_query.from_user.id)
    vote_type = callback_query.data
    
    votes[user_id] = {
        'name': callback_query.from_user.full_name, 
        'answer': vote_type, 
        'time': time.time()
    }
    save_votes(votes)

    try:
        await callback_query.message.edit_text(
            text=render_text(votes, current_limit),
            reply_markup=get_keyboard()
        )
    except Exception:
        pass
    await callback_query.answer()

if __name__ == "__main__":
    threading.Thread(target=run, daemon=True).start()
    executor.start_polling(dp, skip_updates=True)
