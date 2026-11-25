# -*- coding: utf-8 -*-
"""Казино: «казино», «слоты 50», «монетка 20 орёл», «рулетка 30 красное»."""

import asyncio
import io
import re
import time

from telegram import InlineKeyboardButton as B, InlineKeyboardMarkup

from config import ALLOWED, HTML
from core.helpers import reply
from core.logger import log
from core.utils import disp, link, today, touch
from services.casino import (COIN_P, COOLDOWN, DAILY_BONUS, MAX_BET, MIN_BET, SLOT_PAY, chips_add, chips_of, claim_bonus,
                             flip, roulette, spin_slots, top_chips)

_last = {}
_busy = set()
KINDS = {"красное": "красное", "красный": "красное", "чёрное": "чёрное", "черное": "чёрное", "чёрный": "чёрное",
         "черный": "чёрное", "чётное": "чётное", "четное": "чётное", "нечётное": "нечётное", "нечетное": "нечётное",
         "зеро": "число"}
CMD_RE = re.compile(r"^(слоты|слот|монетка|монета|рулетка|казино|фишки|бонус фишки|топ фишек|блэкджек|блекджек|бж|краш|ракета)(?:\s+(.*))?$")


def _menu(uid):
    rows = [[B(f"🎰 Слоты {b}", callback_data=f"cas:{uid}:slots:{b}") for b in (10, 25, 50)],
            [B("🪙 Орёл 20", callback_data=f"cas:{uid}:coin:20:орёл"), B("🪙 Решка 20", callback_data=f"cas:{uid}:coin:20:решка")],
            [B("🔴 Красное 20", callback_data=f"cas:{uid}:rul:20:красное"), B("⚫ Чёрное 20", callback_data=f"cas:{uid}:rul:20:чёрное")]]
    return InlineKeyboardMarkup(rows)


def _help(uid):
    pay = " · ".join(f"{s}×{m}" for s, m in SLOT_PAY.items()).replace("7️⃣", "7")
    return (f"🎰 <b>КАЗИНО</b> · у тебя {chips_of(uid)} 🪙\n"
            f"Играем на фишки, ставка {MIN_BET}–{MAX_BET}. На славКоины не влияют.\n\n"
            "🎰 <code>слоты 50</code>\n"
            "🪙 <code>монетка 20 орёл</code> (или решка)\n"
            "🎡 <code>рулетка 30 красное</code> (чёрное, чётное, нечётное, <code>число 17</code>)\n"
            "🃏 <code>блэкджек 50</code> · 🚀 <code>краш 50</code> · 🎡 <code>рулетка стол</code> (общий стол)\n\n"
            f"Слоты: {pay}\n"
            f"«бонус фишки» +{DAILY_BONUS} раз в сутки · «топ фишек»")


async def _play(bot, chat, uid, name, game, bet, arg):
    """-> (текст, клавиатура) или, при отказе, (текст, None, True)"""
    if bet < MIN_BET or bet > MAX_BET:
        return f"Ставка от {MIN_BET} до {MAX_BET} фишек", None, True
    if chips_of(uid) < bet:
        return f"Не хватает фишек: у тебя {chips_of(uid)}. Бонус раз в сутки: «бонус фишки»", None, True
    left = COOLDOWN - (time.time() - _last.get(uid, 0))
    if left > 0:
        return f"Крупье перемешивает колоду 🃏 Подожди ещё {int(left) + 1} сек.", None, True
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
    from services.xp import quest_hit
    await quest_hit(bot, uid, "casino", chat)
    win = bet * mult
    if win:
        chips_add(uid, win)
    if mult == 0:
        out = f"😔 Проигрыш −{bet}"
    elif win == bet:
        out = "↩️ Ставка вернулась"
    else:
        out = f"🎉 Выигрыш +{win - bet} (×{mult})" + (" ДЖЕКПОТ!" if mult >= 50 else "")
    txt = (f"{title} · {link(uid, name)}\n<b>{res}</b>\n{out} · ставка {bet}\n"
           f"🪙 Фишек: {chips_of(uid)}")
    info = dict(game=game, bet=bet, mult=mult, arg=arg)
    if game == "slots":
        info["reels"] = reels
    elif game == "coin":
        info["side"] = side
    else:
        info.update(num=n, col=col, kind=title)
    kb = InlineKeyboardMarkup([[B(f"🔁 Ещё раз ({bet})", callback_data=f"cas:{uid}:{ 'slots' if game == 'slots' else 'coin' if game == 'coin' else 'rul'}:{bet}:{arg}"),
                                B("🎰 Меню", callback_data=f"cas:{uid}:menu")]])
    return txt, kb, None, info


async def _gif(info):
    """GIF под результат; None, если не вышло."""
    from services import casino_gif as cg
    try:
        g, bet, mult = info["game"], info["bet"], info["mult"]
        if g == "slots":
            data = await asyncio.to_thread(cg.slots_gif, info["reels"], mult, bet)
        elif g == "coin":
            data = await asyncio.to_thread(cg.coin_gif, info["side"], info["arg"], mult, bet)
        else:
            data = await asyncio.to_thread(cg.roulette_gif, info["num"], info["col"], info["kind"].replace("🎡 ", ""), mult, bet)
        bio = io.BytesIO(data)
        bio.name = "casino.gif"
        return bio
    except Exception:
        log.exception("casino gif")
        return None


