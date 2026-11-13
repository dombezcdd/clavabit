# -*- coding: utf-8 -*-
"""Вопрос дня и викторина."""

import json
import random
import re
import time

from config import HTML, NOPREV, QUIZ_MINUTES, QUIZ_XP
from content.data import QUESTIONS, QUIZ
from core.utils import esc, link, norm, urow
from database.db import db
from database.state import state_del, state_get, state_set
from services.summary import send_text
from services.xp import give_xp


# ============================ ВОПРОС И ВИКТОРИНА ============================
async def post_question(bot):
    await send_text(bot, "💬 <b>Вопрос дня</b>\n" + esc(random.choice(QUESTIONS)))


async def post_quiz(bot):
    prev = state_get("quiz_prev")
    pool = [q for i, q in enumerate(QUIZ) if str(i) != prev]
    q, answers = random.choice(pool)
    state_set("quiz_prev", QUIZ.index((q, answers)))
    state_set("quiz", json.dumps({"q": q, "a": answers,
                                  "until": time.time() + QUIZ_MINUTES * 60}, ensure_ascii=False))
    await send_text(bot, f"🧠 <b>Викторина!</b>\n{esc(q)}\n\nПервый, кто ответит правильно, получает очки. "
                         f"Время: {QUIZ_MINUTES} мин.")


def get_quiz():
    raw = state_get("quiz")
    return json.loads(raw) if raw else None


async def try_quiz(update, text):
    q = get_quiz()
    if not q:
        return
    if time.time() > q["until"]:
        return
    n = norm(text)
    for a in q["a"]:
        if re.search(rf"(?<!\w){re.escape(norm(a))}(?!\w)", n):
            state_del("quiz")
            uid = update.effective_user.id
            db.execute("UPDATE users SET quiz_pts=quiz_pts+1 WHERE user_id=?", (uid,))
            db.commit()
            ev = give_xp(uid, QUIZ_XP)
            pts = urow(uid)["quiz_pts"]
            await update.effective_message.reply_text(
                f"✅ Верно! {link(uid, urow(uid)['name'])} отвечает первым. "
                f"Очков викторины: {pts} (+{QUIZ_XP} опыта)\n" + "\n".join(ev),
                parse_mode=HTML, link_preview_options=NOPREV)
            return
