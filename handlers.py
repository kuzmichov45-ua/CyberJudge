import logging
from aiogram import Bot, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand

# Состояния ожидания
waiting_for = {}

async def set_main_menu(bot: Bot):
    commands = [
        BotCommand(command='/poll', description='Створити запис на зміну'),
        BotCommand(command='/up', description='Підняти з резерву (напр. 1 12)'),
        BotCommand(command='/excel', description='Вивантажити список у Excel'),
        BotCommand(command='/reset', description='Скинути список персоналу')
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
    header = "📋 **ЗАПИС НА ЗМІНУ SAHNO**\n"
    header += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
    header += f"📍 ОСНОВНИЙ СКЛАД: {limit} місць\n\n"
    
    if not data:
        return header + "Поки що ніхто не записався."

    # Разделение по статусам
    yes_list = [v for v in data if v['status'] == 'yes']
    maybe = [v for v in data if v['status'] == 'maybe']
    no = [v for v in data if v['status'] == 'no']
    sick = [v for v in data if v['status'] == 'sick']

    # Сортировка по времени
    yes_list.sort(key=lambda x: x['time'])
    
    main = yes_list[:limit]
    res_team = yes_list[limit:]

    res = header + f"**Буде** ✅ ({len(main)}/{limit}):\n"
    for i, v in enumerate(main, 1):
        res += f"{i}. {v['name']}\n"

    if res_team:
        res += f"\n**РЕЗЕРВ** ({len(res_team)}):\n"
        for i, v in enumerate(res_team, 1):
            res += f"{i}. {v['name']}\n"

    footer = ""
    if maybe:
        footer += f"\n**ПІД ПИТАННЯМ** ⏳:\n"
        for i, v in enumerate(maybe, 1):
            footer += f"{i}. {v['name']}\n"
    
    if no:
        footer += f"\n**НЕ БУДУТЬ** ❌:\n"
        for i, v in enumerate(no, 1):
            footer += f"{i}. {v['name']}\n"

    if sick:
        footer += f"\n**НА ЛІКАРНЯНОМУ** 🤒:\n"
        for i, v in enumerate(sick, 1):
            footer += f"{i}. {v['name']}\n"

    return res + footer
