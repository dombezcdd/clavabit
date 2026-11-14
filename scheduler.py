# -*- coding: utf-8 -*-
"""Планировщик: ежедневные события, реклама, приглашения."""

import asyncio
import random
import time
from datetime import timedelta

from config import CHANNEL, FMT, OWNER_USERNAME, PROMO_MAX_MIN, PROMO_MIN_MIN, QUESTION_TIME, QUIET_HOURS, QUIZ_TIME, SUMMARY_TIME
from core.logger import log
from core.utils import esc, now
from database.db import db
from database.state import state_del, state_get, state_set
from handlers.life import life_daily
from handlers.monopoly import monopoly_tick
from services.quiz import get_quiz, post_question, post_quiz
from services.relations import REL_TIME
from services.summary import send_summary, send_text


# ============================ ПЛАНИРОВЩИК ============================
async def tick(app):
    bot = app.bot
    n = now()
    d = n.strftime(FMT)
    db.execute("DELETE FROM mutes WHERE until<?", (time.time(),))
    db.commit()
    await monopoly_tick(bot)
    for name, (h, m), fn in (
        ("question", QUESTION_TIME, lambda: post_question(bot)),
        ("quiz", QUIZ_TIME, lambda: post_quiz(bot)),
        ("summary", SUMMARY_TIME, lambda: send_summary(bot, d, True)),
        ("relations", REL_TIME, lambda: life_daily(bot)),
    ):
        sched = n.replace(hour=h, minute=m, second=0, microsecond=0)
        if n >= sched and (n - sched) < timedelta(hours=2) and state_get("ran_" + name) != d:
            if name == "relations":
                tries = int(float(state_get("tries_relations") or 0)) if state_get("tries_day") == d else 0
                if tries >= 5:
                    continue
                state_set("tries_day", d)
                state_set("tries_relations", tries + 1)
                try:
                    await fn()
                    state_set("ran_" + name, d)
                except Exception:
                    log.exception("relations (попытка %s)", tries + 1)
                continue
            state_set("ran_" + name, d)
            await fn()

    q = get_quiz()
    if q and time.time() > q["until"]:
        state_del("quiz")
        await send_text(bot, f"⌛ Время вышло. Правильный ответ: <b>{esc(q['a'][0])}</b>")

    quiet = QUIET_HOURS[0] <= n.hour < QUIET_HOURS[1]
    last = state_get("last_promo")
    if last is None:
        state_set("last_promo", time.time())
        state_set("promo_gap", random.randint(PROMO_MIN_MIN, PROMO_MAX_MIN))
    elif not quiet and time.time() - float(last) >= float(state_get("promo_gap") or 90) * 60:
        state_set("last_promo", time.time())
        state_set("promo_gap", random.randint(PROMO_MIN_MIN, PROMO_MAX_MIN))
        turn = int(float(state_get("promo_turn") or 0))
        state_set("promo_turn", turn + 1)
        await (post_ad if turn % 2 == 0 else post_invite)(bot)


async def scheduler(app):
    await asyncio.sleep(5)
    while True:
        try:
            await tick(app)
        except Exception:
            log.exception("tick")
        await asyncio.sleep(30)


async def post_ad(bot):
    await send_text(bot, random.choice([
        f"📢 Загляните к нам в канал {esc(CHANNEL)}, там проходят все розыгрыши",
        f"📢 Подписывайтесь на {esc(CHANNEL)}, чтобы не пропустить розыгрыши и новости",
        f"📢 Самое интересное у нас в канале {esc(CHANNEL)}. Подпишитесь, чтобы быть в курсе",
    ]))


async def post_invite(bot):
    ids = [r["user_id"] for r in db.execute(
        "SELECT user_id FROM users WHERE registered=1 AND total>0")]
    text = random.choice([
        "🎁 Зовите друзей в чат, за приглашения можно получить подарки",
        "🎁 Пригласите друга в чат и получите подарок",
        "🎁 Хотите подарок? Приводите друзей в чат",
    ]) + f"\nПодробности у @{OWNER_USERNAME}\nЧтобы отключить напоминания, напишите /анрег"
    if not ids:
        await send_text(bot, text)
        return
    for i in range(0, len(ids), 90):
        hidden = "".join(f'<a href="tg://user?id={u}">\u200b</a>' for u in ids[i:i + 90])
        await send_text(bot, text + hidden if i == 0 else "🎁" + hidden)
