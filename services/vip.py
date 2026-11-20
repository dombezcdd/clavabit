# -*- coding: utf-8 -*-
"""VIP-статус и донатная валюта «звёздики»."""

import time

from database.db import db
from core.utils import urow

STAR = "⭐"
STARS_NAME = "звёздиков"
VIP_PRICE = 25            # звёздиков за 30 дней
VIP_DAYS = 30
VIP_REL_MULT = 1.25       # +25% искр в отношениях
VIP_CD_MULT = 0.9         # пауза между сменами на 10% короче
VIP_CASINO_BONUS = 750    # ежедневный бонус фишек (обычный 500)
VIP_QUEST_XP = 60         # опыт за каждый VIP-квест


def stars_of(uid):
    r = urow(uid)
    return (r["stars"] or 0) if r else 0


def stars_add(uid, n):
    db.execute("UPDATE users SET stars=MAX(0, COALESCE(stars,0)+?) WHERE user_id=?", (n, uid))
    db.commit()


def vip_until(uid):
    r = urow(uid)
    return (r["vip_until"] or 0) if r else 0


def is_vip(uid):
    try:
        return vip_until(uid) > time.time()
    except Exception:
        return False


def vip_left_text(uid):
    left = vip_until(uid) - time.time()
    if left <= 0:
        return ""
    d, h = int(left // 86400), int(left % 86400 // 3600)
    return f"{d} дн. {h} ч." if d else f"{h} ч."


def buy_vip(payer, target):
    """Платит payer, VIP получает target. -> (ok, текст ошибки или '')"""
    if stars_of(payer) < VIP_PRICE:
        return False, f"Не хватает звёздиков: нужно {VIP_PRICE}, у тебя {stars_of(payer)}"
    if not urow(target):
        return False, "Этого человека нет в базе бота"
    base = max(vip_until(target), time.time())
    db.execute("UPDATE users SET stars=stars-? WHERE user_id=?", (VIP_PRICE, payer))
    db.execute("UPDATE users SET vip_until=? WHERE user_id=?", (base + VIP_DAYS * 86400, target))
    db.commit()
    return True, ""
