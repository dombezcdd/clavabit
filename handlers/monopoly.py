# -*- coding: utf-8 -*-
"""Монополия в чате: лобби, ходы по кнопкам, поле картинкой. Награды нет, ведётся рейтинг побед («топ игр»)."""

import asyncio
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.error import NetworkError, TimedOut

from config import ALLOWED, HTML, MONO_IDLE_END, MONO_MAX_PLAYERS, MONO_MAX_ROUNDS, MONO_TURN_TIMEOUT
from core.helpers import group_only, reply
from core.logger import log
from core.utils import esc, is_owner, link
from database.db import db
from handlers.duel import played
from services.monopoly import JAIL_FINE, TILES, Game
from services.monopoly_board import render

MONO_WORDS = {"монополия", "играть в монополию", "монополию", "monopoly"}
MONO_STOP_WORDS = {"стоп монополия", "закончить монополию", "остановить монополию"}
BOT_NAMES = ["Макс", "Лиза", "Гоша", "Соня", "Артём"]
MONO_GAMES = {}     # chat_id -> {"state": "lobby"|"play", host, players, msg_id, game, lock, log, menu, last_cur, last_act}


def _name(u):
    n = (u.full_name or u.first_name or str(u.id)).strip()
    return n if len(n) <= 16 else n[:15] + "…"


def _lobby_text(e):
    rows = [f"{i + 1}. " + (link(p[0], p[1]) if p[2] else esc(p[1]) + " (бот)") for i, p in enumerate(e["players"])]
    return ("🎩 <b>Монополия</b>: набор игроков\n"
            f"Игроков: {len(e['players'])} из {MONO_MAX_PLAYERS}\n" + "\n".join(rows) +
            f"\n\nНачнёт игру {link(e['host'], e['host_name'])}. Можно добавить ботов. "
            f"Партия идёт до {MONO_MAX_ROUNDS} кругов, побеждает последний неразорённый или самый богатый.")


def _lobby_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Присоединиться", callback_data="mono:join"),
         InlineKeyboardButton("➖ Выйти", callback_data="mono:leave")],
        [InlineKeyboardButton("🤖 Добавить бота", callback_data="mono:bot"),
         InlineKeyboardButton("▶️ Начать", callback_data="mono:start")],
        [InlineKeyboardButton("✖ Отменить", callback_data="mono:cancel")],
    ])


def _game_kb(e):
    g = e["game"]
    p = g.cur()
    rows = []
    if g.phase == "roll" and e.get("menu"):
        for i in g.build_options(p.id)[:8]:
            rows.append([InlineKeyboardButton(f"🏠 {TILES[i]['n']} (−${g.house_cost(i)}, домов {g.houses.get(i, 0)})",
                                              callback_data=f"mono:b:{i}")])
        rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="mono:back")])
    elif g.phase == "roll":
        rows.append([InlineKeyboardButton("🎲 Бросить кубики", callback_data="mono:roll")])
        if g.build_options(p.id):
            rows.append([InlineKeyboardButton("🏠 Строить дома", callback_data="mono:build")])
    elif g.phase == "buy":
        t = TILES[g.pending]
        rows.append([InlineKeyboardButton(f"💰 Купить −${t['p']}", callback_data="mono:buy"),
                     InlineKeyboardButton("Пропустить", callback_data="mono:skip")])
    elif g.phase == "jail":
        rows.append([InlineKeyboardButton(f"💵 Выйти −${JAIL_FINE}", callback_data="mono:jpay"),
                     InlineKeyboardButton("🎲 Бросить на дубль", callback_data="mono:jroll")])
    if g.phase != "over":
        rows.append([InlineKeyboardButton("🚪 Выйти из игры", callback_data="mono:quit")])
    return InlineKeyboardMarkup(rows) if rows else None


