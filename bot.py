import os
import io
import pandas as pd
from datetime import datetime
from aiogram import Bot, Dispatcher, executor, types
from config import API_TOKEN, ADMIN_IDS
from database import load_data, save_data
from handlers import set_main_menu, get_keyboard, render_text, waiting_for

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

@dp.message_handler(commands=['start', 'poll'])
async def cmd_poll(m: types.Message):
    if m.from_user.id not in ADMIN_IDS:
        return await m.answer("❌ Ця команда тільки для адміністраторів!")
    
    waiting_for[m.from_user.id] = 'limit'
    await m.answer("🔢 **Введіть ліміт співробітников:**")

@dp.message_handler(commands=['up'])
async def cmd_up(m: types.Message):
    if m.from_user.id not in ADMIN_IDS:
        return
    waiting_for[m.from_user.id] = 'up'
    await m.answer("🔄 **Введіть через пробіл: [№ резерву] [№ основи]**")

@dp.message_handler(commands=['excel'])
async def cmd_excel(m: types.Message):
    if m.from_user.id not in ADMIN_IDS: return
    db = load_data()
    if not db['votes']: return await m.answer("Список порожній")
    
    df = pd.DataFrame([{
        "Прізвище Ім'я": v['name'],
        "Статус": v['status'],
        "Час запису": v['time']
    } for v in db['votes']])
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Staff')
    output.seek(0)
    
    await m.answer_document(types.InputFile(output, filename="sahno_staff_list.xlsx"))

@dp.message_handler(commands=['reset'])
async def cmd_reset(m: types.Message):
    if m.from_user.id not in ADMIN_IDS: return
    kb = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("Так, очистити ✅", callback_data="reset_confirm"),
        types.InlineKeyboardButton("Скасувати ❌", callback_data="reset_cancel")
    )
    await m.answer("⚠️ **Скинути список персоналу?**", reply_markup=kb)

@dp.message_handler()
async def handle_text(m: types.Message):
    state = waiting_for.get(m.from_user.id)
    if not state: return

    if state == 'limit':
        if not m.text.isdigit():
            return await m.answer("Введіть число!")
        
        db = load_data()
        db['limit'] = int(m.text)
        db['votes'] = []
        save_data(db)
        
        msg = await m.answer(render_text([], db['limit']), reply_markup=get_keyboard(), parse_mode="Markdown")
        db['msg_id'] = msg.message_id
        db['chat_id'] = m.chat.id
        save_data(db)
        del waiting_for[m.from_user.id]

    elif state == 'up':
        try:
            res_idx, main_idx = map(int, m.text.split())
            db = load_data()
            limit = db['limit']
            yes_all = [v for v in db['votes'] if v['status'] == 'yes']
            yes_all.sort(key=lambda x: x['time'])
            
            if res_idx > len(yes_all[limit:]): return await m.answer("Невірний номер у резерві")
            
            target_res = yes_all[limit:][res_idx-1]
            target_main = yes_all[:limit][main_idx-1]
            
            # Меняем время местами, чтобы сдвинуть в списке
            target_res['time'], target_main['time'] = target_main['time'], target_res['time']
            
            save_data(db)
            await bot.edit_message_text(render_text(db['votes'], limit), db['chat_id'], db['msg_id'], 
                                      reply_markup=get_keyboard(), parse_mode="Markdown")
            await m.answer("Успішно змінено!")
            del waiting_for[m.from_user.id]
        except:
            await m.answer("Помилка. Формат: 1 5")

@dp.callback_query_handler()
async def cb_handler(cb: types.CallbackQuery):
    db = load_data()
    
    if cb.data.startswith("reset_"):
        if cb.data == "reset_confirm":
            db['votes'] = []
            save_data(db)
            await cb.message.edit_text("♻️ Список очищено")
        else:
            await cb.message.delete()
        return

    # Логика голосования
    user_id = cb.from_user.id
    name = cb.from_user.full_name
    
    # Удаляем старый голос если был
    db['votes'] = [v for v in db['votes'] if v['user_id'] != user_id]
    
    db['votes'].append({
        "user_id": user_id,
        "name": name,
        "status": cb.data,
        "time": datetime.now().isoformat()
    })
    save_data(db)
    
    try:
        await bot.edit_message_text(
            render_text(db['votes'], db['limit']),
            db['chat_id'],
            db['msg_id'],
            reply_markup=get_keyboard(),
            parse_mode="Markdown"
        )
    except:
        pass
    await cb.answer()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=set_main_menu)
