# -*- coding: utf-8 -*-
"""Профиль и топы: /me, /top, /week, /month, /quiztop, /quests."""

import time

from config import QUEST_ALL_BONUS_XP, QUEST_XP
from core.helpers import group_only, reply, target_user
from core.utils import esc, today, touch, urow
from database.db import db
from services.profile import build_profile
from services.stats import fmt_top, month_start, top_rows, week_start
from services.xp import QUEST_TITLES, progress, quests_for


_prof_hits = {}      # uid -> [время запросов]
_prof_block = {}     # uid -> до какого времени игнорируем
PROF_FREE, PROF_WINDOW, PROF_BLOCK = 2, 60, 60


def _profile_gate(uid):
    """-> None (можно) | 0 (молча игнорировать) | секунды (сказать один раз «позже»)"""
    now_ = time.time()
    until = _prof_block.get(uid, 0)
    if until > now_:
        return 0
    hits = [t for t in _prof_hits.get(uid, []) if now_ - t < PROF_WINDOW]
    if len(hits) >= PROF_FREE:
        _prof_block[uid] = now_ + PROF_BLOCK
        _prof_hits[uid] = []
        return PROF_BLOCK
    hits.append(now_)
    _prof_hits[uid] = hits
    return None


async def send_profile(update, context, u):
    from handlers.finance import _send_photo
    gate = _profile_gate(update.effective_user.id)
    if gate == 0:
        return
    if gate:
        return await reply(update, f"⏳ Слишком часто. Попробуйте позже, через {gate} сек")
    from services.profile import profile_view
    touch(u)
    try:
        card, cap = await profile_view(context.bot, urow(u.id))
    except Exception:
        card, cap = None, await build_profile(context.bot, urow(u.id))
    if card is None:
        return await reply(update, cap)
    await _send_photo(update.effective_message, card, cap)


@group_only
async def cmd_me(update, context):
    await send_profile(update, context, target_user(update) or update.effective_user)


@group_only
async def cmd_top(update, context):
    rows = top_rows(today(), today())
    await reply(update, "📊 <b>Топ дня</b>\n" + fmt_top(rows) if rows else "Пока тишина 🤫")


@group_only
async def cmd_week(update, context):
    rows = top_rows(week_start(), today())
    await reply(update, "📅 <b>Топ недели</b>\n" + fmt_top(rows) if rows else "Пока тишина 🤫")


@group_only
async def cmd_month(update, context):
    rows = top_rows(month_start(), today())
    await reply(update, "🗓 <b>Топ месяца</b>\n" + fmt_top(rows) if rows else "Пока тишина 🤫")


@group_only
async def cmd_quiztop(update, context):
    rows = db.execute("SELECT name, quiz_pts FROM users WHERE quiz_pts>0 "
                      "ORDER BY quiz_pts DESC LIMIT 10").fetchall()
    if not rows:
        return await reply(update, "Пока никто не отвечал правильно 🧠")
    await reply(update, "🧠 <b>Рейтинг викторины</b>\n" + "\n".join(
        f"{i + 1}. {esc(r['name'])} — {r['quiz_pts']}" for i, r in enumerate(rows)))


@group_only
async def cmd_quests(update, context):
    uid = update.effective_user.id
    d = today()
    prog = progress(uid, d)
    done = {r["qid"] for r in db.execute(
        "SELECT qid FROM quest_done WHERE day=? AND user_id=?", (d, uid))}
    lines = ["📜 <b>Квесты на сегодня</b>"]
    for qid, target in quests_for(d, uid):
        mark = "✅" if qid in done else "▫️"
        lines.append(f"{mark} {QUEST_TITLES[qid].format(n=target)} "
                     f"({min(prog[qid], target)}/{target})")
    lines.append(f"\nНаграда: +{QUEST_XP} опыта за квест, +{QUEST_ALL_BONUS_XP} за все три.")
    from services.vip import VIP_QUEST_XP, is_vip
    if is_vip(uid):
        from services.xp import vip_quests_for
        lines.append("\n👑 <b>VIP-квесты</b>")
        for qid, target in vip_quests_for(d, uid):
            mark = "✅" if ("V" + qid) in done else "▫️"
            lines.append(f"{mark} {QUEST_TITLES[qid].format(n=target)} ({min(prog[qid], target)}/{target}) · +{VIP_QUEST_XP} опыта")
    else:
        lines.append("\n👑 С VIP есть 2 особых квеста: «вип»")
    await reply(update, "\n".join(lines))