def _caption(e):
    g = e["game"]
    cur = g.cur()
    lines = [f"🎩 <b>Монополия</b> · круг {min(g.round, g.max_rounds)} из {g.max_rounds}"]
    if g.phase != "over":
        who = link(cur.id, cur.name) if cur.human else esc(cur.name)
        hint = {"roll": "бросай кубики", "buy": f"купить «{TILES[g.pending]['n']}» за ${TILES[g.pending]['p']}?" if g.pending is not None else "",
                "jail": "ты в тюрьме: заплати или брось на дубль"}.get(g.phase, "")
        if e.get("menu"):
            hint = "выбери, где построить дом"
        lines.append(f"Ходит: {who}, {hint}")
    lines.append("")
    lines += [esc(x) for x in e["log"][-7:]]
    return "\n".join(lines)[:1000]


SLOW = dict(read_timeout=40, write_timeout=40, connect_timeout=20, pool_timeout=20)   # картинки грузятся дольше обычных запросов


async def _send_board(bot, chat_id, data, cap, kb):
    """Отправляет поле. При таймауте повторяет, в крайнем случае шлёт только текст с кнопками, чтобы игра не зависла."""
    for attempt in range(3):
        try:
            return await bot.send_photo(chat_id, data, caption=cap, parse_mode=HTML, reply_markup=kb, **SLOW)
        except (TimedOut, NetworkError) as ex:
            log.warning("mono send_photo (%s): %r", attempt + 1, ex)
            await asyncio.sleep(1.5)
    return await bot.send_message(chat_id, cap + "\n\n(картинка не загрузилась)", parse_mode=HTML, reply_markup=kb)


async def _refresh(bot, chat_id, e, new_msg=None):
    """Обновляет картинку и кнопки. Когда ход переходит к другому игроку, отправляет поле заново (внизу чата, с пингом)."""
    g = e["game"]
    e["log"] = (e["log"] + g.take_events())[-14:]
    data = (await asyncio.to_thread(render, g, e["log"][-9:])).getvalue()   # в потоке, чтобы не тормозить бота
    cap, kb = _caption(e), _game_kb(e)
    cur_id = g.cur().id
    fresh = new_msg if new_msg is not None else (e["last_cur"] != cur_id or g.phase == "over")
    e["last_cur"] = cur_id
    if not fresh and e.get("msg_id"):
        try:
            await bot.edit_message_media(chat_id, e["msg_id"], InputMediaPhoto(data, caption=cap, parse_mode=HTML),
                                         reply_markup=kb, **SLOW)
            return
        except Exception as ex:
            if "not modified" in str(ex).lower():
                return
            log.warning("mono edit: %r", ex)
    old = e.get("msg_id")
    m = await _send_board(bot, chat_id, data, cap, kb)
    e["msg_id"] = m.message_id
    if old:
        try:
            await bot.delete_message(chat_id, old)
        except Exception:
            pass


async def _finish(bot, chat_id, e):
    g = e["game"]
    w = g.winner
    humans = [p for p in g.players if p.human]
    if w and w.human:
        db.execute("INSERT INTO game_wins(user_id,wins) VALUES(?,1) ON CONFLICT(user_id) DO UPDATE SET wins=wins+1", (w.id,))
        db.commit()
    e["log"].append("Итог: " + ", ".join(f"{p.name} {'банкрот' if p.dead else '$' + str(round(g.worth(p)))}" for p in g.players))
    await _refresh(bot, chat_id, e, new_msg=True)
    MONO_GAMES.pop(chat_id, None)
    for p in humans:
        try:
            await played(bot, p.id)
        except Exception:
            log.exception("mono played")


async def _advance(bot, chat_id, e):
    """Ходы ботов, проверка конца игры и обновление сообщения."""
    g = e["game"]
    g.last_act = time.time()
    g.run_bots()
    g.settle()
    if g.phase == "over":
        return await _finish(bot, chat_id, e)
    await _refresh(bot, chat_id, e)


# ============================ ЗАПУСК И КНОПКИ ============================


