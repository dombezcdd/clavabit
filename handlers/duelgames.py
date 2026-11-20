# -*- coding: utf-8 -*-
"""Дуэли без ставок: на выстрелах (патроны/укрытие) и камень-ножницы-бумага. Ходы скрытые, кнопками."""

import asyncio
import random
import time

from telegram import InlineKeyboardButton as B, InlineKeyboardMarkup

from config import HTML
from core.logger import log
from core.utils import esc, link, urow
from database.db import db

ROUND_SEC = 30
HP, AMMO_MAX, MAX_ROUNDS = 3, 3, 12
GAMES = {}
_next = [1]
MOVES = {"s": "🔫 выстрел", "b": "🛡 укрытие", "r": "🔄 перезарядка"}
RPS = {"k": "✊ камень", "n": "✌️ ножницы", "p": "✋ бумага"}
RPS_WIN = {("k", "n"), ("n", "p"), ("p", "k")}


class G:
    def __init__(self, kind, chat, a, b):
        self.gid = _next[0]
        _next[0] += 1
        self.kind, self.chat, self.ids = kind, chat, (a, b)
        self.name = {a: urow(a)["name"], b: urow(b)["name"]}
        self.hp = {a: HP, b: HP}
        self.ammo = {a: 0, b: 0}
        self.prev = {a: "", b: ""}
        self.wins = {a: 0, b: 0}
        self.choice = {}
        self.round = 0
        self.msg = None
        self.ev = None
        self.idle = 0
        self.log = ""
        self.photo = False
        self.cardev = []
        self.hitd = {}


def _kb(g):
    if g.kind == "shoot":
        row = [B(v, callback_data=f"dg:{g.gid}:{k}") for k, v in MOVES.items()]
    else:
        row = [B(v, callback_data=f"dg:{g.gid}:{k}") for k, v in RPS.items()]
    return InlineKeyboardMarkup([row])


def _status(g):
    a, b = g.ids
    if g.kind == "shoot":
        def line(u):
            return (f"👤 {link(u, g.name[u])}\n    ❤️ жизни: {'❤️' * g.hp[u]}{'🖤' * (HP - g.hp[u])}   🔫 патроны: {'🔸' * g.ammo[u]}{'▫️' * (AMMO_MAX - g.ammo[u])}")
        return line(a) + "\n" + line(b)
    return f"{link(a, g.name[a])}: {g.wins[a]}  ·  {link(b, g.name[b])}: {g.wins[b]}  (до 2 побед)"


def _ready(g):
    return " · ".join(f"{esc(g.name[u])} {'✅' if u in g.choice else '⏳'}" for u in g.ids)


def _text(g):
    title = "🔫 <b>Дуэль на выстрелах</b>" if g.kind == "shoot" else "✊ <b>Камень-ножницы-бумага</b>"
    if g.kind == "shoot":
        hint = ("<b>Твой ход</b> (выбирай скрытно, соперник не видит):\n"
                "🔫 Выстрел: нужен патрон, отнимает 1 ❤️ у соперника\n"
                "🛡 Укрытие: защищает от выстрела (два раза подряд не работает)\n"
                "🔄 Перезарядка: +1 патрон")
    else:
        hint = "<b>Твой ход:</b> выбери кнопкой, соперник не видит твой выбор."
    last = f"📋 <b>Что было в прошлом раунде:</b>\n{g.log}\n\n" if g.log and g.log.strip() else ""
    if g.photo:      # жизни, патроны и итог раунда уже нарисованы на картинке
        return f"{title} · раунд {g.round}\n\n{hint}\n\nВыбрали: {_ready(g)}\n⏱ {ROUND_SEC} сек на ход"
    return (f"{title} · раунд {g.round}\n\n{_status(g)}\n\n{last}{hint}\n\n"
            f"Выбрали: {_ready(g)}\n⏱ {ROUND_SEC} сек на ход")


def _card(g, winner=None):
    from services.duel_card import duel_card
    a, b = g.ids
    pl = [dict(name=g.name[u], hp=max(0, g.hp[u]), ammo=g.ammo[u], hit=g.hitd.get(u, False)) for u in g.ids]
    wi = None if winner is None else (0 if winner == a else 1)
    return duel_card(pl, g.round, g.cardev, wi, HP, AMMO_MAX)


