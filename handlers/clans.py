# -*- coding: utf-8 -*-
"""Кланы и клановые войны: «клан», «клан создать Имя», «клан война Имя 300» и т.д."""

import re
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import ALLOWED, CHAT_ID
from core.helpers import reply, resolve_target
from core.logger import log
from core.utils import disp, esc, link, touch, urow
from database.db import db
from services.clans import (CLAN_CREATE_COST, CLAN_MAX, CLAN_NAME_MAX, LEVEL_MAX, LEVEL_STEP, PTS_MSG, PTS_SHIFT,
                            PTS_WIN, WAR_HOURS, WAR_PENDING_MIN, WAR_STAKE_DEFAULT, active_war, clan_level, clan_of,
                            find_clan, get_clan, members)
from services.economy import COIN, coins_of, give_coins

CLAN_RE = re.compile(r"^(клан|кланы|топ кланов|война|клан война|клан-война)(?:\s+(.*))?$")


def _clan_text(c):
    lv = clan_level(c["xp"])
    ms = members(c["id"])
    nxt = "макс. уровень" if lv >= LEVEL_MAX else f"до {lv + 1} ур. ещё {lv * LEVEL_STEP - c['xp']} {COIN}"
    lines = [f"🏰 <b>Клан «{esc(c['name'])}»</b> · ур. {lv} (+{lv}% к зарплате)",
             f"Глава: {link(c['owner'], (urow(c['owner']) or {'name': '?'})['name'])}",
             f"Казна: {c['treasury']} {COIN} · {nxt}",
             f"Участники ({len(ms)}/{CLAN_MAX}): " + ", ".join(esc(m["name"] or "?") for m in ms[:15])]
    w = active_war(c["id"])
    if w:
        lines.append(_war_line(w))
    return "\n".join(lines)


