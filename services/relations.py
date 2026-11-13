# -*- coding: utf-8 -*-
"""Отношения и искры: константы, словари слов, логика пар."""

import time

from core.utils import today, urow
from database.db import db
from database.state import state_get, state_set


# ============================ ОТНОШЕНИЯ (искры) ============================
REL_START, REL_DAILY_CAP, REL_DATE_GAIN = 100, 300, 80     # искры: старт, лимит в сутки с действий, свидание


REL_ASK_SEC = 120                                           # сколько живёт предложение (2 минуты)


SPARK_RATE = 2                                              # 1 монета = 2 искры


KID_COST, KIDS_MAX = 300, 4


REL_TIME = (10, 15)            # когда раз в день списывать содержание


LEVELS = [(0, "Первые искры"), (300, "Тёплые чувства"), (800, "Крепкая связь"), (1500, "Горячая любовь"),
          (2500, "Родные души"), (4000, "Вместе навсегда"), (6000, "Пара мечты"), (9000, "Легенда чата")]


REL_GAIN = {"поцеловать": 50, "обнять": 30, "обнять крепко": 40, "взять за руку": 25,
            "погладить": 20, "покормить": 15, "пощекотать": 15, "похвалить": 15, "помахать": 5}


REL_PIC = {"поцеловать": "поцелуй", "обнять": "объятие", "обнять крепко": "объятие"}


REL_EVENTS = {
    "предложение": "кто-то предложил отношения",
    "пара": "предложение принято, пара создана",
    "поцелуй": "партнёры целуются (команда «поцеловать»)",
    "объятие": "партнёры обнимаются (команды «обнять»)",
    "свидание": "команда «свидание»",
    "скучаю": "напоминание: искры на исходе",
    "расставание": "расставание",
    "предложение брака": "кто-то предложил брак",
    "свадьба": "свадьба",
    "развод": "развод",
    "годовщина": "годовщина свадьбы",
    "ребёнок": "рождение ребёнка",
    "обида": "кто-то обиделся",
}


REL_TXT_PROPOSE = [
    "💌 {a} признаётся {b} в чувствах и предлагает быть вместе.\nСердце бьётся чаще: нажмите «Да» или «Нет». Запрос действителен 2 минуты.",
    "💘 {a} протягивает руку и сердце: {b}, станем парой?\nОтвет ждут 2 минуты: кнопка «Да», «Нет» или слова «принять» и «отказать».",
    "🌹 Для {b} есть особое послание: {a} мечтает встречаться!\nУ вас 2 минуты, чтобы ответить: «Да» или «Нет».",
]


REL_TXT_ACCEPT = [
    "💞 Два сердца нашли друг друга: {a} и {b} теперь пара!",
    "💖 Свершилось! {a} и {b} вместе. Пусть это будет красивая история.",
    "🌷 {a} и {b} теперь вместе. Берегите друг друга и не забывайте про свидания.",
]


REL_TXT_DECLINE = [
    "💔 {b} мягко отказал{ea} {a}. Бывает, зато теперь всё ясно.",
    "🥀 Сердце {a} дрогнуло: {b} ответил{ea} «нет». Но всё ещё впереди.",
    "🌧 {b} пока не готов{ea} к отношениям с {a}. Дружба тоже красиво.",
]


PROPOSE = {"предложить отношения", "предложить встречаться", "встречаться"}


ACCEPT = {"принять", "принимаю", "согласна", "согласен"}


DECLINE = {"отказать", "отказываюсь", "отказаться"}


LEAVE = {"расстаться", "расстаёмся", "расстаемся", "порвать отношения", "расторгнуть"}


STATUS_SELF = {"моя пара", "мои отношения", "отн я", "профиль пары"}


STATUS_OTHER = {"пара", "отношения"}   # только ответом на сообщение человека


DATE_WORDS = {"свидание", "пойти на свидание"}


TOPPAIRS = {"топ пар"}


LIST_WORDS = {"список пар", "все пары"}


OFFEND_WORDS = {"обида", "обидеться", "я обиделся", "я обиделась"}


KID_WORDS = {"завести ребёнка", "завести ребенка", "родить ребёнка"}


KIDS_LIST_WORDS = {"дети", "мои дети", "наши дети"}


SONS = ["Артём", "Матвей", "Лев", "Тимур", "Ян", "Макс", "Платон", "Мирон"]


DAUGHTERS = ["Аня", "Соня", "Мия", "Ева", "Алиса", "Вера", "Лея", "Майя"]


