# -*- coding: utf-8 -*-
"""Ранги админов, права на команды, декоратор need, журнал админ-действий."""

import time

from core.helpers import group_only, reply_user
from core.logger import log
from core.utils import disp, is_owner
from database.db import db
from database.state import state_get


# ---------- ранги админов и права на команды ----------
# с какого ранга доступна команда (меняется: «дк мут 2»). Владелец всегда 8.
DEFAULT_RANKS = {
    "админка": 1, "админы": 1, "мут": 1, "размут": 1, "список мута": 1,
    "бан": 2, "разбан": 2, "статистика": 2, "слова дня": 2,
    "тег": 3, "снять тег": 3,
    "итоги": 4, "запустить вопрос": 4, "запустить викторину": 4,
    "добавить картинку": 2, "список картинок": 1, "очистить картинки": 3,
    "добавить товар": 4, "удалить товар": 4, "выдать монеты": 5, "заказы": 2, "выдан": 2,
    "добавить работу": 5, "удалить работу": 5, "список работ": 2, "журнал": 3,
    "установить приветствие": 3, "установить правила": 3, "статистика недели": 2,
    "статья команд": 6,
}


ADMIN_TITLES = {
    1: "Мл. модератор", 2: "Старший модератор", 3: "Главный модератор",
    4: "Стажер админ", 5: "Младший админ", 6: "Старший админ",
    7: "Зам.Администрации", 8: "Доверенное лицо",
}


def rank_title(n):
    return ADMIN_TITLES.get(n, "")


FIXED_8 = {"повысить", "дк"}          # только админ 8 ранга


MAX_RANK = 8


def rank_of_id(uid):
    oid = state_get("owner_id")
    if oid and str(uid) == oid:
        return MAX_RANK
    r = db.execute("SELECT arank FROM users WHERE user_id=?", (uid,)).fetchone()
    return (r["arank"] or 0) if r else 0


def rank_of(user):
    if not user:
        return 0
    if is_owner(user):
        return MAX_RANK
    return rank_of_id(user.id)


def required_rank(key):
    if key in FIXED_8:
        return MAX_RANK
    r = db.execute("SELECT rank FROM cmd_access WHERE cmd=?", (key,)).fetchone()
    return r["rank"] if r else DEFAULT_RANKS.get(key, MAX_RANK)


def has_rank(user, key):
    return rank_of(user) >= required_rank(key)


def can_act_on(actor, target_id):
    """Нельзя трогать тех, чей ранг не ниже твоего (владелец может всех)."""
    if is_owner(actor):
        return True
    return rank_of(actor) > rank_of_id(target_id)


def need(key):
    def deco(fn):
        async def wrapper(update, context):
            if not has_rank(update.effective_user, key):
                return
            if key not in LOG_SKIP:
                log_admin(update, key)
            return await fn(update, context)
        wrapper.__name__ = fn.__name__
        return group_only(wrapper)
    return deco


# ---------- админка: журнал, приветствие, правила, статистика недели ----------
LOG_SKIP = {"список мута", "список картинок", "админка", "админы", "заказы", "журнал", "статистика",
            "слова дня", "статистика недели", "список работ", "дк"}


def log_admin(update, key):
    try:
        u, m = update.effective_user, update.effective_message
        txt = (m.text or "")[:200]
        t = reply_user(update)
        if t:
            txt += f"  [→ {disp(t)}]"
        db.execute("INSERT INTO admin_log(ts,actor,actor_name,cmd,text) VALUES(?,?,?,?,?)",
                   (time.time(), u.id, disp(u), key, txt))
        db.execute("DELETE FROM admin_log WHERE id < (SELECT MAX(id) FROM admin_log) - 500")
        db.commit()
    except Exception:
        log.exception("admin log")
