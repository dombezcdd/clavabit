# -*- coding: utf-8 -*-
"""Базовые утилиты: время, форматирование, пользователи, уровни и звания, владелец."""

import html
import re
import time
from datetime import datetime, timedelta

from config import FMT, OWNER_ID, OWNER_USERNAME, TZ
from content.data import OLD_TITLES, RANK_TITLES
from database.db import db
from database.state import state_get, state_set


# ============================ УТИЛИТЫ ============================
def now():
    return datetime.now(TZ)


def today():
    return now().strftime(FMT)


def esc(s):
    return html.escape(str(s))


def link(uid, name):
    return f'<a href="tg://user?id={uid}">{esc(name)}</a>'


def disp(user):
    return (user.full_name or user.username or str(user.id)).strip()


def urow(uid):
    return db.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()


def touch(user):
    uid, name = user.id, disp(user)
    un = (user.username or "").lower()
    if un:
        db.execute("UPDATE users SET username='' WHERE username=? AND user_id!=?", (un, uid))
    if urow(uid):
        db.execute("UPDATE users SET name=?, username=? WHERE user_id=?", (name, un, uid))
    else:
        db.execute("INSERT INTO users(user_id,name,username,first_seen) VALUES(?,?,?,?)",
                   (uid, name, un, time.time()))
    db.commit()


def find_by_username(un):
    rows = db.execute("SELECT * FROM users WHERE username=? ORDER BY last_seen DESC", (un.lstrip("@").lower(),)).fetchall()
    return rows[0] if len(rows) == 1 else None      # неоднозначное имя не принимаем


def tagged(row):
    t = (row["tag"] or "").strip()
    name = esc(row["name"])
    return f"<b>{esc(t)}</b> {name}" if t else name


def is_owner(user):
    if not user:
        return False
    if OWNER_ID:
        return str(user.id) == OWNER_ID
    oid = state_get("owner_id")
    if oid:
        return str(user.id) == oid          # ID уже сохранён: имя больше не проверяем
    if (user.username or "").lower() == OWNER_USERNAME.lower():
        state_set("owner_id", user.id)      # самый первый раз определяем по имени и закрепляем ID
        return True
    return False


def owner_mention():
    oid = state_get("owner_id")
    return link(oid, "@" + OWNER_USERNAME) if oid else "@" + OWNER_USERNAME


def level_need(l):
    return int(15 * l ** 1.6)


def level_of(xp):
    lvl = 0
    for l in range(1, 101):
        if xp >= level_need(l):
            lvl = l
        else:
            break
    return lvl


def title_of(lvl):
    t = RANK_TITLES[0][1]
    for need, name in RANK_TITLES:
        if lvl >= need:
            t = name
    return t


def old_title(first_seen):
    days = int((time.time() - (first_seen or time.time())) // 86400)
    t = OLD_TITLES[0][1]
    for need, name in OLD_TITLES:
        if days >= need:
            t = name
    return t, days


def fmt_when(ts):
    if not ts:
        return "неизвестно"
    d = datetime.fromtimestamp(ts, TZ)
    n = now()
    if d.date() == n.date():
        return f"сегодня в {d:%H:%M}"
    if d.date() == (n - timedelta(days=1)).date():
        return f"вчера в {d:%H:%M}"
    return f"{d:%d.%m.%Y в %H:%M}"


def norm(s):
    s = s.lower().replace("ё", "е")
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()
