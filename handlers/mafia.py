# -*- coding: utf-8 -*-
"""Мафия: лобби в чате, роли и ночные действия в личке, голосование в личке, картинки."""

import asyncio
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest, Forbidden

from config import ALLOWED, HTML
from core.helpers import reply
from core.logger import log
from core.ranks import has_rank
from core.utils import disp, esc, link, touch, today
from handlers.finance import _send_photo
from services.mafia import (KILL_TEXT, MAX_PLAYERS, MIN_PLAYERS, ROLES, Game)
from services.mafia_cards import end_card, phase_card, role_card

NIGHT_SEC, DISC_SEC, VOTE_SEC, HUNTER_SEC, LOBBY_SEC = 60, 75, 40, 30, 300
GAMES, CHAT_GAME = {}, {}
_next = [1]
B = InlineKeyboardButton


def _kb(rows):
    return InlineKeyboardMarkup(rows)


def _name(g, uid):
    return link(uid, g.players[uid].name)


def _short(name):
    return (name or "?")[:22]


async def dm(bot, uid, text, kb=None, photo=None):
    try:
        if photo is not None:
            await _send_photo((bot, uid), photo, text, reply_markup=kb)
        else:
            await bot.send_message(uid, text, parse_mode=HTML, reply_markup=kb)
        return True
    except Forbidden:
        return False
    except Exception as e:
        log.warning("mafia dm %s: %r", uid, e)
        return False


def _lobby_text(g):
    lines = ["🎭 <b>МАФИЯ</b> · набор игроков",
             f"Нужно от {MIN_PLAYERS} до {MAX_PLAYERS}. Роли придут в личку бота, ночью действуешь там же.",
             f"Режим хоррор (Джейсон Вурхис, Фредди Крюгер): {'🩸 включён' if g.horror else 'выключен'}", ""]
    for i, p in enumerate(g.players.values(), 1):
        lines.append(f"{i}. {link(p.uid, p.name)}" + (" 👑" if p.uid == g.host else ""))
    lines.append(f"\nИгроков: {len(g.players)}. Начать может хозяин игры 👑")
    return "\n".join(lines)


def _lobby_kb(g):
    return _kb([[B("✅ Играть", callback_data=f"maf:{g.gid}:join"), B("🚪 Выйти", callback_data=f"maf:{g.gid}:leave")],
                [B("▶️ Начать", callback_data=f"maf:{g.gid}:start"),
                 B("🩸 Хоррор вкл/выкл", callback_data=f"maf:{g.gid}:horror")],
                [B("✖️ Отменить", callback_data=f"maf:{g.gid}:cancel")]])


RULES = ("🎭 <b>Мафия: правила</b>\n"
         "Ночью мафия убивает, особые роли действуют в личке бота. Днём город обсуждает в чате и голосует в личке, "
         "кого повесить. Побеждает город, если убиты все злодеи; мафия — когда её не меньше, чем остальных; "
         "убийца-одиночка — если остаётся последним.\n\n<b>Роли</b>\n" +
         "\n".join(f"{v[1]} <b>{v[0]}</b> — {v[3]}" for v in ROLES.values()) +
         f"\n\nНачать: «мафия».")


async def handle_mafia_text(update, context, low, text):
    if update.effective_chat.id not in ALLOWED or not low.startswith("мафия"):
        return False
    me = update.effective_user
    touch(me)
    chat = update.effective_chat.id
    arg = low[5:].strip()
    if arg in ("правила", "роли", "помощь"):
        await reply(update, RULES)
        return True
    if arg in ("стоп", "отмена", "закончить"):
        g = GAMES.get(CHAT_GAME.get(chat))
        if not g:
            await reply(update, "Сейчас нет игры в мафию")
        elif me.id != g.host and not has_rank(me, "ban"):
            await reply(update, "Остановить может только хозяин игры или администрация")
        else:
            await _finish(context.bot, g, None, cancelled=True)
        return True
    if arg:
        return False
    if chat in CHAT_GAME:
        await reply(update, "Игра в этом чате уже идёт. Остановить: «мафия стоп»")
        return True
    g = Game(_next[0], chat, me.id, disp(me))
    _next[0] += 1
    if not await dm(context.bot, me.id, "✅ Ты создал(а) игру в мафию. Здесь будут приходить твои роль и ходы. "
                                        "Не блокируй бота!"):
        uname = (await context.bot.get_me()).username
        await reply(update, f"Сначала открой бота в личке и нажми Start: https://t.me/{uname}?start=mafia — "
                            "иначе я не смогу выслать роль. Потом напиши «мафия» ещё раз")
        return True
    GAMES[g.gid] = g
    CHAT_GAME[chat] = g.gid
    m = await update.effective_message.reply_text(_lobby_text(g), parse_mode=HTML, reply_markup=_lobby_kb(g))
    g.msg_id = m.message_id
    g.task = asyncio.create_task(_lobby_timeout(context.bot, g))
    return True


