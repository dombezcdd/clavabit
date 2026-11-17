# -*- coding: utf-8 -*-
"""Дуэли и кости с согласием соперника."""

import asyncio
import random
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import HTML, NOPREV
from core.antispam import cooldown
from core.helpers import group_only, reply, target_user, why_no_target
from core.utils import disp, esc, link, touch, urow
from database.db import db
from services.profile import profile_score
from services.xp import bump, check_quests


# ---------- мини-игры ----------
async def played(bot, uid):
    bump(uid, "plays")
    await check_quests(bot, uid)


async def _send(bot, chat_id, text, reply_to=None, markup=None):
    return await bot.send_message(chat_id, text, parse_mode=HTML, link_preview_options=NOPREV,
                                  reply_to_message_id=reply_to, reply_markup=markup,
                                  allow_sending_without_reply=True)


async def run_dice(bot, chat, a_id, b_id, reply_to=None):
    a = await bot.send_dice(chat, emoji="🎲")
    b = await bot.send_dice(chat, emoji="🎲")
    await asyncio.sleep(4)
    va, vb = a.dice.value, b.dice.value
    ra, rb = urow(a_id), urow(b_id)
    if va == vb:
        res = "🤝 Ничья!"
    else:
        win = ra if va > vb else rb
        db.execute("UPDATE users SET game_pts=game_pts+1 WHERE user_id=?", (win["user_id"],))
        db.commit()
        res = f"🏆 Победил {link(win['user_id'], win['name'])}! (+1 игровое очко)"
    await _send(bot, chat, f"🎲 {esc(ra['name'])}: {va} — {esc(rb['name'])}: {vb}\n{res}", reply_to)
    await played(bot, a_id)
    await played(bot, b_id)


async def run_duel(bot, chat, a_id, b_id, reply_to=None):
    ra, rb = urow(a_id), urow(b_id)
    pa, pb = await profile_score(bot, ra), await profile_score(bot, rb)
    sa = round(min(sum(pa.values()), 100) * 0.1) + random.randint(0, 30)      # профиль даёт максимум +10, остальное удача
    sb = round(min(sum(pb.values()), 100) * 0.1) + random.randint(0, 30)

    def fmt(p):
        return ", ".join(f"{k} {v}" for k, v in p.items() if v)

    win = ra if sa >= sb else rb
    lose = rb if win is ra else ra
    db.execute("UPDATE users SET game_pts=game_pts+2, duel_w=duel_w+1 WHERE user_id=?", (win["user_id"],))
    db.execute("UPDATE users SET duel_l=duel_l+1 WHERE user_id=?", (lose["user_id"],))
    db.commit()
    from services.xp import quest_hit
    await quest_hit(bot, win["user_id"], "duelw", chat)
    await _send(bot, chat,
                f"⚔️ <b>Дуэль профилей</b>\n"
                f"{esc(ra['name'])}: <b>{sa}</b> ({fmt(pa)})\n"
                f"{esc(rb['name'])}: <b>{sb}</b> ({fmt(pb)})\n\n"
                f"🏆 Побеждает {link(win['user_id'], win['name'])} (+2 игровых очка)\n"
                f"<i>Профиль даёт максимум +10 очков, остальное решает удача: слабый профиль тоже может выиграть.</i>", reply_to)
    await played(bot, a_id)
    await played(bot, b_id)


CHALLENGE_SEC = 120


def challenge_kb(kind, a, b):
    ts = int(time.time())
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ Принять", callback_data=f"ch:{kind}:{a}:{b}:y:{ts}"),
                                  InlineKeyboardButton("❌ Отказаться", callback_data=f"ch:{kind}:{a}:{b}:n:{ts}")]])


async def send_challenge(update, context, kind):
    me = update.effective_user
    other = target_user(update)
    cmd = {"duel": "«дуэль»", "dice": "/dice", "rps": "«кнб»", "prof": "«дуэль профилей»"}.get(kind, "/duel")
    if not other or other.id == me.id:
        return await reply(update, why_no_target(update, f"Ответь командой {cmd} на сообщение соперника или напиши {cmd} @юз"))
    if not cooldown((kind, me.id), 30):
        return await reply(update, "Подожди немного ⏳")
    touch(me)
    title = {"duel": "🔫 дуэль на выстрелах", "rps": "✊ камень-ножницы-бумага", "prof": "🪪 дуэль профилей",
             "dice": "🎲 кости"}[kind]
    await _send(context.bot, update.effective_chat.id,
                f"{link(other.id, disp(other))}, {link(me.id, disp(me))} вызывает тебя: {title}!\n"
                f"Принять вызов? Время на ответ: {CHALLENGE_SEC // 60} мин.",
                update.effective_message.message_id, challenge_kb(kind, me.id, other.id))


async def on_challenge_btn(update, context):
    q = update.callback_query
    p = (q.data or "").split(":")
    if len(p) != 6 or p[1] not in ("duel", "dice", "rps", "prof") or not p[2].isdigit() or not p[3].isdigit() or p[4] not in ("y", "n"):
        return await q.answer()
    kind, a, b, ans, ts = p[1], int(p[2]), int(p[3]), p[4], int(p[5]) if p[5].isdigit() else 0
    if q.from_user.id != b:
        return await q.answer("Этот вызов адресован не тебе", show_alert=True)
    cur = db.execute("INSERT OR IGNORE INTO challenge_done(chat_id,message_id,ts) VALUES(?,?,?)",
                     (q.message.chat_id, q.message.message_id, time.time()))
    db.execute("DELETE FROM challenge_done WHERE ts<?", (time.time() - 7 * 86400,))
    db.commit()
    if cur.rowcount == 0:
        return await q.answer()                 # этот вызов уже обработан (в том числе до перезапуска)
    try:
        await q.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    if time.time() - ts > CHALLENGE_SEC:
        await q.answer("Вызов устарел", show_alert=True)
        return
    ra, rb = urow(a), urow(b)
    if not ra or not rb:
        return await q.answer()
    if ans == "n":
        await q.answer()
        return await _send(context.bot, q.message.chat_id,
                           f"🙅 {link(b, rb['name'])} отказался от вызова {link(a, ra['name'])}.")
    await q.answer()
    if kind == "dice":
        await run_dice(context.bot, q.message.chat_id, a, b)
    elif kind == "prof":
        await run_duel(context.bot, q.message.chat_id, a, b)
    else:
        from handlers.duelgames import start
        await start(context.bot, "shoot" if kind == "duel" else "rps", q.message.chat_id, a, b)


@group_only
async def cmd_duel(update, context):
    low = (update.effective_message.text or "").lower()
    await send_challenge(update, context, "prof" if "профил" in low else "duel")


@group_only
async def cmd_rps(update, context):
    await send_challenge(update, context, "rps")
