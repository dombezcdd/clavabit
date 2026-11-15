# -*- coding: utf-8 -*-
"""Налоги, бизнес и биржа акций (вымышленные компании)."""

import math
import random
import time

from core.utils import today, urow
from database.db import db
from database.state import state_get, state_set

# ---------- налоги и лимит на подарки ----------
SALARY_TAX = 0.05          # налог на зарплату
GIFT_VAT = 0.12            # НДС после покупки подарка: на время паузы зарплата ещё меньше
GIFT_PAUSE_H = 48          # после покупки подарка новые покупать нельзя столько часов


def gift_left(row):
    """Секунд до конца паузы после покупки подарка (0 если можно покупать)."""
    return max(0, int((row["gift_until"] or 0) - time.time())) if row else 0


def tax_rate(row):
    return SALARY_TAX + (GIFT_VAT if gift_left(row) > 0 else 0)


def mark_gift_bought(uid):
    db.execute("UPDATE users SET gift_until=? WHERE user_id=?", (time.time() + GIFT_PAUSE_H * 3600, uid))


# ---------- бизнес ----------
BIZ = [   # (название, цена, доход в час)
    ("Ларёк", 600, 5),
    ("Магазин", 1800, 15),
    ("Кафе", 5000, 42),
    ("Фабрика", 14000, 120),
    ("Завод", 40000, 350),
]
BIZ_CAP_H = 24             # доход копится не дольше стольких часов
BIZ_EVENTS = (             # (шанс, множитель дохода, текст)
    (0.10, 0.8, "🕵 Налоговая проверка: штраф 20% дохода"),
    (0.07, 0.5, "🔧 Поломка оборудования: доход вдвое меньше"),
    (0.08, 1.3, "🎉 Удачный день: доход +30%"),
)


def biz_of(uid):
    return db.execute("SELECT * FROM business WHERE user_id=?", (uid,)).fetchone()


def biz_accrued(b):
    hours = min(BIZ_CAP_H, max(0.0, (time.time() - b["last_collect"]) / 3600))
    return int(BIZ[b["level"] - 1][2] * hours), hours


def biz_upgrade_cost(level):
    return BIZ[level][1] - BIZ[level - 1][1] // 2


def biz_roll_event(income):
    r = random.random()
    acc = 0.0
    for p, mult, txt in BIZ_EVENTS:
        acc += p
        if r < acc:
            return max(0, int(income * mult)), txt
    return income, ""


# ---------- биржа ----------
STOCKS = [   # (тикер, название, базовая цена, волатильность за тик, чувствительность к активности чата)
    ("КЛВ", "Клава Банк", 100, 0.035, 0.5),
    ("МШК", "Мишка Тойс", 60, 0.050, 0.8),
    ("ВИР", "ВирусФарм", 80, 0.060, 0.0),
    ("ЧАТ", "ЧатМедиа", 120, 0.045, 1.5),
    ("ДОМ", "ДомСтрой", 150, 0.030, 0.3),
]
STOCK_TICK_SEC = 1800
STOCK_FEE = 0.03           # комиссия при продаже
STOCK_DAY_LIMIT = 1500     # сколько славКоинов можно вложить в акции за сутки
STOCK_MAX_QTY = 100        # максимум акций одной компании у игрока
STOCK_ALERT = 0.08         # изменение за тик, после которого в чат приходит картинка
HIST_KEEP = 48


def init_stocks():
    for sym, name, base, vol, sens in STOCKS:
        if not db.execute("SELECT 1 FROM stocks WHERE sym=?", (sym,)).fetchone():
            db.execute("INSERT INTO stocks(sym,name,price,prev,base,vol,sens,updated) VALUES(?,?,?,?,?,?,?,?)",
                       (sym, name, base, base, base, vol, sens, time.time()))
            db.execute("INSERT INTO stock_hist(sym,ts,price) VALUES(?,?,?)", (sym, time.time(), base))
    db.commit()


def find_stock(q):
    q = (q or "").strip().lower()
    if not q:
        return None
    for s in db.execute("SELECT * FROM stocks").fetchall():
        if s["sym"].lower() == q or s["name"].lower().startswith(q) or s["name"].lower().replace(" ", "") == q:
            return s
    return None


def history(sym, n=HIST_KEEP):
    rows = db.execute("SELECT price FROM stock_hist WHERE sym=? ORDER BY ts DESC LIMIT ?", (sym, n)).fetchall()
    return [r["price"] for r in reversed(rows)]


