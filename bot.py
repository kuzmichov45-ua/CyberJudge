import threading
import logging
import time
import pandas as pd
import io
from aiogram import types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import dp, bot, app, run
from database import load_votes, save_votes

votes = load_votes()
current_limit = 12
last_poll_msg_id = None # Для отслеживания последнего сообщения опроса

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
    
    all_yes = sorted([{'id': k, **v} for k, v in data.items() if v['answer'] == 'yes'], key=lambda x: x['time'])
    sections = {'no': [], 'sick': [], 'maybe': []}
    for uid, info in data.items():
        if info['answer'] in sections: sections[info['answer']].append(info.get('name'))
            
    main_team = all_yes[:limit]
    reserve_team = all_yes[limit:]

    res = header + f"Буду 🔥 ({len(main_team)}/{limit}):\n"
    for i, p in enumerate(main_team, 1): res += f"{i}. {p['name']}\n"
    if reserve_team:
        res += f"\n🟠 РЕЗЕРВ ({len(reserve_team)}):\n"
        for i, p in enumerate(reserve_team, 1): res += f"{i}. {p['name']}\n"
    
    res += f"\n⏳ ПОД ВОПРОСОМ:\n"
    for i, n in enumerate(sections['maybe'], 1): res += f"{i}. {n}\n"
    res += f"\n👎 НЕ БУДУ:\n"
    for i, n in enumerate(sections['no'], 1): res += f"{i}. {n}\n"
    res += f"\n🤧 БОЛЕЮ:\n"
    for i, n in enumerate(sections['sick'], 1): res += f"{i}. {n}\n"
    return res

async def send_new_poll(chat_id):
    global last_poll_msg_id
    if last_poll_msg_id:
        try: await bot.delete_message(chat_id, last_poll_msg_id)
        except: pass
    new_msg = await bot.send_message(chat_id, render_text(votes, current_limit), reply_markup=get_keyboard())
    last_poll_msg_id = new_msg.message_id

@dp.message_handler(commands=['poll'])
async def start_poll(message: types.Message):
    global current_limit, votes
    if not (await message.chat.get_member(message.from_user.id)).is_chat_admin(): return
    try: await message.delete() # Удаляем команду /poll
    except: pass
    
    args = message.get_args()
    current_limit = int(args) if args.isdigit() else 12
    votes = {}; save_votes(votes)
    await send_new_poll(message.chat.id)

@dp.message_handler(commands=['up'])
async def up_player(message: types.Message):
    global votes
    if not (await message.chat.get_member(message.from_user.id)).is_chat_admin(): return
    try: await message.delete() # Удаляем команду /up
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
            # Меняем время местами
            votes[target_res['id']]['time'], votes[target_main['id']]['time'] = target_main['time'], target_res['time']
            save_votes(votes)
            await send_new_poll(message.chat.id)
    else:
        msg = await message.answer("Использование: /up [номер в резерве] [номер в основе]\nПример: /up 1 2")
        time.sleep(5); await msg.delete()

@dp.message_handler(commands=['excel'])
async def get_excel(message: types.Message):
    if not (await message.chat.get_member(message.from_user.id)).is_chat_admin(): return
    try: await message.delete() # Удаляем команду /excel
    except: pass
    
    all_yes = sorted([{'id': k, **v} for k, v in votes.items() if v['answer'] == 'yes'], key=lambda x: x['time'])
    data = []
    for uid, info in votes.items():
        status = info['answer']
        if status == 'yes':
            status = 'Основа' if any(p['id'] == uid for p in all_yes[:current_limit]) else 'Резерв'
        elif status == 'no': status = 'Не буду'
        elif status == 'sick': status = 'Болею'
        elif status == 'maybe': status = 'Под вопросом'
        data.append({'Имя': info['name'], 'Статус': status})
    
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    await message.answer_document(types.InputFile(output, filename="football_list.xlsx"))

@dp.callback_query_handler()
async def handle_vote(callback_query: types.CallbackQuery):
    global votes
    votes[str(callback_query.from_user.id)] = {
        'name': callback_query.from_user.full_name, 
        'answer': callback_query.data, 
        'time': time.time()
    }
    save_votes(votes)
    await send_new_poll(callback_query.message.chat.id)
    await callback_query.answer()

@dp.message_handler(commands=['reset'])
async def reset_all(message: types.Message):
    global votes, last_poll_msg_id
    # Проверка на админа
    member = await message.chat.get_member(message.from_user.id)
    if not member.is_chat_admin():
        return

    # 1. Удаляем саму команду /reset из чата (чистим мусор)
    try: await message.delete()
    except: pass

    # 2. Очищаем данные
    votes = {}
    save_votes(votes)
    
    # 3. Пытаемся удалить старое сообщение опроса, если оно есть
    if last_poll_msg_id:
        try: await bot.delete_message(message.chat.id, last_poll_msg_id)
        except: pass
        last_poll_msg_id = None

    # 4. Отправляем подтверждение, которое само удалится через 5 секунд
    confirm_msg = await message.answer("✅ Список игроков очищен! Теперь можно запускать новый сбор.")
    time.sleep(5)
    try: await confirm_msg.delete()
    except: pass
        
if __name__ == "__main__":
    threading.Thread(target=run, daemon=True).start()
    executor.start_polling(dp, skip_updates=True)
