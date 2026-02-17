import threading
import time
import asyncio
import requests
from aiogram import types
from aiogram.utils import executor
from config import dp, bot, run
from database import load_votes, save_votes
import handlers as h  # Импортируем наш новый файл

# Самопинг для Render
def self_ping():
    while True:
        try: requests.get("https://cyberjudge-test.onrender.com/")
        except: pass
        time.sleep(300)

threading.Thread(target=self_ping, daemon=True).start()

votes = load_votes()
current_limit = 12
last_poll_msg_id = None
poll_lock = asyncio.Lock()

async def is_admin(message: types.Message):
    member = await message.chat.get_member(message.from_user.id)
    if member.is_chat_admin(): return True
    try: await message.delete()
    except: pass
    return False

async def send_poll(chat_id):
    global last_poll_msg_id
    async with poll_lock:
        if last_poll_msg_id:
            try: await bot.delete_message(chat_id, last_poll_msg_id)
            except: pass
        msg = await bot.send_message(chat_id, h.render_text(votes, current_limit), reply_markup=h.get_keyboard())
        last_poll_msg_id = msg.message_id

@dp.message_handler(commands=['poll'])
async def cmd_poll(m: types.Message):
    if not await is_admin(m): return
    try: await m.delete()
    except: pass
    h.waiting_for[m.from_user.id] = 'limit'
    q = await m.answer("🔢 **Введите лимит игроков (1-50):**")
    h.waiting_for[f"msg_{m.from_user.id}"] = q.message_id

@dp.message_handler(commands=['up'])
async def cmd_up(m: types.Message):
    if not await is_admin(m): return
    try: await m.delete()
    except: pass
    h.waiting_for[m.from_user.id] = 'up_numbers'
    q = await m.answer("🔄 **Введите через пробел: [№ резерв] [№ основа] (напр. 1 12)**")
    h.waiting_for[f"msg_{m.from_user.id}"] = q.message_id

@dp.message_handler(commands=['reset'])
async def cmd_reset(m: types.Message):
    if not await is_admin(m): return
    try: await m.delete()
    except: pass
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("✅ Да, очистить", callback_data="confirm_reset"),
                                          types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    await m.answer("♻️ **Сбросить список?**", reply_markup=kb)

@dp.message_handler(lambda m: m.from_user.id in h.waiting_for)
async def handle_input(m: types.Message):
    uid = m.from_user.id
    state = h.waiting_for.get(uid)
    global current_limit, votes
    
    if state == 'limit' and m.text.isdigit():
        current_limit = int(m.text)
        votes = {}; save_votes(votes)
    elif state == 'up_numbers':
        args = m.text.split()
        if len(args) == 2 and all(a.isdigit() for a in args):
            all_yes = sorted([{'id': k, **v} for k, v in votes.items() if v['answer'] == 'yes'], key=lambda x: x['time'])
            r_idx, m_idx = int(args[0]) - 1, int(args[1]) - 1
            if 0 <= r_idx < len(all_yes[current_limit:]) and 0 <= m_idx < current_limit:
                rid, mid = all_yes[current_limit:][r_idx]['id'], all_yes[:current_limit][m_idx]['id']
                votes[rid]['time'], votes[mid]['time'] = votes[mid]['time'], votes[rid]['time']
                save_votes(votes)
    
    try:
        await m.delete()
        await bot.delete_message(m.chat.id, h.waiting_for[f"msg_{uid}"])
    except: pass
    h.waiting_for.pop(uid, None); h.waiting_for.pop(f"msg_{uid}", None)
    await send_poll(m.chat.id)

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
    await asyncio.sleep(2)
    try: await cb.message.delete()
    except: pass

@dp.callback_query_handler()
async def handle_vote(cb: types.CallbackQuery):
    votes[str(cb.from_user.id)] = {'name': cb.from_user.full_name, 'answer': cb.data, 'time': time.time()}
    save_votes(votes); await cb.answer(); await send_poll(cb.message.chat.id)

if __name__ == "__main__":
    threading.Thread(target=run, daemon=True).start()
    executor.start_polling(dp, skip_updates=True, on_startup=lambda d: h.set_main_menu(bot))
    
