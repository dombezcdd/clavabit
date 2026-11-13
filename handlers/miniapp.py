# -*- coding: utf-8 -*-
"""Mini App: кнопка «Игры», приём результата смены (/start r_<сессия>_<очки>)."""

import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from core.helpers import reply
from core.logger import log
from database.db import db
from handlers.work import finish_task
from services.miniapp import mini_claim, mini_enabled, mini_link, mult_for
from services.jobs import open_task

PLAY_WORDS = {"игры в приложении", "приложение", "мини апп", "мини-апп", "арена", "играть"}


async def send_hub(update, context):
    if not mini_enabled():
        return await reply(update, "Мини-приложение пока не подключено.")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🕹 Открыть игры", url=mini_link(context.bot.username, "hub"))]])
    await update.effective_message.reply_text(
        "🕹 <b>Игры в приложении</b>: Монополия против ботов, 2048, Сапёр, Змейка и тренировка всех профессий. "
        "Награды за них нет, это просто для удовольствия.", parse_mode="HTML", reply_markup=kb)


async def cmd_play(update, context):
    await send_hub(update, context)


async def handle_miniapp(update, context, clean):
    if clean in PLAY_WORDS:
        await send_hub(update, context)
        return True
    return False


async def claim_from_start(update, context, arg):
    """/start r_<sid>_<очки> из мини-игры смены."""
    msg = update.effective_message
    me = update.effective_user
    try:
        _, sid, score = arg.split("_", 2)
        score = int(score)
    except ValueError:
        return await msg.reply_text("Не удалось прочитать результат игры.")
    ok, text, s = mini_claim(me.id, sid, score)
    if not ok:
        return await msg.reply_text("🎮 " + text)
    t = open_task(me.id)
    if not t or abs(t["created"] - s["task_created"]) > 0.5 or t["expires"] < time.time():
        return await msg.reply_text("🎮 Задание уже закрыто или время вышло, оплата не начислена.")
    mult = mult_for(score)
    try:
        await finish_task(context.bot, s["chat_id"], me.id, reply_to=s["reply_to"], mult=mult, score=score)
    except Exception:
        log.exception("mini claim")
        return await msg.reply_text("Не получилось отправить результат в чат, попробуй ещё раз.")
    await msg.reply_text(f"✅ Результат {score}/100 засчитан, зарплата ×{mult:g}. Загляни в чат!")