from services.casino import LAST_MSG as _msgs


async def _send_result(bot, chat, reply_to, txt, kb, info, uid=None, edit_id=None):
    """Результат с анимацией. Если есть прошлое сообщение игрока, меняем его (без спама), иначе шлём новое."""
    from telegram import InputMediaAnimation
    key = (chat, uid)
    edit_id = edit_id or (_msgs.get(key) if uid else None)
    try:                                               # сообщение с идущим блэкджеком не трогаем: там живые кнопки
        from handlers.casino_games import BJ
        g = BJ.get(key)
        if g and g.get("msg") == edit_id:
            edit_id = None
    except Exception:
        pass
    gif = await _gif(info)
    if edit_id:
        try:
            if gif:
                gif.seek(0)
                await bot.edit_message_media(chat_id=chat, message_id=edit_id,
                                             media=InputMediaAnimation(gif, caption=txt, parse_mode=HTML),
                                             reply_markup=kb, read_timeout=25, write_timeout=25)
            else:
                await bot.edit_message_caption(chat_id=chat, message_id=edit_id, caption=txt, parse_mode=HTML, reply_markup=kb)
            return edit_id
        except Exception as e:
            log.info("casino edit: %r", e)
    m = None
    if gif:
        try:
            gif.seek(0)
            m = await bot.send_animation(chat, gif, caption=txt, parse_mode=HTML, reply_markup=kb,
                                         reply_to_message_id=reply_to, read_timeout=25, write_timeout=25)
        except Exception as e:
            log.warning("casino send gif: %r", e)
    if m is None:
        m = await bot.send_message(chat, txt, parse_mode=HTML, reply_markup=kb, reply_to_message_id=reply_to)
    if uid and m:
        if edit_id:                                   # старое не удалось изменить: убираем его кнопки
            try:
                await bot.edit_message_reply_markup(chat_id=chat, message_id=edit_id, reply_markup=None)
            except Exception:
                pass
        _msgs[key] = m.message_id
    return m


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
        from handlers.casino_games import send_top
        await send_top(update)
        return True
    from handlers import casino_games as G
    chat = update.effective_chat.id
    if cmd == "рулетка" and rest[:1] in (["стол"], ["столик"]):
        err = await G.table_open_cmd(context.bot, chat)
        if err:
            await reply(update, err)
        return True
    if cmd in ("блэкджек", "блекджек", "бж", "краш", "ракета"):
        try:
            bet = int(rest[0])
        except (ValueError, IndexError):
            await reply(update, f"Ставка числом, например «{cmd} 50»")
            return True
        if me.id in _busy:
            return True
        _busy.add(me.id)
        try:
            if cmd in ("краш", "ракета"):
                err = await G.crash_join(context.bot, chat, me, bet)
            else:
                err = await G.bj_start(context.bot, chat, me, bet, update.effective_message.message_id)
        finally:
            _busy.discard(me.id)
        if err:
            await reply(update, err)
        return True
    if cmd == "казино" and False:
        pass
    if cmd == "казино" or (not rest and cmd in ("слоты", "слот", "монетка", "монета", "рулетка")):
        await G.send_lobby(update, _help(me.id), me.id)
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
        if G.table_open(chat):
            kk, _, nn = arg.partition(":")
            err = await G.table_bet(context.bot, chat, me, bet, kk, nn or None)
            await reply(update, err or f"🎡 Ставка принята: {bet} на {arg.replace(':', ' ')}")
            return True
    await _run(update.effective_message, context.bot, me, game, bet, arg)
    return True


async def _run(msg, bot, me, game, bet, arg):
    if me.id in _busy:
        return
    _busy.add(me.id)
    try:
        r = await _play(bot, msg.chat_id, me.id, disp(me), game, bet, arg)
        if len(r) == 3:
            return await msg.reply_text(r[0])
        await _send_result(bot, msg.chat_id, msg.message_id, r[0], r[1], r[3], uid=me.id)
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
            await q.edit_message_reply_markup(None)
        except Exception:
            pass
        await context.bot.send_message(q.message.chat_id, _help(q.from_user.id), parse_mode=HTML, reply_markup=__import__('handlers.casino_games', fromlist=['x']).menu_kb(q.from_user.id))
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
    _busy.add(me.id)
    try:
        r = await _play(context.bot, q.message.chat_id, me.id, disp(me), game, bet, arg)
        if len(r) == 3:
            return await q.answer(r[0], show_alert=True)
        await q.answer("Крутим…")
        await _send_result(context.bot, q.message.chat_id, None, r[0], r[1], r[3], uid=me.id, edit_id=q.message.message_id)
    finally:
        _busy.discard(me.id)
