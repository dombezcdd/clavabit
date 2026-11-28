# -*- coding: utf-8 -*-
"""Карточки с котятами: «карточка» (раз в 30 минут) и «коллекция котят». Фото берётся с TheCatAPI в момент выпадения."""

import asyncio
import json
import random
import time
import urllib.request

from telegram import InputMediaPhoto

from config import ALLOWED, HTML
from core.helpers import reply
from core.utils import disp, esc, link, touch
from database.db import db

CD_SEC = 30 * 60
RARITY = [("Обычная", "⚪", 60), ("Редкая", "🔵", 25), ("Эпическая", "🟣", 10), ("Легендарная", "🟡", 4), ("Мифическая", "🔴", 1)]
NAMES = ["Мурзик", "Барсик", "Пушок", "Снежок", "Рыжик", "Тигра", "Симба", "Багира", "Кузя", "Персик", "Мишка", "Соня", "Ушастик",
         "Космос", "Оладушек", "Бублик", "Шерлок", "Маркиз", "Лаки", "Дымка", "Пират", "Зефир", "Масяня", "Тоша"]
FALLBACK = ["LSaDk6OjY", "ZocD-pQxd", "hBXicehMA", "bhs"]
API = "https://api.thecatapi.com/v1/images/search?mime_types=jpg,png"


def _init():
    db.execute("CREATE TABLE IF NOT EXISTS cat_cards(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, img_id TEXT, "
               "url TEXT, name TEXT, rarity INTEGER, created REAL)")


def _fetch():
    try:
        req = urllib.request.Request(API, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as r:
            d = json.loads(r.read().decode())[0]
        return d["id"], d["url"]
    except Exception:
        i = random.choice(FALLBACK)
        return i, f"https://cdn2.thecatapi.com/images/{i}.jpg"


def _roll():
    return random.choices(range(len(RARITY)), weights=[r[2] for r in RARITY])[0]


def _stats(uid):
    rows = db.execute("SELECT rarity, COUNT(*) c FROM cat_cards WHERE user_id=? GROUP BY rarity", (uid,)).fetchall()
    return {r["rarity"]: r["c"] for r in rows}


async def handle_cat_text(update, context, low, text):
    low = low.strip()
    new = low in ("карточка", "новая карточка", "котик", "карточка кота")
    coll = low in ("коллекция котят", "моя коллекция", "коллекция карточек", "мои карточки", "коллекция")
    if not (new or coll) or update.effective_chat.id not in ALLOWED:
        return False
    me = update.effective_user
    touch(me)
    _init()
    if coll:
        st = _stats(me.id)
        total = sum(st.values())
        if not total:
            await reply(update, "У тебя пока нет карточек. Напиши «карточка» 🐱")
            return True
        lines = [f"🐱 <b>Коллекция {link(me.id, disp(me))}</b>: {total} шт."]
        for i, (n, e, _) in enumerate(RARITY):
            lines.append(f"{e} {n}: {st.get(i, 0)}")
        best = db.execute("SELECT * FROM cat_cards WHERE user_id=? ORDER BY rarity DESC, id DESC LIMIT 6", (me.id,)).fetchall()
        try:
            media = [InputMediaPhoto(b["url"], caption="\n".join(lines) if k == 0 else None, parse_mode=HTML)
                     for k, b in enumerate(best)]
            await update.effective_chat.send_media_group(media, reply_to_message_id=update.effective_message.message_id)
        except Exception:
            await reply(update, "\n".join(lines))
        return True
    last = db.execute("SELECT MAX(created) m FROM cat_cards WHERE user_id=?", (me.id,)).fetchone()["m"] or 0
    left = int(last + CD_SEC - time.time())
    if left > 0:
        await reply(update, f"⏳ Следующая карточка через {left // 60 + 1} мин.")
        return True
    img_id, url = await asyncio.to_thread(_fetch)
    r = _roll()
    name = random.choice(NAMES)
    db.execute("INSERT INTO cat_cards(user_id,img_id,url,name,rarity,created) VALUES(?,?,?,?,?,?)",
               (me.id, img_id, url, name, r, time.time()))
    db.commit()
    n, e, _ = RARITY[r]
    total = db.execute("SELECT COUNT(*) c FROM cat_cards WHERE user_id=?", (me.id,)).fetchone()["c"]
    cap = (f"🃏 <b>Новая карточка!</b>\n🐱 Кот: <b>{esc(name)}</b>\n{e} Редкость: <b>{n}</b>\n"
           f"В коллекции: {total} · «коллекция котят»")
    try:
        await update.effective_message.reply_photo(url, caption=cap, parse_mode=HTML)
    except Exception:
        await reply(update, cap)
    return True
