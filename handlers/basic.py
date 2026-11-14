# -*- coding: utf-8 -*-
"""Команды /start, /help, /id."""

from config import ALLOWED, CHAT_ID
from content.texts import HELP_TEXT, START_TEXT
from core.helpers import reply
from handlers.menu import menu_kb, send_commands_link
from handlers.miniapp import claim_from_start


async def cmd_start(update, context):
    private = update.effective_chat.type == "private"
    args = getattr(context, "args", None) or []
    if private and args and args[0].startswith("r_"):
        return await claim_from_start(update, context, args[0])
    await update.effective_message.reply_text(START_TEXT, reply_markup=menu_kb() if private else None)


async def cmd_help(update, context):
    private = update.effective_chat.type == "private"
    if await send_commands_link(update):
        return
    await reply(update, HELP_TEXT, **({"reply_markup": menu_kb()} if private else {}))


async def cmd_id(update, context):
    cid = update.effective_chat.id
    ok = "✅ бот тут работает" if cid in ALLOWED else "❌ бот здесь молчит: этот чат не совпадает с CHAT_ID в коде"
    await update.effective_message.reply_text(
        f"ID этого чата: {cid}\n{ok}\nCHAT_ID в коде: {CHAT_ID}\nверсия: 31")
