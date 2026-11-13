# -*- coding: utf-8 -*-
"""Системные обработчики: реакции и ошибки."""

from telegram import Update
from telegram.ext import ContextTypes

from config import CHAT_ID
from core.logger import log
from database.db import db


async def on_reaction_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rc = update.message_reaction_count
    if not rc or rc.chat.id != CHAT_ID:
        return
    total = sum(r.total_count for r in rc.reactions)
    db.execute("UPDATE msgs SET reactions=? WHERE message_id=?", (total, rc.message_id))
    db.commit()


async def on_error(update, context):
    log.error("Ошибка: %s", context.error, exc_info=context.error)
