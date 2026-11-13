# -*- coding: utf-8 -*-
"""Итоги дня."""

import os
from datetime import timedelta

from telegram import ReplyParameters

from config import BANNER, BASE, CHAT_ID, HTML, MIN_MSGS, MIN_REACTIONS, NOPREV
from core.logger import log
from core.utils import link, now, owner_mention
from database.db import db
from services.stats import fmt_top, month_start, top_rows, week_start


# ============================ ИТОГИ ДНЯ ============================
async def send_text(bot, text, **kw):
    return await bot.send_message(CHAT_ID, text, parse_mode=HTML,
                                  link_preview_options=NOPREV, **kw)


async def send_summary(bot, d, periodic):
    rows = [r for r in top_rows(d, d, 3) if r["c"] >= MIN_MSGS]
    if rows:
        medals = ["🥇", "🥈", "🥉"]
        lines = [f"{medals[i]} {link(r['uid'], r['name'])} — {r['c']} сообщ."
                 for i, r in enumerate(rows)]
        text = ("🏆 <b>Итоги дня</b>\n" + "\n".join(lines) +
                f"\n\n🎁 {owner_mention()}, вручи подарки победителям!")
    else:
        text = f"🏆 <b>Итоги дня</b>\nСегодня никто не набрал норму ({MIN_MSGS} сообщений). Завтра новый шанс!"
    path = os.path.join(BASE, BANNER)
    sent = False
    if os.path.exists(path) and len(text) <= 1000:
        try:
            with open(path, "rb") as f:
                await bot.send_photo(CHAT_ID, f, caption=text, parse_mode=HTML)
            sent = True
        except Exception:
            log.exception("banner")
    if not sent:
        await send_text(bot, text)

    best = db.execute("SELECT m.message_id, m.user_id, m.reactions, u.name FROM msgs m "
                      "JOIN users u ON u.user_id=m.user_id WHERE m.day=? AND m.reactions>=? "
                      "ORDER BY m.reactions DESC LIMIT 1", (d, MIN_REACTIONS)).fetchone()
    if best:
        try:
            await bot.send_message(
                CHAT_ID,
                f"⭐ <b>Лучшее сообщение дня</b> — {link(best['user_id'], best['name'])} "
                f"({best['reactions']} реакций)!\n🎁 {owner_mention()}, награда автору.",
                parse_mode=HTML, link_preview_options=NOPREV,
                reply_parameters=ReplyParameters(message_id=best["message_id"],
                                                 allow_sending_without_reply=True))
        except Exception:
            log.exception("best msg")

    if periodic:
        n = now()
        if n.weekday() == 6:
            rows = top_rows(week_start(), d, 10)
            if rows:
                await send_text(bot, "📅 <b>Топ недели</b>\n" + fmt_top(rows))
        if (n + timedelta(days=1)).day == 1:
            rows = top_rows(month_start(), d, 10)
            if rows:
                await send_text(bot, "🗓 <b>Топ месяца</b>\n" + fmt_top(rows))
