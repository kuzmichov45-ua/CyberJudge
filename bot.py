import threading
import logging
import time
import pandas as pd
import io
import asyncio
from aiogram import types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Импорт твоих настроек и базы
from config import dp, bot, app, run
from database import load_votes, save_votes

# Глобальные переменные
votes = load_votes()
current_limit = 12
last_poll_msg_id = None 
poll_lock = asyncio.Lock() # Защита от задвоения сообщений

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
    if not data:
        return header + "Пока никто не записался."
    
    # Сортируем тех, кто нажал "Буду", по времени для очереди
    all_yes = sorted([{'id': k, **v} for k, v in data.items() if v['answer'] == 'yes'], key=lambda x: x['time'])
    
    # Списки для остальных статусов
    sections = {'maybe': [], 'no': [], 'sick': []}
    for uid, info in data.items():
        ans = info['answer']
        if ans in sections:
            sections[ans].append(info.get('name'))
            
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
    for i, n in enumerate(sections['maybe'], 1): res += f"{i}. {n}\n"

    res += f"\n👎 НЕ БУДУ:\n"
    for i, n in enumerate(sections['no'], 1): res += f"{i}. {n}\n"

    res += f"\n🤧 БОЛЕЮ:\n"
    for i, n in enumerate(sections['sick'], 1): res += f"{i}. {n}\n"
    return res

async def send_new_poll(chat_id):
    """Удаляет старое сообщение и присылает новое в самый низ чата"""
    global last_poll_msg_id
    async with poll_lock:
        if last_poll_msg_id:
            try:
                await bot.delete_message(chat_id, last_poll_msg_id)
            except:
                pass
            last_poll_msg_id = None

        new_msg = await bot.send_message(
            chat_id, 
            render_text(votes, current_limit), 
            reply_markup=get_keyboard()
        )
        last_poll_msg_id = new_msg.message_id

@dp.message_handler(commands=['poll'])
async def start_poll(message: types.Message):
    global current_limit, votes
    if not (await message.chat.get_member(message.from_user.id)).is_chat_admin(): return
    try: await message.delete() 
    except: pass
    
    args = message.get_args()
    current_limit = int(args) if args.isdigit() else 12
    votes = {} 
    save_votes(votes)
    await send_new_poll(message.chat.id)

@dp.message_handler(commands=['up'])
async def up_player(message: types.Message):
    global votes
    if not (await message.chat.get_member(message.from_user.id)).is_chat_admin(): return
    try: await message.delete()
    except: pass
    
    args = message.get_args().split()
    all_yes = sorted([{'id': k, **v} for k, v in votes.items() if v['answer'] == 'yes'], key=lambda x: x['time'])
    
    if len(args) == 2 and all(a.isdigit() for a in args):
        res_idx, main_idx = int(args[0]) - 1, int(args[1]) - 1
        reserve = all_yes[current_limit:]
        main = all_yes[:current_limit]
        
        if 0 <= res_idx < len(reserve) and 0 <= main_idx < len(main):

            target_res = reserve[res_idx]
            target_main = main[main_idx]
            # Меняем время записи местами для перетасовки очереди
            votes[target_res['id']]['time'], votes[target_main['id']]['time'] = target_main['time'], target_res['time']
            save_votes(votes)
            await send_new_poll(message.chat.id)
    else:
        temp = await message.answer("⚠️ Ошибка! Используй: /up [номер в резерве] [номер в основе]")
        await asyncio.sleep(5); await temp.delete()

@dp.message_handler(commands=['excel'])
async def get_excel(message: types.Message):
    if not (await message.chat.get_member(message.from_user.id)).is_chat_admin(): return
    try: await message.delete()
    except: pass
    
    if not votes: return await message.answer("Список пуст.")

    all_yes = sorted([{'id': k, **v} for k, v in votes.items() if v['answer'] == 'yes'], key=lambda x: x['time'])
    data = []
    for uid, info in votes.items():
        status = info['answer']
        if status == 'yes':
            status = 'Основа' if any(p['id'] == uid for p in all_yes[:current_limit]) else 'Резерв'
        elif status == 'no': status = 'Не буду'
        elif status == 'sick': status = 'Болею'
        elif status == 'maybe': status = 'Под вопросом'
        
        data.append({
            'Имя': info['name'], 
            'Статус': status, 
            'Время': time.ctime(info['time'])
        })
    
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    await message.answer_document(types.InputFile(output, filename="football_list.xlsx"))

@dp.message_handler(commands=['reset'])
async def reset_all(message: types.Message):
    global votes, last_poll_msg_id
    if not (await message.chat.get_member(message.from_user.id)).is_chat_admin(): return
    try: await message.delete()
    except: pass

    votes = {}
    save_votes(votes)
    
    async with poll_lock:
        if last_poll_msg_id:
            try: await bot.delete_message(message.chat.id, last_poll_msg_id)
            except: pass
            last_poll_msg_id = None
            
    temp = await message.answer("♻️ Список полностью очищен.")
    await asyncio.sleep(5); await temp.delete()

@dp.callback_query_handler()
async def handle_vote(callback_query: types.CallbackQuery):
    global votes
    user_id = str(callback_query.from_user.id)
    votes[user_id] = {
        'name': callback_query.from_user.full_name, 
        'answer': callback_query.data, 
        'time': time.time()
    }
    save_votes(votes)
    await callback_query.answer()
    await send_new_poll(callback_query.message.chat.id)

if __name__ == "__main__":
    threading.Thread(target=run, daemon=True).start()
    executor.start_polling(dp, skip_updates=True)
    
