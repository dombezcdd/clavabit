# -*- coding: utf-8 -*-
"""Кланы: казна, уровни, клановые войны (очки за активность)."""

import time

from core.utils import urow
from database.db import db

CLAN_CREATE_COST = 1000
CLAN_MAX = 15
CLAN_NAME_MAX = 16
LEVEL_STEP = 1000          # вклада в казну на уровень
LEVEL_MAX = 10             # уровень = +1% к зарплате участников
WAR_HOURS = 24
WAR_STAKE_DEFAULT = 200
WAR_PENDING_MIN = 60       # сколько ждём ответа на вызов
# очки войны
PTS_MSG, PTS_SHIFT, PTS_WIN = 1, 10, 15


def clan_level(xp):
    return min(LEVEL_MAX, 1 + (xp or 0) // LEVEL_STEP)


def get_clan(cid):
    return db.execute("SELECT * FROM clans WHERE id=?", (cid,)).fetchone() if cid else None


def clan_of(uid):
    r = urow(uid)
    return get_clan(r["clan_id"]) if r and r["clan_id"] else None


def find_clan(name):
    n = (name or "").strip().lower()
    for c in db.execute("SELECT * FROM clans").fetchall():
        if c["name"].lower() == n:
            return c
    return None


def members(cid):
    return db.execute("SELECT user_id,name FROM users WHERE clan_id=? ORDER BY total DESC", (cid,)).fetchall()


def clan_bonus_pct(uid):
    c = clan_of(uid)
    return clan_level(c["xp"]) if c else 0


def active_war(cid):
    return db.execute("SELECT * FROM wars WHERE (a=? OR b=?) AND status IN ('pending','active') "
                      "ORDER BY id DESC", (cid, cid)).fetchone()


def war_add(uid, n):
    """Очки клана в активной войне за действие участника."""
    try:
        r = urow(uid)
        if not r or not r["clan_id"]:
            return
        w = db.execute("SELECT * FROM wars WHERE status='active' AND end>? AND (a=? OR b=?)",
                       (time.time(), r["clan_id"], r["clan_id"])).fetchone()
        if not w:
            return
        col = "sa" if w["a"] == r["clan_id"] else "sb"
        db.execute(f"UPDATE wars SET {col}={col}+? WHERE id=?", (n, w["id"]))
        db.commit()
    except Exception:
        pass