async def _open_lobby(update, context):
    chat_id = update.effective_chat.id
    me = update.effective_user
    if chat_id in MONO_GAMES:
        return await reply(update, "В этом чате уже идёт набор или партия в Монополию. Остановить: «стоп монополия».")
    e = {"state": "lobby", "host": me.id, "host_name": _name(me), "players": [(me.id, _name(me), True)],
         "msg_id": None, "game": None, "lock": asyncio.Lock(), "log": [], "menu": False, "last_cur": None,
         "last_act": time.time()}
    m = await update.effective_message.reply_text(_lobby_text(e), parse_mode=HTML, reply_markup=_lobby_kb())
    e["msg_id"] = m.message_id
    MONO_GAMES[chat_id] = e


@group_only
async def cmd_monopoly(update, context):
    await _open_lobby(update, context)


async def handle_monopoly_text(update, context, clean):
    if clean in MONO_WORDS:
        await _open_lobby(update, context)
        return True
    if clean in MONO_STOP_WORDS:
        chat_id = update.effective_chat.id
        e = MONO_GAMES.get(chat_id)
        me = update.effective_user
        if not e:
            await reply(update, "Сейчас нет Монополии.")
        elif me.id == e["host"] or is_owner(me):
            async with e["lock"]:
                await _stop(context.bot, chat_id, e, "Партия остановлена")
        else:
            await reply(update, "Остановить партию может тот, кто её создал.")
        return True
    return False


async def _stop(bot, chat_id, e, why):
    MONO_GAMES.pop(chat_id, None)
    try:
        if e["state"] == "lobby":
            await bot.edit_message_text(f"🎩 Монополия: {why.lower()}.", chat_id, e["msg_id"])
        else:
            await bot.send_message(chat_id, f"🎩 Монополия: {why.lower()}.")
            if e.get("msg_id"):
                await bot.edit_message_reply_markup(chat_id, e["msg_id"], reply_markup=None)
    except Exception:
        pass


async def on_mono_btn(update, context):
    q = update.callback_query
    chat_id = q.message.chat_id
    if chat_id not in ALLOWED:
        return await q.answer()
    parts = (q.data or "").split(":")
    act = parts[1] if len(parts) > 1 else ""
    e = MONO_GAMES.get(chat_id)
    if not e or q.message.message_id != e.get("msg_id"):
        return await q.answer("Это старое сообщение. Игра закончилась или идёт в новом сообщении.", show_alert=True)
    me = q.from_user
    async with e["lock"]:
        if MONO_GAMES.get(chat_id) is not e:
            return await q.answer("Игра уже закончилась.", show_alert=True)
        if e["state"] == "lobby":
            return await _lobby_action(context.bot, q, chat_id, e, act, me)
        return await _game_action(context.bot, q, chat_id, e, act, parts, me)


async def _lobby_action(bot, q, chat_id, e, act, me):
    pl = e["players"]
    host = me.id == e["host"] or is_owner(me)
    if act == "join":
        if any(p[0] == me.id for p in pl):
            return await q.answer("Ты уже в игре.")
        if len(pl) >= MONO_MAX_PLAYERS:
            return await q.answer("Мест нет.", show_alert=True)
        pl.append((me.id, _name(me), True))
    elif act == "leave":
        if me.id == e["host"]:
            return await q.answer("Ты создатель. Чтобы отменить, нажми «Отменить».", show_alert=True)
        if not any(p[0] == me.id for p in pl):
            return await q.answer("Тебя нет в списке.")
        e["players"] = [p for p in pl if p[0] != me.id]
    elif act == "bot":
        if not host:
            return await q.answer("Ботов добавляет создатель игры.", show_alert=True)
        if len(pl) >= MONO_MAX_PLAYERS:
            return await q.answer("Мест нет.", show_alert=True)
        k = sum(1 for p in pl if not p[2])
        pl.append((-(k + 1), BOT_NAMES[k % len(BOT_NAMES)], False))
    elif act == "cancel":
        if not host:
            return await q.answer("Отменить может создатель игры.", show_alert=True)
        await q.answer()
        return await _stop(bot, chat_id, e, "Набор отменён")
    elif act == "start":
        if not host:
            return await q.answer("Начать может создатель игры.", show_alert=True)
        if len(pl) < 2:
            return await q.answer("Нужно минимум два игрока: добавь участника или бота.", show_alert=True)
        await q.answer("Поехали!")
        try:
            await bot.delete_message(chat_id, e["msg_id"])
        except Exception:
            pass
        e["state"], e["msg_id"] = "play", None
        e["game"] = Game(list(pl), max_rounds=MONO_MAX_ROUNDS)
        e["game"].say("Игра началась! У каждого по $1500")
        return await _advance(bot, chat_id, e)
    else:
        return await q.answer()
    await q.answer()
    e["last_act"] = time.time()
    await q.edit_message_text(_lobby_text(e), parse_mode=HTML, reply_markup=_lobby_kb())


