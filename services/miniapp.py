# -*- coding: utf-8 -*-
"""Mini App: сессии мини-игр на смене и приём результата.

Игра открывается ссылкой https://t.me/<бот>/<MINI_APP>?startapp=<sid>. По окончании страница открывает
https://t.me/<бот>?start=r_<sid>_<очки>, а бот проверяет сессию. Очки приходят от клиента, поэтому
награда небольшая: максимум MINI_MULT x обычной зарплаты и только за одно открытое задание.
"""

import secrets
import time

from config import MINI_APP, MINI_MULT, MINI_SESSION_MIN
from database.db import db

# код профессии для страницы (первые 3 символа sid); остальные профессии получат случайную игру
JOB_CODES = {"курьер": "kur", "уборщик": "uby", "продавец": "pro", "официант": "off", "таксист": "tax",
             "программист": "prg", "врач": "vra", "пилот": "pil", "директор": "dir"}
SESSION_TTL = 30 * 60


def mini_enabled():
    return bool(MINI_APP)


def mini_link(bot_username, param):
    return f"https://t.me/{bot_username}/{MINI_APP}?startapp={param}"


def mini_open(uid, chat_id, reply_to, job, task_created):
    """Создаёт сессию игры для текущего задания. -> sid"""
    sid = JOB_CODES.get(job, "rnd") + secrets.token_hex(5)
    db.execute("DELETE FROM mini_sessions WHERE created<?", (time.time() - 86400,))
    db.execute("INSERT INTO mini_sessions(sid,user_id,chat_id,reply_to,job,task_created,created) "
               "VALUES(?,?,?,?,?,?,?)", (sid, uid, chat_id, reply_to, job, task_created, time.time()))
    db.commit()
    return sid


def mult_for(score):
    for lim, m in MINI_MULT:
        if score >= lim:
            return m
    return MINI_MULT[-1][1]


def mini_claim(uid, sid, score):
    """Проверяет результат. -> (ok, сообщение, сессия|None)"""
    s = db.execute("SELECT * FROM mini_sessions WHERE sid=?", (sid,)).fetchone()
    if not s or s["user_id"] != uid:
        return False, "Эта игра не найдена или открыта другим участником.", None
    if s["used"]:
        return False, "Результат этой игры уже засчитан.", None
    age = time.time() - s["created"]
    if age > SESSION_TTL:
        return False, "Время смены вышло, результат уже не засчитать.", None
    if age < MINI_SESSION_MIN:
        return False, "Слишком быстро: игра ещё не могла закончиться.", None
    if not 0 <= score <= 100:
        return False, "Некорректный результат.", None
    cur = db.execute("UPDATE mini_sessions SET used=1 WHERE sid=? AND used=0", (sid,))
    db.commit()
    if cur.rowcount == 0:
        return False, "Результат этой игры уже засчитан.", None
    return True, "", s
