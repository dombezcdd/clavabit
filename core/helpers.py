# -*- coding: utf-8 -*-
"""Общие помощники хендлеров: group_only/owner_only, reply, поиск цели команды."""

import re
from types import SimpleNamespace

from telegram import Update
from telegram.ext import ContextTypes

from config import ALLOWED, CHAT_TAG, HTML, NOPREV
from core.utils import disp, esc, find_by_username, is_owner, touch, urow


# ============================ КОМАНДЫ ============================
def group_only(fn):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        if chat.type == "private":
            if fn.__name__ in ("cmd_start", "cmd_help", "cmd_id"):
                return await fn(update, context)
            return await update.effective_message.reply_text(
                f"Бот работает исключительно в чате {CHAT_TAG}")
        if chat.id not in ALLOWED:
            return
        if update.effective_user:
            touch(update.effective_user)
        return await fn(update, context)
    wrapper.__name__ = fn.__name__
    return wrapper


def owner_only(fn):
    async def wrapper(update, context):
        if not is_owner(update.effective_user):
            return
        return await fn(update, context)
    wrapper.__name__ = fn.__name__
    return group_only(wrapper)


async def reply(update, text, **kw):
    return await update.effective_message.reply_text(
        text, parse_mode=HTML, link_preview_options=NOPREV, **kw)


def why_no_target(update, usage):
    """Если команду дали ответом, но цель не определилась — объяснить почему."""
    m = update.effective_message
    r = m.reply_to_message if m else None
    if m and getattr(m, "external_reply", None):
        return ("Ты ответил на сообщение из другого чата (личного). Найди сообщение этого "
                "человека прямо в группе и ответь командой на него.")
    if r:
        if getattr(r, "sender_chat", None):
            return ("Это сообщение отправлено от имени канала или чата, а не участника — "
                    "применить команду нельзя.")
        if r.from_user and r.from_user.is_bot:
            return (f"Это сообщение от бота или анонимного админа ({esc(r.from_user.full_name)}) — "
                    "применить команду нельзя.")
        if not r.from_user:
            return "Не удалось определить автора этого сообщения (скрытый отправитель)."
    return usage


def reply_user(update):
    """Пользователь из ответа на сообщение (не бот)."""
    m = update.effective_message
    if m.reply_to_message and m.reply_to_message.from_user:
        u = m.reply_to_message.from_user
        if not u.is_bot:
            touch(u)
            return u
    return None


def target_user(update):
    """Цель: ответ на сообщение, иначе @юзернейм (или упоминание без юза) прямо в тексте."""
    u = reply_user(update)
    if u:
        return u
    m = update.effective_message
    if not m or not getattr(m, "text", None):
        return None
    for e in (getattr(m, "entities", None) or []):
        if getattr(e, "type", "") == "text_mention" and getattr(e, "user", None) and not e.user.is_bot:
            touch(e.user)
            return e.user
    for tok in re.findall(r"@([A-Za-z0-9_]{4,32})", m.text):
        r = find_by_username(tok)
        if r:
            return SimpleNamespace(id=r["user_id"], username=r["username"], is_bot=False,
                                   full_name=r["name"] or tok)
    return None


def resolve_target(update, args):
    """Цель: ответ на сообщение, иначе @юзернейм / id из аргументов.
    -> (uid, имя, оставшиеся аргументы, текст ошибки)"""
    u = reply_user(update)
    if u:
        return u.id, disp(u), args, None
    uid = name = None
    rest = []
    for a in args:
        if uid is None and a.startswith("@"):
            r = find_by_username(a)
            if not r:
                return None, None, args, (
                    f"Не нашёл {esc(a)}: человек должен хотя бы раз написать в чат при "
                    f"запущенном боте. Можно ответить командой на его сообщение.")
            uid, name = r["user_id"], r["name"]
            continue
        if uid is None and a.isdigit() and len(a) > 6:
            r = urow(int(a))
            uid, name = int(a), (r["name"] if r else a)
            continue
        rest.append(a)
    if uid is None:
        return None, None, args, None
    return uid, name, rest, None
