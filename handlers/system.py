# -*- coding: utf-8 -*-
"""Системные обработчики: реакции и ошибки."""

from telegram import Update
from telegram.error import NetworkError, TimedOut
from telegram.ext import ContextTypes

from config import CHAT_ID, TEST_CHAT_COUNTS, TEST_CHAT_ID
from core.logger import log
from core.utils import today, touch
from database.db import db


async def on_reaction_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rc = update.message_reaction_count
    if not rc or rc.chat.id != CHAT_ID:
        return
    total = sum(r.total_count for r in rc.reactions)
    db.execute("UPDATE msgs SET reactions=? WHERE message_id=?", (total, rc.message_id))
    db.commit()


async def on_any_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Считает ВСЕ сообщения участников (стикеры, фото, короткие, команды) для «топ дня/недели/месяца».
    Награды, опыт и квесты по-прежнему идут только за осмысленные сообщения (см. on_text)."""
    msg, user, chat = update.effective_message, update.effective_user, update.effective_chat
    if not msg or not user or user.is_bot or chat.type == "private":
        return
    if chat.id != CHAT_ID and not (TEST_CHAT_COUNTS and chat.id == TEST_CHAT_ID):
        return
    touch(user)
    db.execute("INSERT INTO daily(day,user_id,msgs_all) VALUES(?,?,1) "
               "ON CONFLICT(day,user_id) DO UPDATE SET msgs_all=msgs_all+1", (today(), user.id))
    db.commit()


async def on_error(update, context):
    if isinstance(context.error, (NetworkError, TimedOut)):
        # временный обрыв связи хостинга с Telegram: не ошибка кода, трейсбек не нужен
        log.warning("Сеть: %s: %s", type(context.error).__name__, context.error)
        return
    log.error("Ошибка: %s", context.error, exc_info=context.error)
