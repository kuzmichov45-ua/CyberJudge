import threading
import time
import pandas as pd
import io
import asyncio
import requests
from aiogram import types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand

from config import dp, bot, app, run
from database import load_votes, save_votes

# --- СИСТЕМА ПОДДЕРЖКИ АКТИВНОСТИ (RENDER) ---
def self_ping():
    while True:
        try: requests.get("https://cyberjudge-test.onrender.com/")
        except: pass
        time.sleep(300) # Пинг раз в 5 минут

threading.Thread(target=self_ping, daemon=True).start()

# --- ПЕРЕМЕННЫЕ И СОСТОЯНИЯ ---
votes = load_votes()
current_limit = 12
last_poll_msg_id = None
poll_lock = asyncio.Lock()
waiting_for = {} # Состояния: 'limit' или 'up_numbers'

# --- СЛУЖЕБНЫЕ ФУНКЦИИ ---
async def set_main_menu(bot):
    commands = [
        BotCommand(command='/poll', description='⚽️ Сбор на футбол (указать лимит)'),
        BotCommand(command='/up', description='⬆️ Поднять из резерва (напр. 1 12)'),
        BotCommand(command='/excel', description='📊 Выгрузить список в Excel'),
        BotCommand(command='/reset', description='♻️ Сбросить список игроков')
    ]
    await bot.set_my_commands(commands)

async def is_admin(message: types.Message):
    member = await message.chat.get_member(message.from_user.id)
    if member.is_chat_admin(): return True
    try: await message.delete()
    except: pass
    warn = await message.answer(f"❌ {message.from_user.first_name}, доступ только для админов!")
    await asyncio.sleep(4); await warn.delete()
    return False

def get_keyboard():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("Буду 🔥", callback_data="yes"),
           InlineKeyboardButton("Не буду 👎", callback_data="no"),
           InlineKeyboardButton("Болею 🤧", callback_data="sick"),
           InlineKeyboardButton("Под вопросом ⏳", callback_data="maybe"))
    return kb

def render_text(data, limit):
    header = f"⚽️ ЗАПИСЬ НА ФУТБОЛ ⚽️\nОСНОВНОЙ СОСТАВ: {limit} мест\n———————\n\n"
    if not data: return header + "Пока никто не записался."
    all_yes = sorted([{'id': k, **v} for k, v in data.items() if v['answer'] == 'yes'], key=lambda x: x['time'])
    sections = {'maybe': [], 'no': [], 'sick': []}
    for uid, info in data.items():
        if info['answer'] in sections: sections[info['answer']].append(info.get('name'))
    main = all_yes[:limit]; res_team = all_yes[limit:]
    res = header + f"Буду 🔥 ({len(main)}/{limit}):\n"
    for i, p in enumerate(main, 1): res += f"{i}. {p['name']}\n"
    if res_team:
        res += f"\n🟠 РЕЗЕРВ ({len(res_team)}):\n"
        for i, p in enumerate(res_team, 1): res += f"{i}. {p['name']}\n"
    if any(sections.values()):
        res += "\n———————"
        if sections['maybe']: res += f"\n⏳ ПОД ВОПРОСОМ: {', '.join(sections['maybe'])}"
        if sections['no']: res += f"\n👎 НЕ БУДУТ: {', '.join(sections['no'])}"
    return res

async def send_new_poll(chat_id):
    global last_poll_msg_id
    async with poll_lock:
        if last_poll_msg_id:
            try: await bot.delete_message(chat_id, last_poll_msg_id)
            except: pass
        new_msg = await bot.send_message(chat_id, render_text(votes, current_limit), reply_markup=get_keyboard())
        last_poll_msg_id = new_msg.message_id

# --- ОБРАБОТКА МЕНЮ КОМАНД ---

@dp.message_handler(commands=['poll'])
async def cmd_poll(message: types.Message):
    if not await is_admin(message): return
    try: await message.delete()
    except: pass
    waiting_for[message.from_user.id] = 'limit'
    q = await message.answer("🔢 **Введите лимит игроков основного состава (1-50):**")
    waiting_for[f"msg_{message.from_user.id}"] = q.message_id

