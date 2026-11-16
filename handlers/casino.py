# -*- coding: utf-8 -*-
"""Казино: «казино», «слоты 50», «монетка 20 орёл», «рулетка 30 красное»."""

import asyncio
import re
import time

from telegram import InlineKeyboardButton as B, InlineKeyboardMarkup

from config import ALLOWED, HTML
from core.helpers import reply
from core.utils import disp, link, today, touch
from services.casino import (COIN_P, COOLDOWN, DAILY_BONUS, MAX_BET, MIN_BET, SLOT_PAY, chips_add, chips_of, claim_bonus,
                             flip, roulette, spin_slots, top_chips)

_last = {}
_busy = set()
KINDS = {"красное": "красное", "красный": "красное", "чёрное": "чёрное", "черное": "чёрное", "чёрный": "чёрное",
         "черный": "чёрное", "чётное": "чётное", "четное": "чётное", "нечётное": "нечётное", "нечетное": "нечётное",
         "зеро": "число"}
CMD_RE = re.compile(r"^(слоты|слот|монетка|монета|рулетка|казино|фишки|бонус фишки|топ фишек)(?:\s+(.*))?$")


def _menu(uid):
    rows = [[B(f"🎰 Слоты {b}", callback_data=f"cas:{uid}:slots:{b}") for b in (10, 25, 50)],
            [B("🪙 Орёл 20", callback_data=f"cas:{uid}:coin:20:орёл"), B("🪙 Решка 20", callback_data=f"cas:{uid}:coin:20:решка")],
            [B("🔴 Красное 20", callback_data=f"cas:{uid}:rul:20:красное"), B("⚫ Чёрное 20", callback_data=f"cas:{uid}:rul:20:чёрное")]]
    return InlineKeyboardMarkup(rows)


def _help(uid):
    pay = ", ".join(f"{s}{s}{s} ×{m}" for s, m in SLOT_PAY.items())
    return (f"🎰 <b>Казино</b> · игра на фишки (с славКоинами не связаны), ставка {MIN_BET}–{MAX_BET}\n"
            f"• «слоты 50»: {pay}; две 🍒: ставка назад\n"
            f"• «монетка 20 орёл» (или решка): шанс {int(COIN_P * 100)}%, выплата ×2\n"
            f"• «рулетка 30 красное»: красное/чёрное/чётное/нечётное ×2; «рулетка 30 число 17» ×35 (есть 0 и 00)\n"
            f"Все ставки на фишки: «фишки» баланс, «бонус фишки» +{DAILY_BONUS} раз в сутки, «топ фишек». "
            f"Фишки нельзя обменять на славКоины, это просто игра.")


async def _play(bot, chat, uid, name, game, bet, arg):
    """-> (текст, клавиатура) или, при отказе, (текст, None, True)"""
    if bet < MIN_BET or bet > MAX_BET:
        return f"Ставка от {MIN_BET} до {MAX_BET} фишек", None, True
    if chips_of(uid) < bet:
        return f"Не хватает фишек: у тебя {chips_of(uid)}. Бонус раз в сутки: «бонус фишки»", None, True
    if time.time() - _last.get(uid, 0) < COOLDOWN:
        return "Не так быстро, крупье устал 😅", None, True
    _last[uid] = time.time()
    chips_add(uid, -bet, name)
    if game == "slots":
        reels, mult = spin_slots()
        title = "🎰 Слоты"
        res = " ".join(reels)
    elif game == "coin":
        side, mult = flip(arg)
        title = f"🪙 Монетка ({arg})"
        res = f"выпало: {side}"
    else:
        kind, num = (arg.split(":") + [None])[:2]
        n, col, mult = roulette(kind, num)
        title = f"🎡 Рулетка ({kind}{' ' + str(num) if kind == 'число' else ''})"
        res = f"выпало {n} · {col}"
    win = bet * mult
    if win:
        chips_add(uid, win)
    if mult == 0:
        out = f"😔 Проигрыш −{bet}"
    elif win == bet:
        out = "↩️ Ставка вернулась"
    else:
        out = f"🎉 Выигрыш +{win - bet} (×{mult})" + (" ДЖЕКПОТ!" if mult >= 50 else "")
    txt = (f"{title}\n{link(uid, name)} · ставка {bet}\n<b>{res}</b>\n{out}\n"
           f"Фишек: {chips_of(uid)}")
    kb = InlineKeyboardMarkup([[B(f"🔁 Ещё раз ({bet})", callback_data=f"cas:{uid}:{ 'slots' if game == 'slots' else 'coin' if game == 'coin' else 'rul'}:{bet}:{arg}"),
                                B("🎰 Меню", callback_data=f"cas:{uid}:menu")]])
    return txt, kb, False