def _war_line(w):
    a, b = get_clan(w["a"]), get_clan(w["b"])
    if w["status"] == "pending":
        return f"⚔️ Вызов: «{esc(a['name'])}» → «{esc(b['name'])}», ставка {w['stake']} {COIN}, ждём ответа"
    left = max(0, int((w["end"] - time.time()) // 60))
    return (f"⚔️ Война: «{esc(a['name'])}» {w['sa']} : {w['sb']} «{esc(b['name'])}» · ставка {w['stake']} {COIN} · "
            f"осталось {left // 60} ч {left % 60} мин")


async def handle_clan_text(update, context, low, text):
    """True, если сообщение — команда кланов."""
    if update.effective_chat.id not in ALLOWED:
        return False
    m = CLAN_RE.match(low)
    if not m:
        return False
    me = update.effective_user
    touch(me)
    cmd, rest = m.group(1), (m.group(2) or "").strip()
    orig = text.strip().split(None, 1)
    orig_rest = orig[1] if len(orig) > 1 else ""
    if cmd in ("кланы", "топ кланов"):
        await _top(update)
    elif cmd == "война":
        await _war_info(update, me)
    elif cmd in ("клан война", "клан-война"):
        await _war_declare(update, me, re.sub(r"^\S+\s*", "", text.strip()))
    elif not rest:
        c = clan_of(me.id)
        await reply(update, _clan_text(c) if c else
                    f"У тебя нет клана. «клан создать Имя» или «клан вступить Имя». "
                    f"Все кланы: «кланы»")
    else:
        sub, _, arg = rest.partition(" ")
        arg_orig = orig_rest.partition(" ")[2].strip()
        if sub == "создать":
            await _create(update, me, arg_orig)
        elif sub == "вступить":
            await _join(update, me, arg_orig)
        elif sub == "выйти":
            await _leave(update, me)
        elif sub == "вклад":
            await _deposit(update, me, arg.strip())
        elif sub == "исключить":
            await _kick(update, context, me, arg_orig)
        elif sub == "распустить":
            await _disband(update, me)
        elif sub == "война":
            await _war_declare(update, me, arg_orig)
        else:
            return False
    return True


async def _create(update, me, name):
    name = name.strip()
    if clan_of(me.id):
        return await reply(update, "Ты уже в клане. Сначала «клан выйти»")
    if not name or len(name) > CLAN_NAME_MAX or " " in name or not re.match(r"^[\w\-]+$", name):
        return await reply(update, f"Название: одно слово до {CLAN_NAME_MAX} символов, например «клан создать Волки»")
    if find_clan(name):
        return await reply(update, "Клан с таким названием уже есть")
    if coins_of(me.id) < CLAN_CREATE_COST:
        return await reply(update, f"Создание клана стоит {CLAN_CREATE_COST} {COIN}, у тебя {coins_of(me.id)}")
    give_coins(me.id, -CLAN_CREATE_COST, commit=False)
    cur = db.execute("INSERT INTO clans(name,owner,created) VALUES(?,?,?)", (name, me.id, time.time()))
    db.execute("UPDATE users SET clan_id=? WHERE user_id=?", (cur.lastrowid, me.id))
    db.commit()
    await reply(update, f"🏰 Клан «{esc(name)}» создан! Ты глава. Зови друзей: «клан вступить {esc(name)}», "
                        f"пополняй казну: «клан вклад 100»")


async def _join(update, me, name):
    if clan_of(me.id):
        return await reply(update, "Ты уже в клане. Сначала «клан выйти»")
    c = find_clan(name)
    if not c:
        return await reply(update, "Нет такого клана. Список: «кланы»")
    if len(members(c["id"])) >= CLAN_MAX:
        return await reply(update, f"В клане уже {CLAN_MAX} человек")
    db.execute("UPDATE users SET clan_id=? WHERE user_id=?", (c["id"], me.id))
    db.commit()
    await reply(update, f"✅ {link(me.id, disp(me))} вступил(а) в клан «{esc(c['name'])}»")


async def _leave(update, me):
    c = clan_of(me.id)
    if not c:
        return await reply(update, "Ты не в клане")
    if c["owner"] == me.id:
        return await reply(update, "Глава не может выйти. Передай клан невозможно — только «клан распустить»")
    db.execute("UPDATE users SET clan_id=0 WHERE user_id=?", (me.id,))
    db.commit()
    await reply(update, f"Ты вышел из клана «{esc(c['name'])}»")


async def _deposit(update, me, arg):
    c = clan_of(me.id)
    if not c:
        return await reply(update, "Ты не в клане")
    if not arg.isdigit() or int(arg) < 1:
        return await reply(update, "Напиши: «клан вклад 100»")
    n = int(arg)
    if coins_of(me.id) < n:
        return await reply(update, f"Не хватает славКоинов, у тебя {coins_of(me.id)} {COIN}")
    give_coins(me.id, -n, commit=False)
    db.execute("UPDATE clans SET treasury=treasury+?, xp=xp+? WHERE id=?", (n, n, c["id"]))
    db.commit()
    c2 = get_clan(c["id"])
    await reply(update, f"💰 +{n} {COIN} в казну «{esc(c['name'])}». Казна {c2['treasury']}, уровень {clan_level(c2['xp'])}")


async def _kick(update, context, me, arg):
    c = clan_of(me.id)
    if not c or c["owner"] != me.id:
        return await reply(update, "Исключать может только глава клана")
    uid, name, _, err = resolve_target(update, arg.split())
    if err:
        return await reply(update, err)
    if not uid:
        return await reply(update, "Ответь на сообщение игрока или укажи @юзернейм")
    t = urow(uid)
    if not t or t["clan_id"] != c["id"] or uid == me.id:
        return await reply(update, "Этого игрока нет в твоём клане")
    db.execute("UPDATE users SET clan_id=0 WHERE user_id=?", (uid,))
    db.commit()
    await reply(update, f"{link(uid, name)} исключён(а) из клана «{esc(c['name'])}»")


async def _disband(update, me):
    c = clan_of(me.id)
    if not c or c["owner"] != me.id:
        return await reply(update, "Распустить может только глава")
    if active_war(c["id"]):
        return await reply(update, "Идёт война или вызов — дождись конца")
    give_coins(me.id, c["treasury"], commit=False)
    db.execute("UPDATE users SET clan_id=0 WHERE clan_id=?", (c["id"],))
    db.execute("DELETE FROM clans WHERE id=?", (c["id"],))
    db.commit()
    await reply(update, f"Клан «{esc(c['name'])}» распущен. Казна ({c['treasury']} {COIN}) вернулась главе")


async def _top(update):
    rows = db.execute("SELECT * FROM clans ORDER BY xp DESC, id LIMIT 10").fetchall()
    if not rows:
        return await reply(update, "Кланов пока нет. Создай первый: «клан создать Имя»")
    lines = ["🏆 <b>Топ кланов</b>"]
    for i, c in enumerate(rows, 1):
        lines.append(f"{i}. «{esc(c['name'])}» · ур. {clan_level(c['xp'])} · {len(members(c['id']))} чел. · "
                     f"казна {c['treasury']} {COIN}")
    await reply(update, "\n".join(lines))


async def _war_info(update, me):
    c = clan_of(me.id)
    w = active_war(c["id"]) if c else None
    if not w:
        return await reply(update,
                           f"Нет активной войны. Глава может бросить вызов: «клан война Имя 300» (ставка из казны). "
                           f"Война идёт {WAR_HOURS} ч. Очки: сообщение +{PTS_MSG}, смена +{PTS_SHIFT}, победа в игре +{PTS_WIN}")
    await reply(update, _war_line(w))


async def _war_declare(update, me, arg):
    c = clan_of(me.id)
    if not c or c["owner"] != me.id:
        return await reply(update, "Объявлять войну может только глава клана")
    parts = arg.split()
    if not parts:
        return await reply(update, "Напиши: «клан война Имя 300» (имя клана и ставка из казны)")
    stake = WAR_STAKE_DEFAULT
    if len(parts) > 1 and parts[-1].isdigit():
        stake = int(parts.pop())
    enemy = find_clan(" ".join(parts))
    if not enemy:
        return await reply(update, "Нет такого клана. Список: «кланы»")
    if enemy["id"] == c["id"]:
        return await reply(update, "Сам с собой воевать нельзя 🙃")
    if stake < 50:
        return await reply(update, "Минимальная ставка — 50")
    if active_war(c["id"]) or active_war(enemy["id"]):
        return await reply(update, "Один из кланов уже участвует в войне или вызове")
    if c["treasury"] < stake or enemy["treasury"] < stake:
        return await reply(update, f"В казне каждого клана должно быть минимум {stake} {COIN}")
    chat_id = update.effective_chat.id
    cur = db.execute("INSERT INTO wars(a,b,stake,chat_id,created) VALUES(?,?,?,?,?)",
                     (c["id"], enemy["id"], stake, chat_id, time.time()))
    db.commit()
    wid = cur.lastrowid
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ Принять", callback_data=f"cl:acc:{wid}"),
                                InlineKeyboardButton("🏳 Отказаться", callback_data=f"cl:dec:{wid}")]])
    owner = urow(enemy["owner"])
    await reply(update, f"⚔️ Клан «{esc(c['name'])}» вызывает «{esc(enemy['name'])}» на войну!\n"
                        f"Ставка: {stake} {COIN} с каждой казны, победитель забирает всё. {WAR_HOURS} ч. "
                        f"Очки: сообщение +{PTS_MSG}, смена +{PTS_SHIFT}, победа в игре +{PTS_WIN}.\n"
                        f"Ответить может глава «{esc(enemy['name'])}» — "
                        f"{link(enemy['owner'], owner['name'] if owner else '?')} ({WAR_PENDING_MIN} мин)",
                reply_markup=kb)


