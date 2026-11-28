# -*- coding: utf-8 -*-
"""Тяжёлые дни: в «чёрный день» зарплата вдвое меньше, если не поел или не поспал."""

import zlib

from core.utils import today
from database.db import db

HEAVY_PCT = 12          # шанс чёрного дня (примерно раз в 8 дней)
HEAVY_MULT = 0.5
FOOD = {                # ключ: (название, цена, где)
    "бутерброд": ("🥪 Бутерброд", 3, "магазин"),
    "шаурма": ("🌯 Шаурма", 6, "кафе"),
    "стейк": ("🥩 Стейк", 15, "ресторан"),
}


def _init():
    db.execute("CREATE TABLE IF NOT EXISTS life_needs(user_id INTEGER, day TEXT, fed INTEGER DEFAULT 0, "
               "slept INTEGER DEFAULT 0, PRIMARY KEY(user_id, day))")


def state(uid):
    _init()
    r = db.execute("SELECT fed, slept FROM life_needs WHERE user_id=? AND day=?", (uid, today())).fetchone()
    return (bool(r["fed"]), bool(r["slept"])) if r else (False, False)


def mark(uid, field):
    _init()
    db.execute("INSERT OR IGNORE INTO life_needs(user_id, day) VALUES(?,?)", (uid, today()))
    db.execute(f"UPDATE life_needs SET {field}=1 WHERE user_id=? AND day=?", (uid, today()))
    db.commit()


def is_heavy(uid):
    return zlib.crc32(f"{uid}:{today()}".encode()) % 100 < HEAVY_PCT


def missing(uid):
    fed, slept = state(uid)
    return [n for n, ok in (("поесть", fed), ("поспать", slept)) if not ok]


def heavy_mult(uid):
    return HEAVY_MULT if is_heavy(uid) and missing(uid) else 1.0
