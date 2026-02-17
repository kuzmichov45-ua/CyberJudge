import time
import asyncio
import pandas as pd
import io
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from database import save_votes

# Состояния ожидания
waiting_for = {}

async def set_main_menu(bot):
    commands = [
        BotCommand(command='/poll', description='⚽️ Сбор на футбол (указать лимит)'),
        BotCommand(command='/up', description='⬆️ Поднять из резерва (напр. 1 12)'),
        BotCommand(command='/excel', description='📊 Выгрузить список в Excel'),
        BotCommand(command='/reset', description='♻️ Сбросить список игроков')
    ]
    await bot.set_my_commands(commands)

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
    return res