async def on_clan_btn(update, context):
    q = update.callback_query
    if not q.message or q.message.chat_id not in ALLOWED:
        return await q.answer()
    p = (q.data or "").split(":")
    if len(p) != 3 or not p[2].isdigit():
        return await q.answer()
    w = db.execute("SELECT * FROM wars WHERE id=? AND status='pending'", (int(p[2]),)).fetchone()
    if not w:
        return await q.answer("Вызов уже неактуален", show_alert=True)
    a, b = get_clan(w["a"]), get_clan(w["b"])
    if not a or not b or q.from_user.id != b["owner"]:
        return await q.answer("Отвечать может только глава вызванного клана", show_alert=True)
    if p[1] == "dec":
        db.execute("UPDATE wars SET status='cancel' WHERE id=?", (w["id"],))
        db.commit()
        await q.answer("Отказ")
        return await context.bot.send_message(q.message.chat_id, f"🏳 «{esc(b['name'])}» отказался от войны с «{esc(a['name'])}»", parse_mode="HTML")
    if a["treasury"] < w["stake"] or b["treasury"] < w["stake"]:
        db.execute("UPDATE wars SET status='cancel' WHERE id=?", (w["id"],))
        db.commit()
        return await q.answer("В казне не хватает на ставку, вызов отменён", show_alert=True)
    db.execute("UPDATE clans SET treasury=treasury-? WHERE id IN (?,?)", (w["stake"], a["id"], b["id"]))
    now = time.time()
    db.execute("UPDATE wars SET status='active', start=?, end=? WHERE id=?", (now, now + WAR_HOURS * 3600, w["id"]))
    db.commit()
    await q.answer("Война началась!")
    await context.bot.send_message(
        q.message.chat_id,
        f"⚔️ <b>Война началась!</b> «{esc(a['name'])}» против «{esc(b['name'])}»\n"
        f"Ставка {w['stake']} {COIN} с каждой стороны. Через {WAR_HOURS} ч победит клан с большим числом очков. "
        f"Пишите сообщения, выходите на смены, выигрывайте игры! Счёт: «война»", parse_mode="HTML")


async def clan_tick(bot):
    """Планировщик: отмена просроченных вызовов и подведение итогов войн."""
    now = time.time()
    db.execute("UPDATE wars SET status='cancel' WHERE status='pending' AND created<?", (now - WAR_PENDING_MIN * 60,))
    db.commit()
    for w in db.execute("SELECT * FROM wars WHERE status='active' AND end<=?", (now,)).fetchall():
        a, b = get_clan(w["a"]), get_clan(w["b"])
        db.execute("UPDATE wars SET status='done' WHERE id=?", (w["id"],))
        if not a or not b:
            db.commit()
            continue
        pot = w["stake"] * 2
        if w["sa"] == w["sb"]:
            db.execute("UPDATE clans SET treasury=treasury+? WHERE id IN (?,?)", (w["stake"], a["id"], b["id"]))
            res = "🤝 Ничья! Ставки возвращены в казны"
        else:
            win, lose = (a, b) if w["sa"] > w["sb"] else (b, a)
            db.execute("UPDATE clans SET treasury=treasury+?, xp=xp+? WHERE id=?", (pot, w["stake"], win["id"]))
            res = f"🏆 Побеждает «{esc(win['name'])}»! В казну +{pot} {COIN}"
        db.commit()
        try:
            await bot.send_message(w["chat_id"] or CHAT_ID,
                                   f"⚔️ <b>Война окончена</b>: «{esc(a['name'])}» {w['sa']} : {w['sb']} «{esc(b['name'])}»\n{res}",
                                   parse_mode="HTML")
        except Exception:
            log.exception("clan war result")
