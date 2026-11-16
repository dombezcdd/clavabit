# -*- coding: utf-8 -*-
"""Казино: чистая логика игр. Шансы нарочно в пользу казино."""

import random

MIN_BET, MAX_BET = 5, 100
DAY_LOSS_LIMIT = 300         # больше этого за сутки проиграть нельзя
COOLDOWN = 3                 # секунд между ставками

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