async def _show_card(bot, g, text, kb, winner=None, alt=None):
    """Правим картинку дуэли (edit_media). Если не вышло, переходим на обычный текст."""
    from telegram import InputMediaPhoto
    try:
        buf = await asyncio.to_thread(_card, g, winner)
        await bot.edit_message_media(chat_id=g.chat, message_id=g.msg,
                                     media=InputMediaPhoto(buf, caption=text[:1024], parse_mode=HTML), reply_markup=kb)
        return
    except Exception as e:
        log.warning("duel card edit: %r", e)
    g.photo = False
    await _show(bot, g, alt or _text(g), kb)


async def _show(bot, g, text, kb):
    try:
        if g.photo:
            await bot.edit_message_caption(chat_id=g.chat, message_id=g.msg, caption=text[:1024], parse_mode=HTML, reply_markup=kb)
        else:
            await bot.edit_message_text(text, chat_id=g.chat, message_id=g.msg, parse_mode=HTML, reply_markup=kb)
    except Exception as e:
        if "not modified" in str(e).lower():
            return
        g.photo = False
        try:
            m = await bot.send_message(g.chat, text, parse_mode=HTML, reply_markup=kb)
            g.msg = m.message_id
        except Exception:
            log.exception("duel show")


async def start(bot, kind, chat, a, b):
    g = G(kind, chat, a, b)
    GAMES[g.gid] = g
    g.round = 1
    m = None
    if kind == "shoot":
        try:
            g.photo = True
            buf = await asyncio.to_thread(_card, g)
            m = await bot.send_photo(chat, buf, caption=_text(g)[:1024], parse_mode=HTML, reply_markup=_kb(g),
                                     read_timeout=25, write_timeout=25)
        except Exception as e:
            log.warning("duel card send: %r", e)
            g.photo = False
            m = None
    if m is None:
        m = await bot.send_message(chat, _text(g), parse_mode=HTML, reply_markup=_kb(g))
    g.msg = m.message_id
    g.task = asyncio.create_task(_loop(bot, g))


def _finish_stats(win, lose):
    if win:
        db.execute("UPDATE users SET game_pts=game_pts+2, duel_w=duel_w+1 WHERE user_id=?", (win,))
        db.execute("UPDATE users SET duel_l=duel_l+1 WHERE user_id=?", (lose,))
        db.commit()


async def _end(bot, g, text, win=None):
    GAMES.pop(g.gid, None)
    lose = next((u for u in g.ids if u != win), None) if win else None
    _finish_stats(win, lose)
    if win:
        from services.xp import quest_hit
        await quest_hit(bot, win, "duelw", g.chat)
    extra = f"\n\n🏆 Победил {link(win, g.name[win])}! (+2 игровых очка)" if win else "\n\n🤝 Ничья, очки не выдаются"
    if g.photo and g.kind == "shoot":
        await _show_card(bot, g, f"🔫 <b>Дуэль на выстрелах</b> · итог{extra}", None, winner=win, alt=text + extra)
    else:
        await _show(bot, g, text + extra, None)
    try:
        from handlers.duel import played
        for u in g.ids:
            await played(bot, u)
    except Exception:
        log.exception("duel played")


def _resolve_shoot(g):
    a, b = g.ids
    ch = {u: g.choice.get(u) for u in g.ids}
    why = {}
    for u in g.ids:
        c = ch[u] or "r"
        if ch[u] is None:
            why[u] = "⏰ не успел выбрать, значит перезаряжается"
        if c == "b" and g.prev[u] == "b":
            why[u] = "⚠️ укрытие два раза подряд не работает, ход потерян"
            c = "x"
        if c == "s" and g.ammo[u] < 1:
            why[u] = "⚠️ патронов нет, выстрела не вышло, ход потерян"
            c = "x"
        ch[u] = c
    for u in g.ids:
        if ch[u] == "r":
            g.ammo[u] = min(AMMO_MAX, g.ammo[u] + 1)
        elif ch[u] == "s":
            g.ammo[u] -= 1
    res = {}
    for u in g.ids:
        o = b if u == a else a
        if ch[u] == "s":
            if ch[o] == "b":
                res[u] = f"🔫 стреляет, но {esc(g.name[o])} в укрытии: мимо"
            else:
                g.hp[o] -= 1
                res[u] = f"💥 стреляет и попадает: у {esc(g.name[o])} −1 ❤️"
        elif ch[u] == "b":
            res[u] = "🛡 прячется в укрытии"
        elif ch[u] == "r":
            res[u] = "🔄 перезаряжается (+1 патрон)"
    for u in g.ids:
        g.prev[u] = ch[u] if ch[u] != "x" else ""
    g.cardev, g.hitd = [], {}
    for u in g.ids:
        o = b if u == a else a
        nm = g.name[u]
        if ch[u] == "s":
            if ch[o] == "b":
                t = "стреляет, но соперник в укрытии: мимо"
            else:
                t = "стреляет и попадает: −1 жизнь сопернику"
                g.hitd[o] = True
        elif ch[u] == "b":
            t = "прячется в укрытии"
        elif ch[u] == "r":
            t = "не успел выбрать, перезаряжается" if u in why and "успел" in why[u] else "перезаряжается (+1 патрон)"
        else:
            t = "ход потерян: " + ("нет патронов" if "патрон" in why.get(u, "") else "укрытие два раза подряд")
        g.cardev.append((ch[u], f"{nm}: {t}"))
    out = []
    for u in g.ids:
        parts = ([why[u]] if u in why else []) + ([res[u]] if ch[u] != "x" and u in res else [])
        out.append(f"• {esc(g.name[u])}: " + "; ".join(parts))
    return "\n".join(out)


