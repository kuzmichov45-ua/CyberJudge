import time
import asyncio
import pandas as pd
import io
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand

# Состояния ожидания
waiting_for = {}

async def set_main_menu(bot):
    commands = [
        BotCommand(command='/poll', description='Створити запис на зміну'),
        BotCommand(command='/up', description='⬆️ Підняти з резерву (напр. 1 12)'),
        BotCommand(command='/excel', description='📊 Вивантажити список у Excel'),
        BotCommand(command='/reset', description='♻️ Скинути список персоналу')
    ]
    await bot.set_my_commands(commands)

def get_keyboard():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("Буду ✅", callback_data="yes"),
        InlineKeyboardButton("Не буду ❌", callback_data="no"),
        InlineKeyboardButton("Лікарняний 🤒", callback_data="sick"),
        InlineKeyboardButton("Під питанням ⏳", callback_data="maybe")
    )
    return kb

def render_text(data, limit):
    # Полоски строго под первой строкой
    header = "📋 ЗАПИС НА ЗМІНУ SAHNO 📋\n"
    header += "—————————————————\n"
    header += f"ОСНОВНИЙ СКЛАД: {limit} мест\n\n"
    
    if not data:
        return header + "Поки що ніхто не записався."

    # Сортировка по времени
    all_yes = sorted([{'id': k, **v} for k, v in data.items() if v.get('answer') == 'yes'], key=lambda x: x['time'])
    
    # Списки для остальных
    sections = {'maybe': [], 'no': [], 'sick': []}
    for uid, info in data.items():
        ans = info.get('answer')
        if ans in sections:
            sections[ans].append(info.get('name'))

    main = all_yes[:limit]
    res_team = all_yes[limit:]

    # Блок Буду
    res = header + f"Буде ✅ ({len(main)}/{limit}):\n"
    for i, p in enumerate(main, 1):
        res += f"{i}. {p['name']}\n"

    # Блок Резерв
    if res_team:
        res += f"\n🟠 РЕЗЕРВ ({len(res_team)}):\n"
        for i, p in enumerate(res_team, 1):
            res += f"{i}. {p['name']}\n"

    # Блоки Под вопросом / Не буду / Болею (с нумерацией и переносом строки)
    footer = ""
    if sections['maybe']:
        footer += f"\n⏳ ПІД ПИТАННЯМ:\n"
        for i, name in enumerate(sections['maybe'], 1):
            footer += f"{i}. {name}\n"
            
    if sections['no']:
        footer += f"\n❌ НЕ БУДУТЬ:\n"
        for i, name in enumerate(sections['no'], 1):
            footer += f"{i}. {name}\n"
            
    if sections['sick']:
        footer += f"\n🤧 НА ЛІКАРНЯНОМУ:\n"
        for i, name in enumerate(sections['sick'], 1):
            footer += f"{i}. {name}\n"
            
    return res + footer
