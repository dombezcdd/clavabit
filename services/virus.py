# -*- coding: utf-8 -*-
"""Вирус: «заразить», болезнь снижает зарплату, лечение в аптеке."""

import math
import random
import time

from core.utils import urow
from database.db import db

SICK_HOURS = 12
IMMUNE_HOURS = 6           # иммунитет после лечения
INFECT_CD = 3600           # пауза между попытками заразить, сек
INFECT_CHANCE = 0.55
SICK_PAY_MULT = 0.75      # болезнь забирает 25% зарплаты
CURE_PER_HOUR = 10
CURE_MIN = 20
BOOST_MIN = 10            # после лечения +5% к доходу на 10 минут
BOOST_PCT = 5


def is_sick(row):
    return bool(row) and (row["sick_until"] or 0) > time.time()


def has_boost(row):
    return bool(row) and (row["boost_until"] or 0) > time.time()


def is_immune(row):
    return bool(row) and (row["immune_until"] or 0) > time.time()


def cure_price(row):
    left_h = max(0.0, ((row["sick_until"] or 0) - time.time()) / 3600)
    return max(CURE_MIN, math.ceil(left_h) * CURE_PER_HOUR)


def try_infect(me_id, target_id):
    """-> (код, пояснение). коды: self, cd, already, immune, fail, ok"""
    if me_id == target_id:
        return "self", 0
    me = urow(me_id)
    left = (me["infect_at"] or 0) + INFECT_CD - time.time()
    if left > 0:
        return "cd", left
    t = urow(target_id)
    if not t:
        return "none", 0
    if is_sick(t):
        return "already", 0
    if is_immune(t):
        return "immune", (t["immune_until"] - time.time())
    db.execute("UPDATE users SET infect_at=? WHERE user_id=?", (time.time(), me_id))
    if random.random() > INFECT_CHANCE:
        db.commit()
        return "fail", 0
    db.execute("UPDATE users SET sick_until=? WHERE user_id=?", (time.time() + SICK_HOURS * 3600, target_id))
    db.commit()
    return "ok", 0


def cure(uid):
    db.execute("UPDATE users SET sick_until=0, immune_until=?, boost_until=? WHERE user_id=?",
               (time.time() + IMMUNE_HOURS * 3600, time.time() + BOOST_MIN * 60, uid))
    db.commit()
