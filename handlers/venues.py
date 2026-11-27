# -*- coding: utf-8 -*-
"""Своё заведение за славБакс: «открыть кофейню», «открыть ресторан», «моё заведение», «собрать выручку»."""

import time

from config import ALLOWED
from core.helpers import reply
from core.utils import touch
from database.db import db
from services.casino import chips_add, chips_of

VENUES = {"кофейня": ("☕ Кофейня", 2000, 25), "ресторан": ("🍽 Ресторан", 6000, 85)}   # название, цена, доход/час
CAP_H = 24
CMDS = {"открыть кофейню": "кофейня", "открыть ресторан": "ресторан", "построить кофейню": "кофейня",
        "построить ресторан": "ресторан"}


def _init():
    db.execute("CREATE TABLE IF NOT EXISTS venue(user_id INTEGER PRIMARY KEY, kind TEXT, last_collect REAL)")


def _mine(uid):
    _init()
    return db.execute("SELECT * FROM venue WHERE user_id=?", (uid,)).fetchone()


def _acc(v):
    hours = min(CAP_H, max(0.0, (time.time() - v["last_collect"]) / 3600))
    return int(VENUES[v["kind"]][2] * hours)


async def handle_venue_text(update, context, low, text):
    low = low.strip()
    if low not in CMDS and low not in ("моё заведение", "мое заведение", "заведения", "собрать выручку"):
        return False
    if update.effective_chat.id not in ALLOWED:
        return False
    me = update.effective_user
    touch(me)
    v = _mine(me.id)
    if low in CMDS:
        k = CMDS[low]
        name, price, inc = VENUES[k]
        if v:
            await reply(update, f"У тебя уже есть {VENUES[v['kind']][0]}. Одно заведение на человека.")
        elif chips_of(me.id) < price:
            await reply(update, f"{name}: {price} 💵 славБакс, у тебя {chips_of(me.id)}. Играй в «казино» 🎰")
        else:
            chips_add(me.id, -price)
            db.execute("INSERT INTO venue(user_id, kind, last_collect) VALUES(?,?,?)", (me.id, k, time.time()))
            db.commit()
            await reply(update, f"🎉 Открыто: <b>{name}</b>! Доход {inc} 💵 в час (копится до {CAP_H} ч). Забрать: «собрать выручку»")
    elif not v:
        await reply(update, "Своего заведения нет. Открой: «открыть кофейню» (2000 💵 славБакс) или «открыть ресторан» (6000 💵)")
    elif low == "собрать выручку":
        n = _acc(v)
        if n < 1:
            await reply(update, "Выручки пока нет, зайди позже ⏳")
        else:
            chips_add(me.id, n)
            db.execute("UPDATE venue SET last_collect=? WHERE user_id=?", (time.time(), me.id))
            db.commit()
            await reply(update, f"💵 Выручка {VENUES[v['kind']][0]}: +{n} славБакс. Баланс {chips_of(me.id)}")
    else:
        n = _acc(v)
        await reply(update, f"{VENUES[v['kind']][0]}: доход {VENUES[v['kind']][2]} 💵/ч, накопилось {n}. «собрать выручку»")
    return True