def _activity_bias():
    """+/- от активности чата за последние полчаса относительно обычной."""
    total = db.execute("SELECT COALESCE(SUM(total),0) FROM users").fetchone()[0]
    last = float(state_get("stk_total") or total)
    avg = float(state_get("stk_avg") or 0)
    delta = max(0, total - last)
    state_set("stk_total", str(total))
    bias = 0.0
    if avg > 0:
        bias = max(-1.0, min(1.0, (delta - avg) / (avg + 10)))
    state_set("stk_avg", str(delta if avg == 0 else avg * 0.8 + delta * 0.2))
    return bias


def tick_prices(force=False):
    """Раз в 30 минут двигает цены. Возвращает список (акция, старая цена, новая цена)."""
    last = float(state_get("stk_tick") or 0)
    if not force and time.time() - last < STOCK_TICK_SEC:
        return []
    state_set("stk_tick", str(time.time()))
    act = _activity_bias()
    sick = db.execute("SELECT COUNT(*) FROM users WHERE sick_until>?", (time.time(),)).fetchone()[0]
    out = []
    for s in db.execute("SELECT * FROM stocks").fetchall():
        ch = random.gauss(0, s["vol"]) + 0.04 * (s["base"] - s["price"]) / s["base"] + act * 0.02 * s["sens"]
        if s["sym"] == "ВИР":
            ch += min(sick, 10) * 0.004
        ch = max(-0.12, min(0.12, ch))
        new = round(min(s["base"] * 3, max(s["base"] * 0.4, s["price"] * (1 + ch))), 2)
        db.execute("UPDATE stocks SET prev=?, price=?, updated=? WHERE sym=?", (s["price"], new, time.time(), s["sym"]))
        db.execute("INSERT INTO stock_hist(sym,ts,price) VALUES(?,?,?)", (s["sym"], time.time(), new))
        db.execute("DELETE FROM stock_hist WHERE sym=? AND ts NOT IN "
                   "(SELECT ts FROM stock_hist WHERE sym=? ORDER BY ts DESC LIMIT ?)", (s["sym"], s["sym"], HIST_KEEP))
        out.append((s, s["price"], new))
    db.commit()
    return out


def spent_today(uid):
    r = db.execute("SELECT spent FROM stock_day WHERE user_id=? AND day=?", (uid, today())).fetchone()
    return r["spent"] if r else 0


def holding(uid, sym):
    return db.execute("SELECT * FROM holdings WHERE user_id=? AND sym=?", (uid, sym)).fetchone()


def buy_stock(uid, s, qty):
    """-> (ok, текст ошибки или стоимость)"""
    cost = math.ceil(s["price"] * qty)
    row = urow(uid)
    h = holding(uid, s["sym"])
    have = h["qty"] if h else 0
    if qty < 1:
        return False, "Количество должно быть больше нуля"
    if have + qty > STOCK_MAX_QTY:
        return False, f"Максимум {STOCK_MAX_QTY} акций одной компании (у тебя {have})"
    if spent_today(uid) + cost > STOCK_DAY_LIMIT:
        return False, f"Лимит вложений в сутки: {STOCK_DAY_LIMIT} (сегодня уже {spent_today(uid)})"
    if (row["coins"] or 0) < cost:
        return False, f"Не хватает: нужно {cost}, у тебя {row['coins'] or 0}"
    db.execute("UPDATE users SET coins=coins-? WHERE user_id=?", (cost, uid))
    db.execute("INSERT INTO holdings(user_id,sym,qty,cost) VALUES(?,?,?,?) "
               "ON CONFLICT(user_id,sym) DO UPDATE SET qty=qty+?, cost=cost+?", (uid, s["sym"], qty, cost, qty, cost))
    db.execute("INSERT INTO stock_day(user_id,day,spent) VALUES(?,?,?) "
               "ON CONFLICT(user_id,day) DO UPDATE SET spent=spent+?", (uid, today(), cost, cost))
    db.commit()
    return True, cost


def sell_stock(uid, s, qty):
    """-> (ok, (выручка после комиссии, прибыль, комиссия) или ошибка)"""
    h = holding(uid, s["sym"])
    if not h or h["qty"] < 1:
        return False, "У тебя нет акций этой компании"
    qty = min(qty, h["qty"])
    gross = int(s["price"] * qty)
    fee = int(gross * STOCK_FEE)
    net = gross - fee
    part_cost = h["cost"] * qty // h["qty"]
    profit = net - part_cost
    db.execute("UPDATE users SET coins=coins+? WHERE user_id=?", (net, uid))
    if qty == h["qty"]:
        db.execute("DELETE FROM holdings WHERE user_id=? AND sym=?", (uid, s["sym"]))
    else:
        db.execute("UPDATE holdings SET qty=qty-?, cost=cost-? WHERE user_id=? AND sym=?", (qty, part_cost, uid, s["sym"]))
    db.execute("INSERT INTO investors(user_id,profit) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET profit=profit+?",
               (uid, profit, profit))
    db.commit()
    return True, (net, profit, fee, qty)
