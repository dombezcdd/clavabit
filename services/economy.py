# -*- coding: utf-8 -*-
"""Монеты и цены."""

from config import SHOP_PRICE_MULT
from core.utils import urow
from database.db import db


# ============================ МОНЕТЫ, МАГАЗИН, ЖАЛОБЫ ============================
COIN = "славКоин"


BONUS_BASE = 20


def give_coins(uid, n, commit=True):
    db.execute("UPDATE users SET coins=coins+? WHERE user_id=?", (n, uid))
    if commit:
        db.commit()


def coins_of(uid):
    r = urow(uid)
    return (r["coins"] or 0) if r else 0


SHOP_EXTRA = 15      # надбавка к цене каждого подарка в магазине


def shop_price(it):
    mult = SHOP_PRICE_MULT
    try:
        from services.events import ev_on
        if ev_on("shop"):
            mult *= 0.8
    except Exception:
        pass
    return max(1, int(it["price"] * mult)) + SHOP_EXTRA