async def _game_action(bot, q, chat_id, e, act, parts, me):
    g = e["game"]
    if act == "quit":
        p = g.by_id(me.id)
        if not p or p.dead:
            return await q.answer("Ты не в игре.", show_alert=True)
        await q.answer("Ты вышел из игры.")
        g.forfeit(me.id)
        e["menu"] = False
        return await _advance(bot, chat_id, e)
    cur = g.cur()
    if me.id != cur.id:
        return await q.answer(f"Сейчас ходит {cur.name}.", show_alert=True)
    cur.skips = 0
    phase = g.phase
    if act == "roll" and phase == "roll":
        e["menu"] = False
        g.act_roll()
    elif act == "buy" and phase == "buy":
        g.act_buy(True)
    elif act == "skip" and phase == "buy":
        g.act_buy(False)
    elif act == "jpay" and phase == "jail":
        g.act_jail(True)
    elif act == "jroll" and phase == "jail":
        g.act_jail(False)
    elif act == "build" and phase == "roll":
        e["menu"] = True
    elif act == "back":
        e["menu"] = False
    elif act == "b" and phase == "roll" and len(parts) > 2 and parts[2].isdigit():
        if g.act_build(me.id, int(parts[2])):
            await q.answer("Дом построен")
        else:
            await q.answer("Сейчас здесь строить нельзя.", show_alert=True)
        if not g.build_options(me.id):
            e["menu"] = False
        return await _advance(bot, chat_id, e)
    else:
        return await q.answer("Это действие уже недоступно.")
    await q.answer()
    await _advance(bot, chat_id, e)


# ============================ ТАЙМАУТЫ (вызывается планировщиком) ============================


async def monopoly_tick(bot):
    t = time.time()
    for chat_id, e in list(MONO_GAMES.items()):
        try:
            if e["state"] == "lobby":
                if t - e["last_act"] > 600:
                    async with e["lock"]:
                        if MONO_GAMES.get(chat_id) is e:
                            await _stop(bot, chat_id, e, "Набор закрыт: никто не начал игру")
                continue
            g = e["game"]
            idle = t - g.last_act
            async with e["lock"]:
                if MONO_GAMES.get(chat_id) is not e or g.phase == "over":
                    continue
                if idle > MONO_IDLE_END:
                    await _stop(bot, chat_id, e, "Партия закрыта: долго не было ходов")
                elif g.cur().human and idle > MONO_TURN_TIMEOUT:
                    p = g.cur()
                    p.skips += 1
                    if p.skips >= 2:
                        g.forfeit(p.id)
                    else:
                        g.say(f"⏱ {p.name} долго думал, ход сделан за него")
                        {"roll": g.act_roll, "buy": lambda: g.act_buy(False), "jail": lambda: g.act_jail(False)}.get(g.phase, lambda: None)()
                    e["menu"] = False
                    await _advance(bot, chat_id, e)
        except Exception:
            log.exception("monopoly tick")
