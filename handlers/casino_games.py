# -*- coding: utf-8 -*-
"""Казино, часть 2: блэкджек, крэш (ракета), общий стол рулетки, рейтинг и баннер."""

import asyncio
import io
import math
import random
import time

from telegram import InlineKeyboardButton as B, InlineKeyboardMarkup, InputMediaPhoto

from config import HTML
from core.helpers import reply
from core.logger import log
from core.utils import disp, esc, link, touch
from services.casino import MAX_BET, MIN_BET, WHEEL, chips_add, chips_of, color_of, REDS
from services.casino_ui import bj_card, casino_title, crash_gif, hand_value, lobby_card, top_card

GOLD_OK, BAD = (150, 255, 180), (255, 150, 150)
CROUPIER = {
    "win": ("Фортуна сегодня на твоей стороне.", "Крупье скрипит зубами.", "Так держать, везунчик!", "Казино в шоке."),
    "lose": ("Дом всегда выигрывает.", "Не повезло. Бывает.", "Фишки любят возвращаться… не всегда.", "Крупье довольно улыбается."),
    "push": ("Ничья: ставка при тебе.", "Тут без победителей."),
}


def phrase(kind):
    return random.choice(CROUPIER[kind])


async def _quest(bot, uid, chat):
    try:
        from services.xp import quest_hit
        await quest_hit(bot, uid, "casino", chat)
    except Exception:
        pass


def _check_bet(uid, bet):
    if bet < MIN_BET or bet > MAX_BET:
        return f"Ставка от {MIN_BET} до {MAX_BET} фишек"
    if chips_of(uid) < bet:
        return f"Не хватает фишек: у тебя {chips_of(uid)}. Бонус раз в сутки: «бонус фишки»"
    return None


# ============================== БЛЭКДЖЕК ==============================
BJ = {}       # (chat, uid) -> игра