async def _lobby_timeout(bot, g):
    await asyncio.sleep(LOBBY_SEC)
    if g.phase == "lobby":
        await _finish(bot, g, None, cancelled=True, why="Время набора вышло")


async def _finish(bot, g, side, cancelled=False, why="Игра остановлена"):
    GAMES.pop(g.gid, None)
    CHAT_GAME.pop(g.chat_id, None)
    cur = asyncio.current_task()
    if g.task and g.task is not cur and not g.task.done():
        g.task.cancel()
    g.phase = "over"
    if cancelled:
        try:
            await bot.send_message(g.chat_id, f"🎭 {why}.", parse_mode=HTML)
        except Exception:
            pass
        return
    reveal = "\n".join(f"{ROLES[p.role][1]} {link(p.uid, p.name)} — {ROLES[p.role][0]}" + ("" if p.alive else " ☠️")
                       for p in g.players.values())
    winners = set(g.winners(side))
    names = ", ".join(link(u, g.players[u].name) for u in winners) or "—"
    await _send_photo((bot, g.chat_id), end_card(side),
                      f"🏁 <b>Игра окончена!</b> Победа: {'мафии' if side == 'mafia' else 'города' if side == 'town' else 'убийцы'}\n"
                      f"Победители: {names}\n\n<b>Роли</b>\n{reveal}")


# ---------------- лобби ----------------
async def on_mafia_btn(update, context):
    q = update.callback_query
    p = (q.data or "").split(":")
    if len(p) < 3 or not p[1].isdigit():
        return await q.answer()
    g = GAMES.get(int(p[1]))
    if not g:
        return await q.answer("Эта игра уже закончена", show_alert=True)
    u = q.from_user
    code = p[2]
    bot = context.bot
    if code in ("join", "leave", "start", "horror", "cancel"):
        if q.message and q.message.chat_id != g.chat_id:
            return await q.answer()
        return await _lobby_action(q, context, g, code, u)
    return await _game_action(q, context, g, code, p[3] if len(p) > 3 else None, u)


async def _lobby_action(q, context, g, code, u):
    if g.phase != "lobby":
        return await q.answer("Игра уже идёт", show_alert=True)
    touch(u)
    if code == "join":
        if u.id in g.players:
            return await q.answer("Ты уже в игре")
        if len(g.players) >= MAX_PLAYERS:
            return await q.answer("Мест нет", show_alert=True)
        if not await dm(context.bot, u.id, "✅ Ты в игре «Мафия». Роль придёт сюда."):
            return await q.answer("Сначала открой бота в личке и нажми Start, потом снова «Играть»", show_alert=True)
        g.add(u.id, disp(u))
        await q.answer("Ты в игре!")
    elif code == "leave":
        if not g.remove(u.id):
            return await q.answer("Хозяин не может выйти — отмени игру" if u.id == g.host else "Тебя нет в игре")
        await q.answer("Вышел")
    elif code in ("horror", "cancel", "start") and u.id != g.host and not has_rank(u, "ban"):
        return await q.answer("Это может только хозяин игры", show_alert=True)
    elif code == "horror":
        g.horror = not g.horror
        await q.answer("Хоррор " + ("включён" if g.horror else "выключен"))
    elif code == "cancel":
        await q.answer()
        return await _finish(context.bot, g, None, cancelled=True, why="Игра отменена")
    elif code == "start":
        if len(g.players) < MIN_PLAYERS:
            return await q.answer(f"Нужно минимум {MIN_PLAYERS} игроков", show_alert=True)
        await q.answer("Поехали!")
        if g.task and not g.task.done():
            g.task.cancel()
        g.start()
        g.started_at = time.time()
        try:
            await q.edit_message_text(f"🎭 <b>МАФИЯ</b> · игра началась! Игроков: {len(g.players)}. Роли разосланы в личку.",
                                      parse_mode=HTML)
        except BadRequest:
            pass
        g.task = asyncio.create_task(_run(context.bot, g))
        return
    try:
        await q.edit_message_text(_lobby_text(g), parse_mode=HTML, reply_markup=_lobby_kb(g))
    except BadRequest:
        pass


