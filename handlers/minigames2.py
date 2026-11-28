# -*- coding: utf-8 -*-
"""Новые мини-игры: «крестики-нолики» (ответом на сообщение соперника) и «угадай число» (общий раунд для чата)."""

import random
import time

from telegram import InlineKeyboardButton as B, InlineKeyboardMarkup

from config import ALLOWED, HTML
from core.helpers import reply
from core.utils import disp, link, touch
from database.db import db
from services.economy import COIN, give_coins

TTT = {}                    # message_id -> dict
TTT_WORDS = {"крестики", "крестики-нолики", "крестики нолики", "ттт"}
GUESS = {}                  # chat_id -> dict
GUESS_PRIZE, GUESS_SEC, GUESS_TRIES = 15, 180, 5
LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]


def _win(b):
    for a, c, d in LINES:
        if b[a] and b[a] == b[c] == b[d]:
            return b[a]
    return None


def _board_kb(mid, b, over=False):
    sym = {None: "·", "X": "❌", "O": "⭕"}
    rows = [[B(sym[b[r * 3 + c]], callback_data=f"tt:{mid}:{r * 3 + c}") for c in range(3)] for r in range(3)]
    return InlineKeyboardMarkup(rows) if not over else InlineKeyboardMarkup(rows)


def _title(g, extra=""):
    x, o = g["ids"]
    turn = x if g["turn"] == "X" else o
    return (f"❌⭕ <b>Крестики-нолики</b>\n❌ {link(x, g['name'][x])}  vs  ⭕ {link(o, g['name'][o])}\n" + extra
            + (f"Ходит: {link(turn, g['name'][turn])}" if not extra else ""))


async def handle_games2_text(update, context, low, text):
    if update.effective_chat.id not in ALLOWED:
        return False
    me = update.effective_user
    chat = update.effective_chat.id
    low = low.strip()
    # крестики-нолики
    if low in TTT_WORDS:
        rep = update.effective_message.reply_to_message
        if not rep or not rep.from_user or rep.from_user.is_bot or rep.from_user.id == me.id:
            await reply(update, "❌⭕ Ответь командой «крестики» на сообщение соперника")
            return True
        touch(me)
        opp = rep.from_user
        kb = InlineKeyboardMarkup([[B("✅ Принять", callback_data=f"tt:acc:{me.id}:{opp.id}"),
                                    B("✖ Отказ", callback_data=f"tt:no:{me.id}:{opp.id}")]])
        await reply(update, f"❌⭕ {link(me.id, disp(me))} зовёт {link(opp.id, disp(opp))} сыграть в крестики-нолики. Принимаешь?",
                    reply_markup=kb)
        return True
    # угадай число
    if low in ("угадай число", "угадайка"):
        if chat in GUESS and GUESS[chat]["end"] > time.time():
            await reply(update, "🔢 Раунд уже идёт: пиши числа от 1 до 100")
            return True
        GUESS[chat] = {"n": random.randint(1, 100), "end": time.time() + GUESS_SEC, "tries": {}}
        await reply(update, f"🔢 <b>Угадай число от 1 до 100!</b>\nПиши число в чат (у каждого {GUESS_TRIES} попыток, {GUESS_SEC // 60} мин). "
                            f"Подскажу «больше» или «меньше». Приз: {GUESS_PRIZE} {COIN}")
        return True
    g = GUESS.get(chat)
    if g and low.isdigit() and 1 <= len(low) <= 3:
        if g["end"] < time.time():
            GUESS.pop(chat, None)
            return False
        used = g["tries"].get(me.id, 0)
        if used >= GUESS_TRIES:
            return True
        g["tries"][me.id] = used + 1
        v = int(low)
        if v == g["n"]:
            GUESS.pop(chat, None)
            touch(me)
            give_coins(me.id, GUESS_PRIZE)
            db.execute("UPDATE users SET game_pts=game_pts+1 WHERE user_id=?", (me.id,))
            db.commit()
            await reply(update, f"🎉 {link(me.id, disp(me))} угадал(а): <b>{v}</b>! +{GUESS_PRIZE} {COIN} и 1 игровое очко")
        else:
            await update.effective_message.reply_text("⬆️ Больше" if v < g["n"] else "⬇️ Меньше")
        return True
    return False


async def on_ttt_btn(update, context):
    q = update.callback_query
    p = (q.data or "").split(":")
    mid = q.message.message_id
    if len(p) >= 4 and p[1] in ("acc", "no"):
        a, b = int(p[2]), int(p[3])
        if q.from_user.id != b:
            return await q.answer("Это приглашение не тебе", show_alert=True)
        if p[1] == "no":
            await q.answer()
            return await q.edit_message_text("✖ Соперник отказался от крестиков-ноликов")
        names = {a: str(a), b: disp(q.from_user)}
        try:
            r = db.execute("SELECT name FROM users WHERE user_id=?", (a,)).fetchone()
            names[a] = r["name"] if r and r["name"] else str(a)
        except Exception:
            pass
        ids = [a, b] if random.random() < .5 else [b, a]
        g = {"ids": ids, "name": names, "b": [None] * 9, "turn": "X", "t": time.time()}
        TTT[mid] = g
        await q.answer("Поехали!")
        return await q.edit_message_text(_title(g), parse_mode=HTML, reply_markup=_board_kb(mid, g["b"]))
    if len(p) != 3 or not p[2].isdigit():
        return await q.answer()
    g = TTT.get(mid)
    if not g:
        return await q.answer("Игра закончена или бот перезапускался", show_alert=True)
    x, o = g["ids"]
    me = q.from_user.id
    if me not in (x, o):
        return await q.answer("Это не твоя игра", show_alert=True)
    if (g["turn"] == "X") != (me == x):
        return await q.answer("Сейчас ход соперника", show_alert=True)
    i = int(p[2])
    if g["b"][i]:
        return await q.answer("Клетка занята", show_alert=True)
    g["b"][i] = g["turn"]
    w = _win(g["b"])
    if w or all(g["b"]):
        TTT.pop(mid, None)
        if w:
            wid = x if w == "X" else o
            db.execute("UPDATE users SET game_pts=game_pts+2 WHERE user_id=?", (wid,))
            db.commit()
            extra = f"🏆 Победил {link(wid, g['name'][wid])}! (+2 игровых очка)\n"
        else:
            extra = "🤝 Ничья\n"
        await q.answer()
        return await q.edit_message_text(_title(g, extra), parse_mode=HTML, reply_markup=_board_kb(mid, g["b"], True))
    g["turn"] = "O" if g["turn"] == "X" else "X"
    await q.answer()
    await q.edit_message_text(_title(g), parse_mode=HTML, reply_markup=_board_kb(mid, g["b"]))