async def handle_casino_text(update, context, low, text):
    if update.effective_chat.id not in ALLOWED:
        return False
    m = CMD_RE.match(low)
    if not m:
        return False
    me = update.effective_user
    touch(me)
    cmd, rest = m.group(1), (m.group(2) or "").split()
    if cmd == "фишки":
        await reply(update, f"🪙 У тебя {chips_of(me.id)} фишек. Играть: «казино»")
        return True
    if cmd == "бонус фишки":
        got = claim_bonus(me.id, today())
        await reply(update, f"🎁 Бонус +{got} фишек! Теперь у тебя {chips_of(me.id)}" if got
                    else "Сегодня бонус уже получен, приходи завтра 🙂")
        return True
    if cmd == "топ фишек":
        rows = top_chips()
        await reply(update, "🏆 <b>Топ игроков казино</b>\n" + "\n".join(
            f"{i}. {link(r['user_id'], r['name'] or '?')} — {r['chips']} фишек" for i, r in enumerate(rows, 1)) if rows
            else "Пока никто не играл")
        return True
    if cmd == "казино" or (not rest and cmd in ("слоты", "слот", "монетка", "монета", "рулетка")):
        await update.effective_message.reply_text(_help(me.id), parse_mode=HTML, reply_markup=_menu(me.id))
        return True
    try:
        bet = int(rest[0])
    except ValueError:
        await reply(update, "Ставка должна быть числом, например «слоты 50»")
        return True
    if cmd in ("слоты", "слот"):
        game, arg = "slots", ""
    elif cmd in ("монетка", "монета"):
        side = (rest[1] if len(rest) > 1 else "").lower().replace("орел", "орёл")
        if side not in ("орёл", "решка"):
            await reply(update, "Выбери сторону: «монетка 20 орёл» или «монетка 20 решка»")
            return True
        game, arg = "coin", side
    else:
        k = (rest[1] if len(rest) > 1 else "").lower()
        kind = KINDS.get(k)
        if k in ("число", "зеро") or kind == "число":
            num = "0" if k == "зеро" else (rest[2] if len(rest) > 2 else "")
            if not (num == "00" or (num.isdigit() and 0 <= int(num) <= 36)):
                await reply(update, "Число от 0 до 36 или 00: «рулетка 30 число 17»")
                return True
            kind = "число"
            arg = f"число:{num}"
        elif kind:
            arg = kind
        else:
            await reply(update, "Ставь на: красное, чёрное, чётное, нечётное или число. Например «рулетка 30 красное»")
            return True
        game = "rul"
    await _run(update.effective_message, context.bot, me, game, bet, arg)
    return True


async def _run(msg, bot, me, game, bet, arg):
    if me.id in _busy:
        return
    _busy.add(me.id)
    try:
        if game in ("slots", "rul") and chips_of(me.id) >= bet and MIN_BET <= bet <= MAX_BET:
            frames = {"slots": ["🎰 | 🎲 🎲 🎲 |", "🎰 | 🎲 🎲 ❔ |"], "rul": ["🎡 Крутим колесо… ⚪", "🎡 Крутим колесо… 🔴⚫"]}[game]
            sent = await msg.reply_text(frames[0])
            await asyncio.sleep(0.8)
            try:
                await sent.edit_text(frames[1])
            except Exception:
                pass
            await asyncio.sleep(0.8)
        else:
            sent = None
        r = await _play(bot, msg.chat_id, me.id, disp(me), game, bet, arg)
        if len(r) == 3:
            if sent:
                try:
                    await sent.delete()
                except Exception:
                    pass
            return await msg.reply_text(r[0])
        txt, kb = r[0], r[1]
        if sent:
            try:
                await sent.edit_text(txt, parse_mode=HTML, reply_markup=kb)
                return
            except Exception:
                pass
        await msg.reply_text(txt, parse_mode=HTML, reply_markup=kb)
    finally:
        _busy.discard(me.id)


async def on_casino_btn(update, context):
    q = update.callback_query
    p = (q.data or "").split(":", 4)
    if len(p) < 3 or not p[1].isdigit():
        return await q.answer()
    if q.from_user.id != int(p[1]):
        return await q.answer("Это чужая игра. Напиши «казино»", show_alert=True)
    if p[2] == "menu":
        await q.answer()
        try:
            await q.edit_message_text(_help(q.from_user.id), parse_mode=HTML, reply_markup=_menu(q.from_user.id))
        except Exception:
            pass
        return
    if len(p) < 4 or not p[3].isdigit():
        return await q.answer()
    game, bet, arg = p[2], int(p[3]), (p[4] if len(p) > 4 else "")
    if game == "coin" and arg not in ("орёл", "решка"):
        return await q.answer()
    me = q.from_user
    touch(me)
    if me.id in _busy:
        return await q.answer("Подожди, идёт игра")
    r = await _play(context.bot, q.message.chat_id, me.id, disp(me), game, bet, arg)
    if len(r) == 3:
        return await q.answer(r[0], show_alert=True)
    await q.answer()
    try:
        await q.edit_message_text(r[0], parse_mode=HTML, reply_markup=r[1])
    except Exception:
        pass