def _resolve_rps(g):
    a, b = g.ids
    ca, cb = g.choice.get(a), g.choice.get(b)
    head = " vs ".join(f"{esc(g.name[u])} {RPS[g.choice[u]]}" if u in g.choice else f"{esc(g.name[u])} не успел" for u in g.ids)
    if ca and cb:
        if ca == cb:
            return head + "\n🤝 Ничья в раунде"
        w = a if (ca, cb) in RPS_WIN else b
    elif ca or cb:
        w = a if ca else b
    else:
        return head
    g.wins[w] += 1
    return head + f"\n✅ Раунд за {esc(g.name[w])}"


async def _loop(bot, g):
    try:
        while True:
            g.choice = {}
            g.ev = asyncio.Event()
            try:
                await asyncio.wait_for(g.ev.wait(), ROUND_SEC)
            except asyncio.TimeoutError:
                pass
            if not g.choice:
                g.idle += 1
                if g.idle >= 2:
                    GAMES.pop(g.gid, None)
                    return await _show(bot, g, "⌛ Дуэль сорвалась: никто не ходил. Очки не выданы.", None)
            else:
                g.idle = 0
            a, b = g.ids
            if g.kind == "shoot":
                g.log = _resolve_shoot(g)
                if g.hp[a] <= 0 and g.hp[b] <= 0:
                    return await _end(bot, g, _text_end(g), None)
                if g.hp[a] <= 0 or g.hp[b] <= 0:
                    return await _end(bot, g, _text_end(g), b if g.hp[a] <= 0 else a)
                if g.round >= MAX_ROUNDS:
                    win = a if g.hp[a] > g.hp[b] else b if g.hp[b] > g.hp[a] else None
                    return await _end(bot, g, _text_end(g, "Раунды кончились."), win)
            else:
                g.log = _resolve_rps(g)
                if g.wins[a] >= 2 or g.wins[b] >= 2 or g.round >= 6:
                    win = a if g.wins[a] > g.wins[b] else b if g.wins[b] > g.wins[a] else None
                    return await _end(bot, g, _text_end(g), win)
            g.round += 1
            if g.photo and g.kind == "shoot":
                await _show_card(bot, g, _text(g), _kb(g))
            else:
                await _show(bot, g, _text(g), _kb(g))
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("duel loop")
        GAMES.pop(g.gid, None)


def _text_end(g, extra=""):
    title = "🔫 <b>Дуэль на выстрелах</b>" if g.kind == "shoot" else "✊ <b>Камень-ножницы-бумага</b>"
    return f"{title} · итог\n{_status(g)}\n\n{g.log}\n{extra}"


async def on_duelgame_btn(update, context):
    q = update.callback_query
    p = (q.data or "").split(":")
    if len(p) != 3 or not p[1].isdigit():
        return await q.answer()
    g = GAMES.get(int(p[1]))
    if not g:
        return await q.answer("Эта дуэль уже закончилась", show_alert=True)
    u = q.from_user.id
    if u not in g.ids:
        return await q.answer("Это не твоя дуэль", show_alert=True)
    mv = p[2]
    if mv not in (MOVES if g.kind == "shoot" else RPS):
        return await q.answer()
    if u in g.choice:
        return await q.answer("Ход уже сделан, ждём соперника")
    g.choice[u] = mv
    name = (MOVES if g.kind == "shoot" else RPS)[mv]
    await q.answer(f"Твой ход: {name}")
    if len(g.choice) == 2 and g.ev:
        g.ev.set()
    else:
        await _show(context.bot, g, _text(g), _kb(g))
