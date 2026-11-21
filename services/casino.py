# -*- coding: utf-8 -*-
"""Казино: чистая логика игр. Шансы нарочно в пользу казино."""

import random

from database.db import db


def chips_of(uid):
    r = db.execute("SELECT chips FROM casino WHERE user_id=?", (uid,)).fetchone()
    if r is None:
        db.execute("INSERT INTO casino(user_id,chips,best) VALUES(?,?,?)", (uid, START_CHIPS, START_CHIPS))
        db.commit()
        return START_CHIPS
    return r["chips"]


def chips_add(uid, n, name=None):
    chips_of(uid)
    db.execute("UPDATE casino SET chips=chips+?, best=MAX(best, chips+?)" + (", name=?" if name else "") +
               " WHERE user_id=?", (n, n) + ((name,) if name else ()) + (uid,))
    db.commit()


def claim_bonus(uid, day):
    """-> сумма бонуса или 0, если сегодня уже брали"""
    chips_of(uid)
    r = db.execute("SELECT bonus_day FROM casino WHERE user_id=?", (uid,)).fetchone()
    if r["bonus_day"] == day:
        return 0
    db.execute("UPDATE casino SET bonus_day=? WHERE user_id=?", (day, uid))
    db.commit()
    from services.vip import VIP_CASINO_BONUS, is_vip
    amt = VIP_CASINO_BONUS if is_vip(uid) else DAILY_BONUS
    chips_add(uid, amt)
    return amt


def top_chips(n=10):
    return db.execute("SELECT user_id,name,chips FROM casino ORDER BY chips DESC LIMIT ?", (n,)).fetchall()

CHIP = "🪙 фишек"
MIN_BET, MAX_BET = 10, 1000
START_CHIPS = 1000           # стартовый баланс
DAILY_BONUS = 500            # бонус раз в сутки
COOLDOWN = 10                # секунд между ставками (пока крутится барабан)

SLOT_W = {"🍒": 6, "🍋": 5, "🔔": 4, "💎": 2, "7️⃣": 1}
SLOT_PAY = {"🍒": 5, "🍋": 8, "🔔": 15, "💎": 50, "7️⃣": 200}   # три одинаковых: множитель ставки
TWO_CHERRY = 1                                                  # ровно две вишни: ставка возвращается
COIN_P = 0.45                                                   # шанс монетки, выплата x2
REDS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
WHEEL = list(range(37)) + ["00"]                                # два зеро


def spin_slots():
    syms = list(SLOT_W)
    reels = random.choices(syms, weights=[SLOT_W[s] for s in syms], k=3)
    if len(set(reels)) == 1:
        return reels, SLOT_PAY[reels[0]]
    if reels.count("🍒") == 2:
        return reels, TWO_CHERRY
    return reels, 0


def flip(side):
    """side: 'орёл'|'решка' -> (выпало, множитель)"""
    win = random.random() < COIN_P
    other = "решка" if side == "орёл" else "орёл"
    return (side if win else other), (2 if win else 0)


def color_of(n):
    if n in (0, "00"):
        return "зелёное"
    return "красное" if n in REDS else "чёрное"


def roulette(kind, number=None):
    """kind: красное|чёрное|чётное|нечётное|число -> (выпало, цвет, множитель)"""
    n = random.choice(WHEEL)
    col = color_of(n)
    mult = 0
    if kind in ("красное", "чёрное"):
        mult = 2 if col == kind else 0
    elif kind in ("чётное", "нечётное") and n not in (0, "00"):
        mult = 2 if (n % 2 == 0) == (kind == "чётное") else 0
    elif kind == "число":
        mult = 35 if str(n) == str(number) else 0
    return n, col, mult


def rtp_slots():
    tot = sum(SLOT_W.values())
    r = sum(((SLOT_W[s] / tot) ** 3) * SLOT_PAY[s] for s in SLOT_W)
    p2 = 3 * (SLOT_W["🍒"] / tot) ** 2 * (1 - SLOT_W["🍒"] / tot)
    return r + p2 * TWO_CHERRY
