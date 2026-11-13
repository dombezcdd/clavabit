# -*- coding: utf-8 -*-
"""Работа, карьера, дома и питомцы: данные и расчёты."""

import json
import random
import time

from config import JOB_PAY_MULT
from core.utils import level_of, link, urow
from database.db import db
from services.relations import is_married, pair_of, partner_of


# ============================ ЖИЗНЬ: РАБОТЫ, БРАК, ДОМА, ПИТОМЦЫ ============================
# Все цифры тут: меняй под свой чат.
JOBS = {   # ключ: (название, награда (масштаб искр паре), пауза между сменами в часах, требования)
    "курьер":      ("Курьер", 20, 2, {}),
    "уборщик":     ("Уборщик", 25, 2, {}),
    "продавец":    ("Продавец", 35, 3, {"days": 2}),
    "официант":    ("Официант", 50, 3, {"level": 3}),
    "таксист":     ("Таксист", 70, 4, {"msgs": 300}),
    "программист": ("Программист", 120, 4, {"level": 8, "days": 7}),
    "врач":        ("Врач", 160, 6, {"level": 15, "days": 14}),
    "пилот":       ("Пилот", 220, 6, {"level": 25, "msgs": 2000}),
    "директор":    ("Директор", 400, 8, {"level": 40, "days": 30}),
}


HOUSES = {  # ключ: (название, цена, бонус к зарплате %, ссылка для кнопки «Посмотреть» или "")
    "комната":  ("Комната", 300, 5, ""),
    "квартира": ("Квартира", 1000, 10, ""),
    "дом":      ("Дом", 3000, 20, ""),
    "особняк":  ("Особняк", 10000, 35, ""),
}


PETS = {  # ключ: (название, цена, эмодзи)
    "кот": ("Кот", 150, "🐱"), "собака": ("Собака", 200, "🐶"), "хомяк": ("Хомяк", 80, "🐹"),
    "попугай": ("Попугай", 250, "🦜"), "кролик": ("Кролик", 180, "🐰"), "лиса": ("Лиса", 600, "🦊"),
}


PET_FEED_COST, PET_MAX, PET_RUNAWAY_DAYS = 3, 3, 5


def days_in_chat(row):
    return int((time.time() - (row["first_seen"] or time.time())) // 86400)


def job_missing(row, req):
    """-> список невыполненных условий (пусто, если работа доступна)"""
    out = []
    if row_level(row) < req.get("level", 0):
        out.append(f"уровень {req['level']}")
    if days_in_chat(row) < req.get("days", 0):
        out.append(f"{req['days']} дн. в чате")
    if (row["total"] or 0) < req.get("msgs", 0):
        out.append(f"{req['msgs']} сообщений")
    return out


def row_level(row):
    return level_of(row["xp"] or 0)


def house_bonus_pct(uid):
    """бонус дома: свой или дом супруга (берём лучший)"""
    best = 0
    ids = [uid]
    p = pair_of(uid)
    if p and (p["married_at"] or 0):
        ids.append(partner_of(p, uid))
    for i in ids:
        r = urow(i)
        if r and r["house"] in HOUSES:
            best = max(best, HOUSES[r["house"]][2])
    return best


def shown_pay(base):
    return max(1, int(base * JOB_PAY_MULT))


def job_pay(row):
    name, base, cd, req = JOBS[row["job"]]
    mult = 1 + min(row["job_shifts"] or 0, 100) / 200 + house_bonus_pct(row["user_id"]) / 100
    return max(1, int(base * mult * JOB_PAY_MULT))


JOB_GIF = {"курьер": "delivery courier", "уборщик": "cleaning mop", "продавец": "cashier store",
           "официант": "waiter serving food", "таксист": "taxi driving", "программист": "programming computer",
           "врач": "doctor hospital", "пилот": "airplane pilot cockpit", "директор": "boss office"}


TASK_MIN = 10          # минут на выполнение


DELIVER = {            # работа -> (текст задания, слово-ответ, куда/кому)
    "курьер": ("📦 <b>Заказ #{n}</b>\nОтдайте заказ {t}", "отдать заказ"),
    "официант": ("🍽 <b>Столик #{n}</b>\nОтнесите блюда клиенту {t}", "принести заказ"),
    "таксист": ("🚕 <b>Вызов #{n}</b>\nПассажир {t} ждёт такси. Адрес: {place}", "довезти"),
    "врач": ("🩺 <b>Приём #{n}</b>\nНа осмотр пришёл {t}. Жалобы: {place}", "осмотреть"),
}


PLACES_TAXI = ["вокзал", "аэропорт", "торговый центр", "университет", "парк", "набережная"]


PLACES_DOC = ["болит голова", "кашель", "температура", "болит горло", "слабость", "насморк"]


WORDS = ["пылесос", "швабра", "ведро", "тряпка", "веник", "мусор", "метла", "порошок", "губка"]


MATH_FLAVOR = {"продавец": "🛒 <b>Касса.</b> Пробейте чек: {q}", "программист": "💻 <b>Баг #{n}.</b> Найдите ответ: {q}",
               "пилот": "✈️ <b>Расчёт топлива.</b> {q}", "директор": "📊 <b>Смета.</b> Подпишите, посчитав: {q}"}


def _math_task(job):
    r = random
    if job == "продавец":
        a, b, c = r.randint(20, 200), r.randint(10, 90), r.randint(5, 60)
        return f"{a} + {b} + {c} = ?", a + b + c
    if job == "программист":
        x, y, z = r.randint(6, 19), r.randint(3, 9), r.randint(1, 30)
        return f"{x} × {y} − {z} = ?", x * y - z
    if job == "пилот":
        c, k, d = r.randint(3, 9), r.randint(10, 40), r.randint(5, 50)
        return f"{c * k} ÷ {c} + {d} = ?", k + d
    x, y, z = r.randint(12, 40), r.randint(11, 30), r.randint(100, 900)
    return f"{x} × {y} + {z} = ?", x * y + z


def tag_user(row):
    return "@" + row["username"] if row["username"] else link(row["user_id"], row["name"])


def open_task(uid):
    return db.execute("SELECT * FROM job_tasks WHERE user_id=?", (uid,)).fetchone()


# ---------- питомцы ----------
def my_pets(uid):
    ids = [uid]
    p = pair_of(uid)
    if p and is_married(p):
        ids.append(partner_of(p, uid))
    return db.execute(f"SELECT * FROM pets WHERE owner IN ({','.join('?' * len(ids))})", ids).fetchall()


BUILTIN_JOBS = set(JOBS)


def load_custom_jobs():
    for r in db.execute("SELECT * FROM custom_jobs").fetchall():
        try:
            req = json.loads(r["req"] or "{}")
        except Exception:
            req = {}
        JOBS[r["key"]] = (r["name"], r["pay"], r["cd"], req)


# ---------- карьера: должность растёт со сменами ----------
CAREER = [(0, "Стажёр"), (10, "Специалист"), (30, "Старший"), (70, "Эксперт"), (150, "Мастер")]


def career_title(shifts):
    t = CAREER[0][1]
    for n, name in CAREER:
        if shifts >= n:
            t = name
    return t


def career_next(shifts):
    return next(((n, nm) for n, nm in CAREER if n > shifts), None)
