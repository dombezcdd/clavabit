# -*- coding: utf-8 -*-
"""Очки, уровни, квесты и учёт сообщений."""

import random
import re
import time
from datetime import timedelta

from config import CHAT_ID, FMT, HTML, MSG_COINS_EVERY, NOPREV, QUEST_ALL_BONUS_XP, QUEST_XP
from content.data import STOPWORDS, STREAK_MILESTONES
from core.logger import log
from core.utils import esc, level_of, link, norm, now, title_of, today, urow
from database.db import db
from services.economy import give_coins


# ============================ ОЧКИ, УРОВНИ, КВЕСТЫ ============================
def give_xp(uid, amount):
    u = urow(uid)
    if not u:
        return []
    old = level_of(u["xp"])
    xp = u["xp"] + amount
    new = level_of(xp)
    db.execute("UPDATE users SET xp=? WHERE user_id=?", (xp, uid))
    db.commit()
    ev = []
    if title_of(new) != title_of(old):
        ev.append(f"🎉 {link(uid, u['name'])} получает ранг <b>{esc(title_of(new))}</b> "
                  f"(уровень {new})!")
    elif new > old and new % 10 == 0:
        ev.append(f"⬆️ {link(uid, u['name'])} достиг {new} уровня!")
    return ev


def bump(uid, col, n=1):
    assert col in ("cnt", "replies", "plays", "repgiven")
    db.execute(f"INSERT INTO daily(day,user_id,{col}) VALUES(?,?,?) "
               f"ON CONFLICT(day,user_id) DO UPDATE SET {col}={col}+?",
               (today(), uid, n, n))
    db.commit()


def progress(uid, d=None):
    r = db.execute("SELECT * FROM daily WHERE day=? AND user_id=?", (d or today(), uid)).fetchone()
    if not r:
        return {"msgs": 0, "replies": 0, "plays": 0, "repgiven": 0}
    return {"msgs": r["cnt"], "replies": r["replies"], "plays": r["plays"],
            "repgiven": r["repgiven"]}


QUEST_TITLES = {
    "msgs": "Написать {n} сообщений",
    "replies": "Ответить на {n} сообщений",
    "plays": "Сыграть в мини-игры ({n} раз)",
    "repgiven": "Поставить +реп участнику",
}


def quests_for(d):
    rng = random.Random(d)
    types = rng.sample(list(QUEST_TITLES), 3)
    targets = {"msgs": [30, 50, 80], "replies": [5, 10, 15], "plays": [1, 2, 3], "repgiven": [1]}
    return [(t, rng.choice(targets[t])) for t in types]


async def check_quests(bot, uid):
    d = today()
    u = urow(uid)
    if not u:
        return
    prog = progress(uid, d)
    done = {r["qid"] for r in db.execute(
        "SELECT qid FROM quest_done WHERE day=? AND user_id=?", (d, uid))}
    qs = quests_for(d)
    out = []
    for qid, target in qs:
        if qid not in done and prog[qid] >= target:
            db.execute("INSERT OR IGNORE INTO quest_done VALUES(?,?,?)", (d, uid, qid))
            db.execute("UPDATE users SET quest_pts=quest_pts+1 WHERE user_id=?", (uid,))
            db.commit()
            done.add(qid)
            out.append(f"✅ {link(uid, u['name'])} выполнил квест: "
                       f"{QUEST_TITLES[qid].format(n=target)} (+{QUEST_XP} опыта)")
            out += give_xp(uid, QUEST_XP)
    if len(done) >= 3 and "ALL" not in done:
        db.execute("INSERT OR IGNORE INTO quest_done VALUES(?,?,?)", (d, uid, "ALL"))
        db.commit()
        out.append(f"🏅 {link(uid, u['name'])} выполнил ВСЕ квесты дня! (+{QUEST_ALL_BONUS_XP} опыта)")
        out += give_xp(uid, QUEST_ALL_BONUS_XP)
    if out:
        try:
            await bot.send_message(CHAT_ID, "\n".join(out), parse_mode=HTML,
                                   link_preview_options=NOPREV)
        except Exception:
            log.exception("quest msg")


def add_counted(uid, message_id, is_reply):
    d = today()
    yd = (now() - timedelta(days=1)).strftime(FMT)
    u = urow(uid)
    streak, best, last = u["streak"], u["best_streak"], u["last_day"]
    ev = []
    if last != d:
        streak = streak + 1 if last == yd else 1
        best = max(best, streak)
        if streak in STREAK_MILESTONES:
            ev.append(f"🔥 {link(uid, u['name'])} в серии уже {streak} дн. подряд!")
    cur = db.execute("INSERT OR IGNORE INTO msgs(message_id,user_id,day) VALUES(?,?,?)", (message_id, uid, d))
    if cur.rowcount == 0:                      # это сообщение уже учтено
        db.commit()
        return []
    db.execute("UPDATE users SET total=total+1, streak=?, best_streak=?, last_day=?, last_seen=? "
               "WHERE user_id=?", (streak, best, d, time.time(), uid))
    db.commit()
    bump(uid, "cnt")
    if (u["total"] + 1) % MSG_COINS_EVERY == 0:
        give_coins(uid, 1)
    if is_reply:
        bump(uid, "replies")
    ev += give_xp(uid, 1)
    return ev


def count_words(text):
    d = today()
    for w in set(re.findall(r"[a-zа-я]{5,}", norm(text))):
        if w in STOPWORDS:
            continue
        db.execute("INSERT INTO words(day,word,cnt) VALUES(?,?,1) "
                   "ON CONFLICT(day,word) DO UPDATE SET cnt=cnt+1", (d, w))
    db.commit()
