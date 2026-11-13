# -*- coding: utf-8 -*-
"""Журнал админов, приветствие, правила, статистика недели."""

import time
from datetime import datetime

from config import ALLOWED, HTML
from core.helpers import group_only, reply
from core.logger import log
from core.ranks import need
from core.utils import disp, esc, link, now, touch
from database.db import db
from database.state import state_get, state_set
from services.stats import week_start


@need("журнал")
async def cmd_admin_log(update, context):
    a = list(context.args or [])
    n = max(1, min(int(a[0]), 40)) if a and a[0].isdigit() else 15
    rows = db.execute("SELECT * FROM admin_log ORDER BY id DESC LIMIT ?", (n,)).fetchall()
    if not rows:
        return await reply(update, "Журнал пока пуст.")
    lines = [f"📒 <b>Журнал действий</b> (последние {len(rows)})"]
    for r in rows:
        t = datetime.fromtimestamp(r["ts"], now().tzinfo).strftime("%d.%m %H:%M")
        lines.append(f"{t} · {esc(r['actor_name'])}: {esc(r['text'])}")
    await reply(update, "\n".join(lines)[:4000])


@need("установить приветствие")
async def cmd_set_welcome(update, context):
    t = " ".join(context.args or []).strip()
    if not t:
        cur = state_get("welcome")
        return await reply(update, ("Сейчас: " + esc(cur) if cur else "Приветствие выключено.") +
                                   "\nФормат: установить приветствие Привет, {name}! Правила: «правила». "
                                   "Выключить: установить приветствие выкл")
    if t.lower() in ("выкл", "off", "нет"):
        state_set("welcome", "")
        return await reply(update, "Приветствие выключено.")
    state_set("welcome", t[:500])
    await reply(update, "✅ Приветствие сохранено. {name} заменится на имя новичка.")


@need("установить правила")
async def cmd_set_rules(update, context):
    t = " ".join(context.args or []).strip()
    if not t:
        return await reply(update, "Формат: установить правила Текст правил (выкл — убрать)")
    state_set("rules", "" if t.lower() in ("выкл", "off") else t[:1500])
    await reply(update, "✅ Правила сохранены. Участники смотрят их словом «правила».")


@group_only
async def cmd_rules(update, context):
    t = state_get("rules")
    if t:
        await reply(update, "📜 <b>Правила чата</b>\n" + esc(t))


async def on_new_members(update, context):
    msg, chat = update.effective_message, update.effective_chat
    if not msg or not chat or chat.id not in ALLOWED:
        return
    tpl = state_get("welcome")
    if not tpl:
        return
    for u in msg.new_chat_members or []:
        if u.is_bot:
            continue
        touch(u)
        try:
            await context.bot.send_message(chat.id, esc(tpl).replace("{name}", link(u.id, disp(u))),
                                           parse_mode=HTML)
        except Exception:
            log.exception("welcome")


@need("статистика недели")
async def cmd_weekstat(update, context):
    ws = week_start()
    days = db.execute("SELECT day, SUM(cnt) c FROM daily WHERE day>=? GROUP BY day ORDER BY day", (ws,)).fetchall()
    total = sum(r["c"] or 0 for r in days)
    active = db.execute("SELECT COUNT(DISTINCT user_id) FROM daily WHERE day>=? AND cnt>0", (ws,)).fetchone()[0]
    top = db.execute("SELECT u.user_id, u.name, SUM(d.cnt) c FROM daily d JOIN users u ON u.user_id=d.user_id "
                     "WHERE d.day>=? GROUP BY d.user_id ORDER BY c DESC LIMIT 5", (ws,)).fetchall()
    new = db.execute("SELECT COUNT(*) FROM users WHERE first_seen>=?", (time.time() - 7 * 86400,)).fetchone()[0]
    pairs_n = db.execute("SELECT COUNT(*) FROM pairs").fetchone()[0]
    married = db.execute("SELECT COUNT(*) FROM pairs WHERE married_at>0").fetchone()[0]
    mx = max([r["c"] or 0 for r in days] + [1])
    lines = [f"📊 <b>Неделя в чате</b>\nСообщений: {total} · активных: {active} · новых: {new}",
             f"Пар: {pairs_n} (в браке {married})", "\n<b>По дням</b>"]
    for r in days:
        c = r["c"] or 0
        lines.append(f"{r['day'][5:]} {'█' * max(1, round(c * 10 / mx)) if c else '·'} {c}")
    if top:
        lines.append("\n<b>Топ-5</b>")
        for i, r in enumerate(top, 1):
            lines.append(f"{i}. {link(r['user_id'], r['name'])}: {r['c']}")
    await reply(update, "\n".join(lines))
