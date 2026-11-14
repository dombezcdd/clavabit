# -*- coding: utf-8 -*-
"""Сборка и запуск приложения."""

import asyncio
import os
import sys

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from config import BASE, CHAT_ID, OWNER_USERNAME, TEST_CHAT_ID, TOKEN
from database.state import state_get
from handlers.miniapp import cmd_play
from handlers.monopoly import cmd_monopoly, on_mono_btn
from handlers.basic import cmd_help, cmd_id, cmd_start
from handlers.chat_admin import on_new_members
from handlers.dates_gifts import on_date_btn, on_gift_btn
from handlers.duel import cmd_duel, on_challenge_btn
from handlers.economy import cmd_balance, cmd_bonus, cmd_buy, cmd_coins_give, cmd_duels, cmd_item_add, cmd_item_del, cmd_order_done, cmd_orders, cmd_shop, cmd_topcoins
from handlers.life import on_life_btn
from handlers.minigames import cmd_coin, cmd_dice, cmd_slots, on_game_btn
from handlers.moderation import cmd_admin, cmd_award, cmd_ban, cmd_mute, cmd_mutelist, cmd_question, cmd_quiz, cmd_stat, cmd_tag, cmd_topwords, cmd_unban, cmd_unmute, cmd_untag
from handlers.profiles import cmd_me, cmd_month, cmd_quests, cmd_quiztop, cmd_top, cmd_week
from handlers.ranks_admin import cmd_access, cmd_admins, cmd_demote, cmd_promote
from handlers.relations import on_rel_btn
from handlers.reports import cmd_report, on_report_btn
from handlers.router import on_text
from handlers.system import on_error, on_reaction_count
from scheduler import scheduler
from services.telegraph import telegraph_sync


try:
    from telegram.ext import MessageReactionHandler
except ImportError:  # старая версия библиотеки
    MessageReactionHandler = None

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ============================ ЗАПУСК ============================
async def post_init(app):
    me = await app.bot.get_me()
    print(f"Бот @{me.username} запущен")
    print(f"Основной чат: {CHAT_ID}" + (f", тестовый: {TEST_CHAT_ID}" if TEST_CHAT_ID else ""))
    oid = state_get("owner_id")
    print(f"Владелец: @{OWNER_USERNAME}" + (f" (id {oid})" if oid else
          " — id определится, когда он напишет в чат"))
    if MessageReactionHandler is None:
        print("! Старая версия библиотеки: «лучшее сообщение дня» не работает. "
              "Обнови: py -3.14 -m pip install -U python-telegram-bot")
    print("Бот должен быть АДМИНОМ чата (иначе он не видит реакции и не может мутить/банить).")
    try:
        url = await telegraph_sync()
        print(f"Статья с командами: {url}")
    except Exception as e:
        print("Статья в Telegraph не опубликована:", repr(e)[:200])

    # post_init вызывается до Application.start(). Запускаем небольшой
    # supervisor, который дождётся app.running и только затем включит scheduler.
    # Это совместимо с python-telegram-bot 22.x: у ApplicationBuilder нет post_start.
    app.bot_data["scheduler_supervisor"] = asyncio.create_task(
        _start_scheduler_when_running(app), name="scheduler-supervisor"
    )


async def _start_scheduler_when_running(app):
    try:
        while not app.running:
            await asyncio.sleep(0.1)
        task = asyncio.create_task(scheduler(app), name="bot-scheduler")
        app.bot_data["scheduler_task"] = task
        await task
    except asyncio.CancelledError:
        raise


async def post_stop(app):
    # Останавливаем и supervisor, и сам scheduler до закрытия event loop.
    for key in ("scheduler_task", "scheduler_supervisor"):
        task = app.bot_data.pop(key, None)
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


def main():
    token = (os.environ.get("BOT_TOKEN") or os.environ.get("TOKEN") or TOKEN).strip()
    if not token:
        p = os.path.join(BASE, "token.txt")
        if os.path.exists(p):
            token = open(p, encoding="utf-8").read().strip()
    if not token:
        print("Нет токена. Задай переменную окружения BOT_TOKEN или положи токен в файл token.txt рядом с ботом.")
        return
    app = (Application.builder().token(token).post_init(post_init)
           .post_stop(post_stop).build())
    for name, fn in (
        ("start", cmd_start), ("help", cmd_help), ("id", cmd_id), ("me", cmd_me),
        ("top", cmd_top), ("week", cmd_week), ("month", cmd_month),
        ("quiztop", cmd_quiztop), ("play", cmd_play), ("monopoly", cmd_monopoly), ("quests", cmd_quests), ("coin", cmd_coin),
        ("slots", cmd_slots), ("dice", cmd_dice), ("duel", cmd_duel),
        ("admin", cmd_admin), ("mute", cmd_mute), ("unmute", cmd_unmute),
        ("ban", cmd_ban), ("unban", cmd_unban), ("tag", cmd_tag), ("untag", cmd_untag),
        ("stat", cmd_stat), ("topwords", cmd_topwords), ("award", cmd_award),
        ("question", cmd_question), ("quiz", cmd_quiz),
        ("mutelist", cmd_mutelist), ("promote", cmd_promote), ("demote", cmd_demote),
        ("access", cmd_access), ("admins", cmd_admins),
        ("balance", cmd_balance), ("bonus", cmd_bonus), ("shop", cmd_shop), ("buy", cmd_buy),
        ("topcoins", cmd_topcoins), ("duels", cmd_duels), ("report", cmd_report),
        ("additem", cmd_item_add), ("delitem", cmd_item_del), ("givecoins", cmd_coins_give),
        ("orders", cmd_orders), ("done", cmd_order_done),
    ):
        app.add_handler(CommandHandler(name, fn))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_members))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.UpdateType.MESSAGE, on_text))
    if MessageReactionHandler is not None:
        app.add_handler(MessageReactionHandler(
            on_reaction_count,
            message_reaction_types=MessageReactionHandler.MESSAGE_REACTION_COUNT_UPDATED))
    app.add_handler(CallbackQueryHandler(on_report_btn, pattern=r"^rp:"))
    app.add_handler(CallbackQueryHandler(on_life_btn, pattern=r"^life:"))
    app.add_handler(CallbackQueryHandler(on_mono_btn, pattern=r"^mono:"))
    app.add_handler(CallbackQueryHandler(on_rel_btn, pattern=r"^rel:"))
    app.add_handler(CallbackQueryHandler(on_date_btn, pattern=r"^date:"))
    app.add_handler(CallbackQueryHandler(on_game_btn, pattern=r"^game:"))
    app.add_handler(CallbackQueryHandler(on_challenge_btn, pattern=r"^ch:"))
    app.add_handler(CallbackQueryHandler(on_gift_btn, pattern=r"^gift:"))
    app.add_error_handler(on_error)
    app.run_polling(allowed_updates=Update.ALL_TYPES)