def _deck():
    d = [(r, s) for r in ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A") for s in "shdc"]
    random.shuffle(d)
    return d


def _bj_kb(g, uid):
    row = [B("➕ Ещё", callback_data=f"cg:{uid}:bj:hit"), B("✋ Стоп", callback_data=f"cg:{uid}:bj:stand")]
    if len(g["p"]) == 2 and not g["dbl"] and chips_of(uid) >= g["bet"]:
        row.append(B("✖️2 Удвоить", callback_data=f"cg:{uid}:bj:dbl"))
    return InlineKeyboardMarkup([row])


def _bj_end_kb(uid, bet):
    return InlineKeyboardMarkup([[B(f"🔁 Ещё раз ({bet})", callback_data=f"cg:{uid}:bj:new:{bet}"), B("🎰 Меню", callback_data=f"cas:{uid}:menu")]])


async def bj_start(bot, chat, me, bet, reply_to=None, msg_id=None):
    uid = me.id
    old = BJ.get((chat, uid))
    if old and time.time() - old["t"] < 240:
        # раздача ещё идёт: вместо отказа заново показываем карты с кнопками (прошлое сообщение могло быть заменено)
        try:
            buf = await asyncio.to_thread(bj_card, old["p"], old["d"], True, old["bet"], None, name=old["name"])
            m = await bot.send_photo(chat, buf, caption=f"🃏 <b>Блэкджек</b> · {link(uid, old['name'])}\nТвоя раздача ещё идёт. Ещё, стоп или удвоить?",
                                     parse_mode=HTML, reply_markup=_bj_kb(old, uid), reply_to_message_id=reply_to)
            if old.get("msg") and old["msg"] != m.message_id:
                try:
                    await bot.edit_message_reply_markup(chat_id=chat, message_id=old["msg"], reply_markup=None)
                except Exception:
                    pass
            old["msg"] = m.message_id
            return None
        except Exception as e:
            log.warning("bj resend: %r", e)
            return "Сначала доиграй текущую раздачу (кнопки под картой)"
    err = _check_bet(uid, bet)
    if err:
        return err
    if old:
        await _bj_finish(bot, chat, uid, forced=True)
    chips_add(uid, -bet, disp(me))
    deck = _deck()
    g = dict(deck=deck, p=[deck.pop(), deck.pop()], d=[deck.pop(), deck.pop()], bet=bet, dbl=False, name=disp(me), t=time.time(), msg=None)
    BJ[(chat, uid)] = g
    await _quest(bot, uid, chat)
    if hand_value(g["p"]) == 21:
        from services.casino import LAST_MSG
        g["msg"] = msg_id or LAST_MSG.get((chat, uid))
        return await _bj_finish(bot, chat, uid, reply_to=reply_to)
    buf = await asyncio.to_thread(bj_card, g["p"], g["d"], True, bet, None, name=g["name"])
    cap = f"🃏 <b>Блэкджек</b> · {link(uid, g['name'])}\nТвой ход. Ещё, стоп или удвоить?"
    kb = _bj_kb(g, uid)
    from services.casino import LAST_MSG
    old_id = msg_id or LAST_MSG.get((chat, uid))
    if old_id:
        try:
            await bot.edit_message_media(chat_id=chat, message_id=old_id, media=InputMediaPhoto(buf, caption=cap, parse_mode=HTML),
                                         reply_markup=kb, read_timeout=25, write_timeout=25)
            g["msg"] = old_id
            LAST_MSG[(chat, uid)] = old_id
            return None
        except Exception as e:
            log.info("bj edit: %r", e)
            buf.seek(0)
    m = await bot.send_photo(chat, buf, caption=cap, parse_mode=HTML, reply_markup=kb, reply_to_message_id=reply_to)
    g["msg"] = m.message_id
    LAST_MSG[(chat, uid)] = m.message_id
    return None


async def _bj_finish(bot, chat, uid, forced=False, reply_to=None):
    g = BJ.pop((chat, uid), None)
    if not g:
        return None
    p, dl, bet = g["p"], g["d"], g["bet"] * (2 if g["dbl"] else 1)
    pv = hand_value(p)
    natural = pv == 21 and len(p) == 2
    if pv <= 21:
        while hand_value(dl) < 17:
            dl.append(g["deck"].pop())
    dv = hand_value(dl)
    if pv > 21:
        res, pay, status, col = "lose", 0, f"ПЕРЕБОР −{bet}", BAD
    elif natural and not (dv == 21 and len(dl) == 2):
        pay = int(bet * 2.5)
        res, status, col = "win", f"БЛЭКДЖЕК +{pay - bet}", GOLD_OK
    elif dv > 21 or pv > dv:
        pay = bet * 2
        res, status, col = "win", f"ПОБЕДА +{pay - bet}", GOLD_OK
    elif pv == dv:
        pay = bet
        res, status, col = "push", "НИЧЬЯ, ставка назад", (255, 255, 255)
    else:
        res, pay, status, col = "lose", 0, f"ПРОИГРЫШ −{bet}", BAD
    if pay:
        chips_add(uid, pay)
    buf = await asyncio.to_thread(bj_card, p, dl, False, bet, status, col, g["name"])
    cap = (f"🃏 <b>Блэкджек</b> · {link(uid, g['name'])}\nУ тебя {pv}, у крупье {dv}\n<b>{status}</b>\n"
           f"🪙 Фишек: {chips_of(uid)}\n<i>{phrase(res)}</i>")
    kb = _bj_end_kb(uid, g["bet"])
    try:
        if g["msg"]:
            await bot.edit_message_media(chat_id=chat, message_id=g["msg"], media=InputMediaPhoto(buf, caption=cap, parse_mode=HTML), reply_markup=kb)
        else:
            mm = await bot.send_photo(chat, buf, caption=cap, parse_mode=HTML, reply_markup=kb, reply_to_message_id=reply_to)
            from services.casino import LAST_MSG
            LAST_MSG[(chat, uid)] = mm.message_id
    except Exception as e:
        log.warning("bj finish: %r", e)
        try:
            await bot.send_message(chat, cap, parse_mode=HTML, reply_markup=kb)
        except Exception:
            pass
    return None


async def bj_action(bot, chat, uid, act, q):
    g = BJ.get((chat, uid))
    if not g:
        return await q.answer("Раздача закончилась. Начни новую: «блэкджек 50»", show_alert=True)
    g["t"] = time.time()
    if act == "hit":
        g["p"].append(g["deck"].pop())
        if hand_value(g["p"]) >= 21:
            await q.answer()
            return await _bj_finish(bot, chat, uid)
    elif act == "dbl":
        if len(g["p"]) != 2 or g["dbl"] or chips_of(uid) < g["bet"]:
            return await q.answer("Удвоить нельзя", show_alert=True)
        chips_add(uid, -g["bet"])
        g["dbl"] = True
        g["p"].append(g["deck"].pop())
        await q.answer("Ставка удвоена!")
        return await _bj_finish(bot, chat, uid)
    else:
        await q.answer()
        return await _bj_finish(bot, chat, uid)
    await q.answer()
    buf = await asyncio.to_thread(bj_card, g["p"], g["d"], True, g["bet"], None, name=g["name"])
    try:
        await bot.edit_message_media(chat_id=chat, message_id=g["msg"],
                                     media=InputMediaPhoto(buf, caption=f"🃏 <b>Блэкджек</b> · {link(uid, g['name'])}\nЕщё, стоп или удвоить?", parse_mode=HTML),
                                     reply_markup=_bj_kb(g, uid))
    except Exception as e:
        log.warning("bj edit: %r", e)


# ============================== КРЭШ ==============================
CRASH = {}     # chat -> раунд
K = 0.085      # скорость роста: x = e^(K*t)
LOBBY_SEC = 15


def _crash_point():
    u = random.random()
    c = 0.96 / (1 - u)
    return round(min(c, 60.0), 2) if c >= 1.0 else 1.0


def _mult(rd):
    return math.exp(K * (time.time() - rd["t0"]))


def _crash_text(rd, cur=None, crashed=False):
    lines = []
    for uid, p in rd["pl"].items():
        if p["cash"]:
            lines.append(f"✅ {esc(p['name'])}: x{p['cash']:.2f} → +{int(p['bet'] * p['cash']) - p['bet']}")
        elif crashed:
            lines.append(f"💥 {esc(p['name'])}: −{p['bet']}")
        else:
            lines.append(f"🎯 {esc(p['name'])}: {p['bet']} 🪙")
    head = "🚀 <b>КРЭШ</b>"
    if rd["state"] == "lobby":
        head += f" · старт через {max(0, int(rd['t0'] - time.time()))} сек.\nСтавь: «краш 50»"
    elif crashed:
        head += f" · <b>взрыв на x{rd['crash']:.2f}</b>"
    else:
        bar = "▰" * min(20, int((cur - 1) * 4) + 1)
        head += f"\n<b>x{cur:.2f}</b> {bar}\nЖми «Забрать», пока не взорвалась!"
    return head + ("\n\n" + "\n".join(lines) if lines else "")


def _crash_kb(rd):
    if rd["state"] == "lobby":
        return InlineKeyboardMarkup([[B("🎯 Ставка 50", callback_data="cg:0:crash:join:50"), B("🎯 100", callback_data="cg:0:crash:join:100")]])
    return InlineKeyboardMarkup([[B("💰 ЗАБРАТЬ", callback_data="cg:0:crash:cash")]])


async def crash_join(bot, chat, me, bet):
    err = _check_bet(me.id, bet)
    if err:
        return err
    rd = CRASH.get(chat)
    if rd and rd["state"] == "fly":
        return "Ракета уже летит. Жди следующий раунд"
    if rd and me.id in rd["pl"]:
        return "Ты уже сделал ставку в этом раунде"
    chips_add(me.id, -bet, disp(me))
    await _quest(bot, me.id, chat)
    if not rd:
        rd = dict(state="lobby", t0=time.time() + LOBBY_SEC, pl={}, msg=None, crash=_crash_point())
        CRASH[chat] = rd
        rd["pl"][me.id] = dict(name=disp(me), bet=bet, cash=None)
        m = await bot.send_message(chat, _crash_text(rd), parse_mode=HTML, reply_markup=_crash_kb(rd))
        rd["msg"] = m.message_id
        asyncio.create_task(_crash_run(bot, chat))
    else:
        rd["pl"][me.id] = dict(name=disp(me), bet=bet, cash=None)
    return None


async def _edit(bot, chat, rd, text, kb):
    try:
        await bot.edit_message_text(text, chat_id=chat, message_id=rd["msg"], parse_mode=HTML, reply_markup=kb)
    except Exception:
        pass


async def _crash_run(bot, chat):
    rd = CRASH.get(chat)
    try:
        while time.time() < rd["t0"]:
            await asyncio.sleep(3)
            if time.time() < rd["t0"]:
                await _edit(bot, chat, rd, _crash_text(rd), _crash_kb(rd))
        rd["state"] = "fly"
        rd["t0"] = time.time()
        Tc = math.log(max(rd["crash"], 1.0)) / K
        while True:
            el = time.time() - rd["t0"]
            if el >= Tc:
                break
            if all(p["cash"] for p in rd["pl"].values()):
                break
            await _edit(bot, chat, rd, _crash_text(rd, _mult(rd)), _crash_kb(rd))
            await asyncio.sleep(1.2)
        rd["state"] = "done"
        crashed_all_cashed = all(p["cash"] for p in rd["pl"].values())
        text = _crash_text(rd, crashed=True)
        await _edit(bot, chat, rd, text, None)
        # итоги и GIF
        winners = [(p["name"], p["cash"]) for p in rd["pl"].values()]
        try:
            data = await asyncio.to_thread(crash_gif, rd["crash"], winners)
            bio = io.BytesIO(data)
            bio.name = "crash.gif"
            tot_win = sum(int(p["bet"] * p["cash"]) - p["bet"] for p in rd["pl"].values() if p["cash"])
            tot_lose = sum(p["bet"] for p in rd["pl"].values() if not p["cash"])
            cap = f"💥 Ракета взорвалась на <b>x{rd['crash']:.2f}</b>\n" + (f"Выплачено: +{tot_win}\n" if tot_win else "") + \
                  (f"Сгорело ставок: {tot_lose}\n" if tot_lose else "") + f"<i>{phrase('win' if tot_win > tot_lose else 'lose')}</i>"
            await bot.send_animation(chat, bio, caption=cap, parse_mode=HTML, read_timeout=25, write_timeout=25)
            try:
                await bot.delete_message(chat, rd["msg"])      # текстовое табло заменяем одной анимацией
            except Exception:
                pass
        except Exception as e:
            log.warning("crash gif: %r", e)
    except Exception:
        log.exception("crash run")
        for p_uid, p in rd["pl"].items():           # сбой: вернуть ставки тем, кто не забрал
            if not p["cash"]:
                chips_add(p_uid, p["bet"])
    finally:
        CRASH.pop(chat, None)


async def crash_cash(chat, uid, q):
    rd = CRASH.get(chat)
    if not rd or rd["state"] != "fly":
        return await q.answer("Раунда нет или он ещё не начался", show_alert=True)
    p = rd["pl"].get(uid)
    if not p:
        return await q.answer("Ты не делал ставку в этом раунде", show_alert=True)
    if p["cash"]:
        return await q.answer("Ты уже забрал")
    m = _mult(rd)
    if m >= rd["crash"]:
        return await q.answer("Поздно, ракета взорвалась 💥", show_alert=True)
    m = max(1.0, math.floor(m * 100) / 100)
    p["cash"] = m
    chips_add(uid, int(p["bet"] * m))
    await q.answer(f"Забрал x{m:.2f}: +{int(p['bet'] * m) - p['bet']} 🪙")


# ============================== ОБЩИЙ СТОЛ РУЛЕТКИ ==============================
TABLE = {}      # chat -> стол
TABLE_SEC = 30


def table_open(chat):
    return chat in TABLE


def _table_text(t):
    left = max(0, int(t["end"] - time.time()))
    rows = [f"• {esc(b['name'])}: {b['bet']} на {b['label']}" for b in t["bets"][-12:]]
    return (f"🎡 <b>ОБЩИЙ СТОЛ РУЛЕТКИ</b> · до вращения {left} сек.\n"
            f"Ставки: «рулетка 30 красное», «рулетка 30 число 17» или кнопки.\n\n" + ("\n".join(rows) if rows else "Ставок пока нет"))


def _table_kb():
    return InlineKeyboardMarkup([[B("🔴 Красное 20", callback_data="cg:0:tbl:20:красное"), B("⚫ Чёрное 20", callback_data="cg:0:tbl:20:чёрное")],
                                 [B("2️⃣ Чёт 20", callback_data="cg:0:tbl:20:чётное"), B("1️⃣ Нечет 20", callback_data="cg:0:tbl:20:нечётное")]])


async def table_open_cmd(bot, chat):
    if chat in TABLE:
        return "Стол уже открыт, делай ставки"
    t = dict(end=time.time() + TABLE_SEC, bets=[], msg=None)
    TABLE[chat] = t
    m = await bot.send_message(chat, _table_text(t), parse_mode=HTML, reply_markup=_table_kb())
    t["msg"] = m.message_id
    asyncio.create_task(_table_run(bot, chat))
    return None


def _label(kind, num):
    return f"число {num}" if kind == "число" else kind


async def table_bet(bot, chat, me, bet, kind, num=None):
    t = TABLE.get(chat)
    if not t:
        return "Стол закрыт. Открыть: «рулетка стол»"
    err = _check_bet(me.id, bet)
    if err:
        return err
    mine = sum(b["bet"] for b in t["bets"] if b["uid"] == me.id)
    if mine + bet > 3000:
        return "На одном столе максимум 3000 фишек от человека"
    chips_add(me.id, -bet, disp(me))
    t["bets"].append(dict(uid=me.id, name=disp(me), bet=bet, kind=kind, num=num, label=_label(kind, num)))
    await _quest(bot, me.id, chat)
    return None


def _payout(b, n):
    col = color_of(n)
    k = b["kind"]
    if k in ("красное", "чёрное"):
        return 2 if col == k else 0
    if k in ("чётное", "нечётное") and n not in (0, "00"):
        return 2 if (n % 2 == 0) == (k == "чётное") else 0
    if k == "число":
        return 35 if str(n) == str(b["num"]) else 0
    return 0


async def _table_run(bot, chat):
    t = TABLE.get(chat)
    try:
        while time.time() < t["end"]:
            await asyncio.sleep(min(5, max(0.5, t["end"] - time.time())))
            if time.time() < t["end"]:
                try:
                    await bot.edit_message_text(_table_text(t), chat_id=chat, message_id=t["msg"], parse_mode=HTML, reply_markup=_table_kb())
                except Exception:
                    pass
        n = random.choice(WHEEL)
        col = color_of(n)
        try:
            await bot.edit_message_reply_markup(chat_id=chat, message_id=t["msg"], reply_markup=None)
        except Exception:
            pass
        res, total_pay = {}, 0
        for b in t["bets"]:
            m = _payout(b, n)
            pay = b["bet"] * m
            if pay:
                chips_add(b["uid"], pay)
            r = res.setdefault(b["uid"], [b["name"], 0])
            r[1] += pay - b["bet"]
        lines = [f"{'🟢' if v >= 0 else '🔴'} {esc(nm)}: {v:+d}" for nm, v in res.values()]
        cap = (f"🎡 <b>Выпало {n} · {col}</b>\n" + ("\n".join(lines) if lines else "Никто не ставил 😴") +
               f"\n\n<i>{phrase('win' if any(v > 0 for _, v in res.values()) else 'lose')}</i>")
        try:
            from services.casino_gif import roulette_gif
            data = await asyncio.to_thread(roulette_gif, n, col, "ОБЩИЙ СТОЛ", None, 0)
            bio = io.BytesIO(data)
            bio.name = "table.gif"
            await bot.send_animation(chat, bio, caption=cap[:1000], parse_mode=HTML, read_timeout=25, write_timeout=25)
            try:
                await bot.delete_message(chat, t["msg"])
            except Exception:
                pass
        except Exception as e:
            log.warning("table gif: %r", e)
            await bot.send_message(chat, cap, parse_mode=HTML)
    except Exception:
        log.exception("table run")
        for b in t["bets"]:
            chips_add(b["uid"], b["bet"])
    finally:
        TABLE.pop(chat, None)


# ============================== баннер, рейтинг, кнопки ==============================
def menu_kb(uid):
    return InlineKeyboardMarkup([
        [B(f"🎰 Слоты {b}", callback_data=f"cas:{uid}:slots:{b}") for b in (10, 25, 50)],
        [B("🪙 Орёл 20", callback_data=f"cas:{uid}:coin:20:орёл"), B("🪙 Решка 20", callback_data=f"cas:{uid}:coin:20:решка")],
        [B("🔴 Красное 20", callback_data=f"cas:{uid}:rul:20:красное"), B("⚫ Чёрное 20", callback_data=f"cas:{uid}:rul:20:чёрное")],
        [B("🃏 Блэкджек 50", callback_data=f"cg:{uid}:bj:new:50"), B("🚀 Краш 50", callback_data="cg:0:crash:join:50")],
        [B("🎡 Общий стол", callback_data=f"cg:{uid}:tbl:open")],
    ])


def best_of(uid):
    from database.db import db
    r = db.execute("SELECT best FROM casino WHERE user_id=?", (uid,)).fetchone()
    return (r["best"] if r else 0) or 0


async def send_lobby(update, caption, uid):
    me = update.effective_user
    try:
        buf = await asyncio.to_thread(lobby_card, disp(me), chips_of(me.id), best_of(me.id))
        from handlers.finance import _send_photo
        await _send_photo(update.effective_message, buf, caption, reply_markup=menu_kb(uid))
    except Exception:
        log.exception("lobby")
        await update.effective_message.reply_text(caption, parse_mode=HTML, reply_markup=menu_kb(uid))


async def send_top(update):
    from services.casino import top_chips
    from database.db import db
    rows = db.execute("SELECT user_id,name,chips,best FROM casino ORDER BY chips DESC LIMIT 8").fetchall()
    if not rows:
        return await reply(update, "Пока никто не играл")
    try:
        from handlers.finance import _send_photo
        buf = await asyncio.to_thread(top_card, rows)
        await _send_photo(update.effective_message, buf, "🏆 Топ игроков казино")
    except Exception:
        await reply(update, "🏆 <b>Топ казино</b>\n" + "\n".join(f"{i}. {esc(r['name'] or '?')} — {r['chips']}" for i, r in enumerate(rows, 1)))


async def on_cg_btn(update, context):
    q = update.callback_query
    p = (q.data or "").split(":")
    if len(p) < 4 or not p[1].isdigit():
        return await q.answer()
    owner, game, act = int(p[1]), p[2], p[3]
    me = q.from_user
    chat = q.message.chat_id
    touch(me)
    if owner and me.id != owner:
        return await q.answer("Это чужая игра. Напиши «казино»", show_alert=True)
    if game == "bj":
        if act == "new":
            bet = int(p[4]) if len(p) > 4 and p[4].isdigit() else 50
            await q.answer()
            err = await bj_start(context.bot, chat, me, bet, msg_id=q.message.message_id)
            if err:
                await context.bot.send_message(chat, err)
            return
        return await bj_action(context.bot, chat, me.id, act, q)
    if game == "crash":
        if act == "join":
            bet = int(p[4]) if len(p) > 4 and p[4].isdigit() else 50
            err = await crash_join(context.bot, chat, me, bet)
            return await q.answer(err or "Ставка принята!", show_alert=bool(err))
        return await crash_cash(chat, me.id, q)
    if game == "tbl":
        if act == "open":
            await q.answer()
            err = await table_open_cmd(context.bot, chat)
            if err:
                await context.bot.send_message(chat, err)
            return
        if act.isdigit() and len(p) > 4:
            err = await table_bet(context.bot, chat, me, int(act), p[4])
            return await q.answer(err or "Ставка принята!", show_alert=bool(err))
    await q.answer()
