# -*- coding: utf-8 -*-
"""Монеты и цены."""

from config import SHOP_PRICE_MULT
from core.utils import urow
from database.db import db


# ============================ МОНЕТЫ, МАГАЗИН, ЖАЛОБЫ ============================
COIN = "🪙"


BONUS_BASE = 20


def give_coins(uid, n, commit=True):
    db.execute("UPDATE users SET coins=coins+? WHERE user_id=?", (n, uid))
    if commit:
        db.commit()


def coins_of(uid):
    r = urow(uid)
    return (r["coins"] or 0) if r else 0


def shop_price(it):
    return max(1, int(it["price"] * SHOP_PRICE_MULT))
