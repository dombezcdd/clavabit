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
from services.clans import PTS_MSG, war_add
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


QUEST_COLS = ("cnt", "replies", "plays", "repgiven", "shifts", "biz", "casino", "duelw", "feed", "longmsg", "stock", "mafia")


def bump(uid, col, n=1):
    assert col in QUEST_COLS
    db.execute(f"INSERT INTO daily(day,user_id,{col}) VALUES(?,?,?) "
               f"ON CONFLICT(day,user_id) DO UPDATE SET {col}={col}+?",
               (today(), uid, n, n))
    db.commit()


async def quest_hit(bot, uid, col, chat_id=None):
    """Засчитать действие для квестов дня и сразу проверить выполнение."""
    try:
        bump(uid, col)
        await check_quests(bot, uid, chat_id)
    except Exception:
        log.exception("quest_hit")


def progress(uid, d=None):
    r = db.execute("SELECT * FROM daily WHERE day=? AND user_id=?", (d or today(), uid)).fetchone()
    out = {c: 0 for c in QUEST_COLS}
    out["msgs"] = 0
    if r:
        for c in QUEST_COLS:
            out[c] = r[c] or 0
        out["msgs"] = r["cnt"] or 0
    return out


# квест: (название, возможные цели). Каждый день берётся по одному из трёх разделов
QUEST_POOL = {
    "talk": {
        "msgs": ("Написать {n} нормальных сообщений", [30, 50, 80]),
        "replies": ("Ответить на {n} сообщений других", [5, 10, 15]),
        "longmsg": ("Написать {n} развёрнутых сообщений (от 60 символов)", [3, 5, 8]),
    },
    "game": {
        "plays": ("Сыграть в мини-игры ({n} раз)", [1, 2, 3]),
        "casino": ("Сделать {n} ставок в казино", [3, 5, 8]),
        "duelw": ("Победить в дуэли", [1]),
        "mafia": ("Сыграть партию в мафию", [1]),
    },
    "life": {
        "shifts": ("Отработать смен: {n}", [1, 2, 3]),
        "biz": ("Собрать доход с бизнеса", [1]),
        "feed": ("Покормить питомца", [1]),
        "stock": ("Купить или продать акции", [1]),
        "repgiven": ("Поставить +реп участнику", [1]),
    },
}
QUEST_TITLES = {k: v[0] for grp in QUEST_POOL.values() for k, v in grp.items()}


def quests_for(d):
    """Три квеста дня: по одному из разговорных, игровых и бытовых, чтобы дни не повторялись."""
    rng = random.Random(d)
    out = []
    for grp in ("talk", "game", "life"):
        k = rng.choice(list(QUEST_POOL[grp]))
        out.append((k, rng.choice(QUEST_POOL[grp][k][1])))
    return out


async def check_quests(bot, uid, chat_id=None):
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
            await bot.send_message(chat_id or CHAT_ID, "\n".join(out), parse_mode=HTML,
                                   link_preview_options=NOPREV)
        except Exception:
            log.exception("quest msg")


def add_counted(uid, message_id, is_reply, text=""):
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
    from core.antispam import is_real_text
    if text and is_real_text(text):
        n = (u["coin_msgs"] or 0) + 1
        db.execute("UPDATE users SET coin_msgs=? WHERE user_id=?", (n, uid))
        db.commit()
        if n % MSG_COINS_EVERY == 0:
            give_coins(uid, 1)
    if is_reply:
        bump(uid, "replies")
    war_add(uid, PTS_MSG)
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