# ---------------- ход игры ----------------
def _targets_kb(g, code, ids, extra=None):
    rows, row = [], []
    for uid in ids:
        row.append(B(_short(g.players[uid].name), callback_data=f"maf:{g.gid}:{code}:{uid}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows + (extra or [])


NIGHT_PROMPT = {"mafia": ("k", "🔫 <b>Мафия.</b> Кого убьём этой ночью?"), "don": ("k", "🎩 <b>Дон.</b> Кого убьём этой ночью?"),
                "jason": ("j", "🪓 <b>Джейсон.</b> Чьё имя запишет твой топор?"),
                "freddy": ("f", "😈 <b>Фредди.</b> Чей сон нарушишь? Одного и того же две ночи подряд — смерть."),
                "comm": ("c", "🕵️ <b>Комиссар.</b> Кого проверить?"), "doc": ("d", "💉 <b>Доктор.</b> Кого лечить?"),
                "beauty": ("b", "💃 <b>Красотка.</b> Кого отвлечь этой ночью?")}


async def _send_night(bot, g):
    for uid in g.night_actors():
        p = g.players[uid]
        if p.role == "witch":
            rows = []
            if not p.heal_used:
                rows.append([B("💚 Спасти жертву мафии", callback_data=f"maf:{g.gid}:ws")])
            if not p.poison_used:
                rows += _targets_kb(g, "wp", g.targets_for(p))
            rows.append([B("⏭ Ничего не делать", callback_data=f"maf:{g.gid}:wn")])
            await dm(bot, uid, "🧙 <b>Ведьма.</b> Спасти жертву (если мафия кого-то выберет) или отравить (кнопка с именем):",
                     _kb(rows))
        else:
            code, text = NIGHT_PROMPT[p.role]
            await dm(bot, uid, text, _kb(_targets_kb(g, code, g.targets_for(p))))


async def _game_action(q, context, g, code, arg, u):
    bot = context.bot
    p = g.players.get(u.id)
    if not p or not p.alive:
        return await q.answer("Ты не участвуешь или уже выбыл", show_alert=True)
    tgt = int(arg) if arg and arg.lstrip("-").isdigit() else None
    if code in ("k", "j", "f", "c", "d", "b", "wp", "ws", "wn"):
        if g.phase != "night":
            return await q.answer("Сейчас не ночь", show_alert=True)
        ok = g.set_action(u.id, code, tgt if code not in ("ws", "wn") else 0)
        if not ok:
            return await q.answer("Так нельзя", show_alert=True)
        label = {"ws": "💚 Ты спасёшь жертву мафии", "wn": "⏭ Ты ничего не делаешь"}.get(code) or (
            f"✅ Выбор принят: {g.players[tgt].name}")
        try:
            await q.edit_message_text(label)
        except BadRequest:
            pass
        await q.answer("Принято")
        if code == "k":                                 # сообщаем своим
            for m in g.mafia_team():
                if m.uid != u.id:
                    await dm(bot, m.uid, f"🔫 {esc(p.name)} предлагает убить: <b>{esc(g.players[tgt].name)}</b>")
        if all(a in g.actions for a in g.night_actors()) and g.night_ev:
            g.night_ev.set()
        return
    if code in ("v", "vs"):
        if g.phase != "vote":
            return await q.answer("Сейчас не голосование", show_alert=True)
        if not g.set_vote(u.id, tgt if code == "v" else 0):
            return await q.answer("Так нельзя", show_alert=True)
        try:
            await q.edit_message_text("🗳 Ты проголосовал(а) против: " + (esc(g.players[tgt].name) if code == "v" else "никого (воздержался)"),
                                      parse_mode=HTML)
        except BadRequest:
            pass
        await q.answer("Голос принят")
        if all(a in g.votes for a in g.alive_ids()) and g.vote_ev:
            g.vote_ev.set()
        return
    if code == "h":
        if u.id not in g.hunter_pending:
            return await q.answer("Выстрел уже сделан", show_alert=True)
        if tgt not in g.alive_ids():
            return await q.answer("Цель недоступна", show_alert=True)
        g.hunter_choice[u.id] = tgt
        try:
            await q.edit_message_text("🏹 Выстрел сделан!")
        except BadRequest:
            pass
        await q.answer()
        if g.hunter_ev:
            g.hunter_ev.set()
        return
    await q.answer()


async def _hunters(bot, g, hunters):
    """Мёртвые охотники стреляют. hunters: uid мёртвых охотников."""
    out = []
    for h in hunters:
        if not g.alive_ids():
            break
        g.hunter_pending, g.hunter_choice = [h], {}
        g.hunter_ev = asyncio.Event()
        await dm(bot, h, "🏹 <b>Тебя убили!</b> Успей выстрелить напоследок:",
                 _kb(_targets_kb(g, "h", [u for u in g.alive_ids() if u != h])))
        try:
            await asyncio.wait_for(g.hunter_ev.wait(), HUNTER_SEC)
        except asyncio.TimeoutError:
            pass
        t = g.hunter_choice.get(h)
        g.hunter_pending = []
        if t and g.kill(t):
            out.append(t)
            await bot.send_message(g.chat_id, KILL_TEXT["hunter"].format(n=_name(g, t), r=ROLES[g.players[t].role][0]),
                                   parse_mode=HTML)
            if g.players[t].role == "hunter":
                out += await _hunters(bot, g, [t])
    return out


async def _run(bot, g):
    try:
        for p in g.players.values():
            team = ""
            if p.team == "mafia":
                mates = [x for x in g.players.values() if x.team == "mafia" and x.uid != p.uid]
                team = "\nТвоя команда: " + (", ".join(esc(x.name) + f" ({ROLES[x.role][0]})" for x in mates) or "ты один(а)")
            await dm(bot, p.uid, f"🎭 Игра началась! Ты — <b>{ROLES[p.role][1]} {ROLES[p.role][0]}</b>.{team}",
                     photo=role_card(p.role))
        await bot.send_message(g.chat_id, "🎭 Роли разосланы в личку. Первая ночь…", parse_mode=HTML)
        while True:
            # ---------- ночь ----------
            g.phase, g.actions, g.night_ev = "night", {}, asyncio.Event()
            await _send_photo((bot, g.chat_id), phase_card("night", g.day),
                              f"🌙 <b>Ночь {g.day}.</b> Город засыпает. Действуй в личке с ботом ({NIGHT_SEC} сек).")
            await _send_night(bot, g)
            try:
                await asyncio.wait_for(g.night_ev.wait(), NIGHT_SEC)
            except asyncio.TimeoutError:
                pass
            res = g.resolve_night()
            for uid, txt in res["checks"].items():
                await dm(bot, uid, txt)
            lines = ["🌅 <b>Наступило утро.</b>"]
            dead = []
            for uid, cause in res["deaths"]:
                lines.append(KILL_TEXT[cause].format(n=_name(g, uid), r=ROLES[g.players[uid].role][0]))
                dead.append(uid)
            if not res["deaths"]:
                lines.append("Эта ночь прошла спокойно, никто не погиб.")
            if "saved" in res["notes"]:
                lines.append("💉 Кого-то спасли от гибели!")
            hunters = [u for u in dead if g.players[u].role == "hunter"]
            await _send_photo((bot, g.chat_id), phase_card("day", g.day), "\n".join(lines))
            if hunters:
                dead += await _hunters(bot, g, hunters)
            side = g.winner()
            if side:
                return await _finish(bot, g, side)
            # ---------- день ----------
            g.phase = "day"
            alive = ", ".join(_name(g, u) for u in g.alive_ids())
            await bot.send_message(g.chat_id, f"☀️ <b>День {g.day}.</b> Обсуждайте ({DISC_SEC} сек). Живы ({len(g.alive_ids())}): {alive}",
                                   parse_mode=HTML)
            await asyncio.sleep(DISC_SEC)
            # ---------- голосование ----------
            g.phase, g.votes, g.vote_ev = "vote", {}, asyncio.Event()
            await bot.send_message(g.chat_id, f"🗳 <b>Голосование.</b> Бот прислал вам кнопки в личку ({VOTE_SEC} сек).", parse_mode=HTML)
            for uid in g.alive_ids():
                rows = _targets_kb(g, "v", [u for u in g.alive_ids() if u != uid], [[B("⏭ Воздержаться", callback_data=f"maf:{g.gid}:vs")]])
                await dm(bot, uid, "🗳 <b>Кого повесим?</b>", _kb(rows))
            try:
                await asyncio.wait_for(g.vote_ev.wait(), VOTE_SEC)
            except asyncio.TimeoutError:
                pass
            voted = len(g.votes)
            lynched, spared = g.resolve_vote()
            if spared:
                await bot.send_message(g.chat_id, f"🪓 Петля не удержала {_name(g, spared)}! Это <b>Джейсон Вурхис</b> — он вырвался и скрылся во тьме…", parse_mode=HTML)
            elif lynched:
                await bot.send_message(g.chat_id, KILL_TEXT["lynch"].format(n=_name(g, lynched), r=ROLES[g.players[lynched].role][0]), parse_mode=HTML)
                if g.players[lynched].role == "hunter":
                    await _hunters(bot, g, [lynched])
            else:
                await bot.send_message(g.chat_id, f"🤷 Мнения разошлись (проголосовало {voted}), никого не повесили.", parse_mode=HTML)
            side = g.winner()
            if side:
                return await _finish(bot, g, side)
            g.day += 1
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("mafia run")
        try:
            await bot.send_message(g.chat_id, "🎭 В игре произошла ошибка, она остановлена.")
        except Exception:
            pass
        GAMES.pop(g.gid, None)
        CHAT_GAME.pop(g.chat_id, None)