@dp.message_handler(commands=['up'])
async def cmd_up(message: types.Message):
    if not await is_admin(message): return
    try: await message.delete()
    except: pass
    all_yes = [k for k, v in votes.items() if v['answer'] == 'yes']
    if len(all_yes) <= current_limit:
        m = await message.answer("ℹ️ В резерве пусто."); await asyncio.sleep(3); await m.delete()
        return
    waiting_for[message.from_user.id] = 'up_numbers'
    q = await message.answer("🔄 **Введите через пробел: [№ в резерве] [№ в основе]**\nПример: `1 12`")
    waiting_for[f"msg_{message.from_user.id}"] = q.message_id

@dp.message_handler(commands=['reset'])
async def cmd_reset(message: types.Message):
    if not await is_admin(message): return
    try: await message.delete()
    except: pass
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Да, очистить", callback_data="confirm_reset"),
                                    InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    await message.answer("♻️ **Сбросить список и удалить опрос?**", reply_markup=kb)

@dp.message_handler(commands=['excel'])
async def cmd_excel(message: types.Message):
    if not await is_admin(message): return
    all_yes = sorted([{'id': k, **v} for k, v in votes.items() if v['answer'] == 'yes'], key=lambda x: x['time'])
    data = []
    for uid, info in votes.items():
        st = info['answer']
        if st == 'yes': st = 'Основа' if any(p['id'] == uid for p in all_yes[:current_limit]) else 'Резерв'
        data.append({'Имя': info['name'], 'Статус': st})
    df = pd.DataFrame(data)
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as writer: df.to_excel(writer, index=False)
    out.seek(0)
    await message.answer_document(types.InputFile(out, filename="football.xlsx"))

# --- ОБРАБОТКА ВВОДА АДМИНА ---

@dp.message_handler(lambda m: m.from_user.id in waiting_for)
async def handle_input(message: types.Message):
    uid = message.from_user.id
    state = waiting_for.get(uid)
    
    if state == 'limit' and message.text.isdigit():
        global current_limit, votes
        current_limit = int(message.text)
        votes = {}; save_votes(votes)
        await clean_and_send(message)

    elif state == 'up_numbers':
        args = message.text.split()
        if len(args) == 2 and all(a.isdigit() for a in args):
            all_yes = sorted([{'id': k, **v} for k, v in votes.items() if v['answer'] == 'yes'], key=lambda x: x['time'])
            res_idx, main_idx = int(args[0]) - 1, int(args[1]) - 1
            if 0 <= res_idx < len(all_yes[current_limit:]) and 0 <= main_idx < current_limit:
                r_id = all_yes[current_limit:][res_idx]['id']
                m_id = all_yes[:current_limit][main_idx]['id']
                votes[r_id]['time'], votes[m_id]['time'] = votes[m_id]['time'], votes[r_id]['time']
                save_votes(votes)
                await clean_and_send(message)
                return
        await message.answer("⚠️ Ошибка. Используй формат: `1 12`")

async def clean_and_send(message):
    uid = message.from_user.id
    try:
        await message.delete()
        await bot.delete_message(message.chat.id, waiting_for[f"msg_{uid}"])
    except: pass
    waiting_for.pop(uid, None); waiting_for.pop(f"msg_{uid}", None)
    await send_new_poll(message.chat.id)

# --- CALLBACKS ---
@dp.callback_query_handler(lambda c: c.data in ["confirm_reset", "cancel"])
async def cb_reset(cb: types.CallbackQuery):
    if cb.data == "confirm_reset":
        global votes, last_poll_msg_id
        votes = {}; save_votes(votes)
        if last_poll_msg_id:
            try: await bot.delete_message(cb.message.chat.id, last_poll_msg_id)
            except: pass
            last_poll_msg_id = None
        await cb.message.edit_text("♻️ Список очищен")
    else: await cb.message.delete()
    await asyncio.sleep(2); try: await cb.message.delete()
    except: pass

@dp.callback_query_handler()
async def handle_vote(cb: types.CallbackQuery):
    votes[str(cb.from_user.id)] = {'name': cb.from_user.full_name, 'answer': cb.data, 'time': time.time()}
    save_votes(votes); await cb.answer(); await send_new_poll(cb.message.chat.id)

# --- СТАРТ ---
async def on_startup(dp): await set_main_menu(bot)

if __name__ == "__main__":
    threading.Thread(target=run, daemon=True).start()
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