# перевод старых значений «любви» (0 до 100) в искры, один раз
if not state_get("sparks_v1"):
    db.execute("UPDATE pairs SET love=love*5")
    db.commit()
    state_set("sparks_v1", "1")


def ea(uid):
    """окончание по полу: '' (м), 'а' (ж) или '(а)', если пол не указан"""
    r = urow(uid)
    g = (r["gender"] if r and "gender" in r.keys() else "") or ""
    return "" if g == "м" else "а" if g == "ж" else "(а)"


def pair_of(uid):
    return db.execute("SELECT * FROM pairs WHERE a=? OR b=?", (uid, uid)).fetchone()


def pair_by_id(pid):
    return db.execute("SELECT * FROM pairs WHERE id=?", (pid,)).fetchone()


def partner_of(row, uid):
    return row["b"] if row["a"] == uid else row["a"]


def uname(uid):
    r = urow(uid)
    return r["name"] if r else str(uid)


def spark_level(n):
    lvl = 1
    for i, (thr, _) in enumerate(LEVELS, 1):
        if n >= thr:
            lvl = i
    return lvl


def kids_of(pid):
    return db.execute("SELECT * FROM kids WHERE pair_id=? ORDER BY id", (pid,)).fetchall()


def upkeep(row):
    base = 10 * spark_level(row["love"])
    base *= 1 + 0.1 * len(kids_of(row["id"]))
    if row["married_at"]:
        base *= 0.7
    return max(5, int(base))


def spark_line(row):
    lvl = spark_level(row["love"])
    return (f"🔥 Искры: <b>{row['love']}</b> · {LEVELS[lvl - 1][1]} (ур. {lvl})\n"
            f"📈 Расход в сутки: {upkeep(row)}")


def spark_add(pid, delta, reason, who=""):
    row = pair_by_id(pid)
    if not row:
        return 0
    new = max(0, row["love"] + delta)
    db.execute("UPDATE pairs SET love=? WHERE id=?", (new, pid))
    db.execute("INSERT INTO spark_log(pair_id,delta,reason,who,ts,bal) VALUES(?,?,?,?,?,?)",
               (pid, new - row["love"], reason, who, time.time(), new))
    db.commit()
    return new


def rel_add(uid, other, amount, reason="действие"):
    """Начислить искры за действие, если uid и other пара -> (начислено, всего) или None."""
    row = pair_of(uid)
    if not row or partner_of(row, uid) != other:
        return None
    d = today()
    gain = row["gain"] if row["gain_day"] == d else 0
    add = max(0, min(amount, REL_DAILY_CAP - gain))
    db.execute("UPDATE pairs SET gain=?, gain_day=?, last_action=?, actions=actions+1 WHERE id=?",
               (gain + add, d, time.time(), row["id"]))
    db.commit()
    new = spark_add(row["id"], add, reason, uname(uid)) if add else row["love"]
    return add, new


def fmt_dur(sec):
    days = int(sec // 86400)
    if days >= 30:
        return f"{days // 30} мес. {days % 30} д."
    if days >= 1:
        return f"{days} д. {int(sec % 86400 // 3600)} ч."
    return f"{int(sec // 3600)} ч. {int(sec % 3600 // 60)} мин."


def offended_block(me_id, other_id):
    row = pair_of(me_id)
    return bool(row and partner_of(row, me_id) == other_id and row["offended"]
                and row["offended"] != me_id)


def delete_pair(pid):
    row = pair_by_id(pid)
    if row:
        bank = (row["bank"] or 0) if "bank" in row.keys() else 0
        if bank > 0:                                  # семейный счёт делится поровну
            db.execute("UPDATE users SET coins=coins+? WHERE user_id=?", (bank // 2, row["a"]))
            db.execute("UPDATE users SET coins=coins+? WHERE user_id=?", (bank - bank // 2, row["b"]))
        db.execute("DELETE FROM marry_proposals WHERE from_id IN (?,?) OR to_id IN (?,?)",
                   (row["a"], row["b"], row["a"], row["b"]))
        db.execute("DELETE FROM proposals WHERE from_id IN (?,?) OR to_id IN (?,?)",
                   (row["a"], row["b"], row["a"], row["b"]))
    db.execute("DELETE FROM pairs WHERE id=?", (pid,))
    db.execute("DELETE FROM kids WHERE pair_id=?", (pid,))
    db.commit()


MARRY_MIN_DAYS, MARRY_MIN_LOVE, MARRY_COST, DIVORCE_COST = 2, 300, 100, 50   # MARRY_MIN_LOVE: искры


MARRY_PIC_API = "kiss"


# ---------- брак ----------
def is_married(row):
    return bool(row and (row["married_at"] or 0))
