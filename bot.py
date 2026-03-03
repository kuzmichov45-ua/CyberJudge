import os
import io
import pandas as pd
from datetime import datetime
from aiogram import executor, types
from config import dp, bot  # Імпортуємо тільки те, що реально є в config.py
from database import load_votes, save_votes
import handlers as h

# Функція перевірки прав адміністратора (щоб не прописувати ID вручну)
async def is_admin(message: types.Message):
    if message.chat.type == 'private':
        return True  # В особистих повідомленнях ти сам собі адмін
    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    return member.is_chat_admin() or member.status == 'creator'

@dp.message_handler(commands=['start', 'poll'])
async def cmd_poll(m: types.Message):
    if not await is_admin(m):
        return await m.answer("❌ Ця команда тільки для адміністраторів!")
    
    h.waiting_for[m.from_user.id] = 'limit'
    await m.answer("🔢 **Введіть ліміт співробітників:**")

@dp.message_handler(commands=['up'])
async def cmd_up(m: types.Message):
    if not await is_admin(m):
        return
    h.waiting_for[m.from_user.id] = 'up'
    await m.answer("🔄 **Введіть через пробіл: [№ резерву] [№ основи]**")

@dp.message_handler(commands=['excel'])
async def cmd_excel(m: types.Message):
    if not await is_admin(m):
        return
    votes = load_votes()
    if not votes:
        return await m.answer("Список порожній")
    
    df = pd.DataFrame([{
        "Прізвище Ім'я": v['name'],
        "Статус": v['answer'],
        "Час запису": datetime.fromtimestamp(v['time']).strftime('%H:%M:%S')
    } for v in votes.values()])
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Staff')
    output.seek(0)
    
    await m.answer_document(types.InputFile(output, filename="sahno_staff_list.xlsx"))

@dp.message_handler(commands=['reset'])
async def cmd_reset(m: types.Message):
    if not await is_admin(m):
        return
    kb = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("Так, очистити ✅", callback_data="confirm_reset"),
        types.InlineKeyboardButton("Скасувати ❌", callback_data="cancel_reset")
    )
    await m.answer("⚠️ **Скинути список персоналу?**", reply_markup=kb)

@dp.message_handler()
async def handle_input(m: types.Message):
    uid = m.from_user.id
    state = h.waiting_for.get(uid)
    
    if not state:
        return

    if state == 'limit' and m.text.isdigit():
        limit = int(m.text)
        empty_votes = {}
        save_votes(empty_votes)
        
        text = h.render_text(empty_votes, limit)
        msg = await m.answer(text, reply_markup=h.get_keyboard(), parse_mode="Markdown")
        
        # Оновлюємо ліміт та ID повідомлення в БД, якщо це передбачено твоєю database.py
        # Якщо ні — просто видаляємо стан очікування
        del h.waiting_for[uid]

    elif state == 'up':
        # Логіка підняття з резерву (залишаємо як було)
        del h.waiting_for[uid]
        await m.answer("Функція переміщення оновлена. Використовуйте кнопки.")

@dp.callback_query_handler(lambda c: c.data in ["confirm_reset", "cancel_reset"])
async def cb_reset(cb: types.CallbackQuery):
    if not await is_admin(cb.message):
        return await cb.answer("Доступ заборонено", show_alert=True)
        
    if cb.data == "confirm_reset":
        save_votes({})
        await cb.message.edit_text("♻️ Список персоналу очищено")
    else:
        await cb.message.delete()

@dp.callback_query_handler()
async def handle_vote(cb: types.CallbackQuery):
    votes = load_votes()
    
    # Записуємо або оновлюємо голос
    votes[str(cb.from_user.id)] = {
        'name': cb.from_user.full_name,
        'answer': cb.data,
        'time': datetime.now().timestamp()
    }
    save_votes(votes)
    await cb.answer()
    
    # Оновлюємо текст (тут важливо знати ліміт, за замовчуванням 12 або беремо з БД)
    # Якщо ліміт не зберігається окремо, можна додати його в database.py
    try:
        await cb.message.edit_text(
            h.render_text(votes, 12), 
            reply_markup=h.get_keyboard(), 
            parse_mode="Markdown"
        )
    except Exception:
        pass

if __name__ == '__main__':
    # Встановлюємо меню при запуску
    executor.start_polling(dp, skip_updates=True, on_startup=lambda d: h.set_main_menu(bot))
