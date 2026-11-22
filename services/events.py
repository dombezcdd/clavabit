# -*- coding: utf-8 -*-
"""События часа от владельца: двойной опыт, повышенная зарплата, скидки в магазине."""

import time

from database.state import state_get, state_set

KINDS = {
    "опыт": ("xp", "✨ Двойной опыт"),
    "зарплата": ("pay", "💼 Зарплата +50%"),
    "скидка": ("shop", "🛍 Скидка 20% в магазине"),
}


def ev_set(key, minutes):
    state_set("ev_" + key, time.time() + minutes * 60)


def ev_left(key):
    try:
        return max(0, float(state_get("ev_" + key) or 0) - time.time())
    except Exception:
        return 0


def ev_on(key):
    return ev_left(key) > 0
