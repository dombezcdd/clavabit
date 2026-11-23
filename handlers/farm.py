# -*- coding: utf-8 -*-
"""Рыбалка и огород: «рыбалка», «улов», «огород»."""

import asyncio

from telegram import InlineKeyboardButton as B, InlineKeyboardMarkup

from config import ALLOWED, HTML
from core.helpers import reply
from core.utils import disp, esc, link, today, touch
from services.economy import COIN, give_coins
from services.farm import CROPS, PLOTS, fish_cast, fish_take, garden_card, harvest, plant, plot_state


def _kb(uid):
    rows = []
    for i, st in enumerate(plot_state(uid), 1):
        if st is None:
            rows.append([B(f"{CROPS[k][0].split()[0]} {k} ({CROPS[k][1]})", callback_data=f"fm:{uid}:plant:{i}:{k}") for k in CROPS])
    rows.append([B("🧺 Собрать урожай", callback_data=f"fm:{uid}:harvest"), B("🔄 Обновить", callback_data=f"fm:{uid}:show")])
    return InlineKeyboardMarkup(rows)


def _cap(uid):
    return ("🌱 <b>Огород</b>\nСажай семена (цена в скобках, славКоин), жди и собирай. "
            f"Морковь 3 ч, тыква 8 ч, клубника 12 ч. Грядок: {PLOTS}")


async def handle_farm_text(update, context, low, text):
    if update.effective_chat.id not in ALLOWED:
        return False
    me = update.effective_user
    if low in ("рыбалка", "закинуть удочку", "удочка", "порыбачить"):
        touch(me)
        ok, msg = fish_cast(me.id, today())
        await reply(update, msg)
        return True
    if low in ("улов", "забрать улов", "поплавок"):
        touch(me)
        ok, name, coins, rare = fish_take(me.id)
        if not ok:
            return await reply(update, name) or True
        if coins:
            give_coins(me.id, coins)
        who = link(me.id, disp(me))
        if rare:
            await reply(update, f"✨ {who} вытащил(а) {name}! +{coins} {COIN} 🎉")
        elif coins:
            await reply(update, f"🎣 {who} поймал(а) {name}: +{coins} {COIN}")
        else:
            await reply(update, f"🎣 {who} вытащил(а) {name}. Повезёт в следующий раз")
        return True
    if low in ("огород", "грядки", "мой огород"):
        touch(me)
        await _show(update.effective_message, me)
        return True
    return False


async def _show(msg, me):
    from handlers.finance import _send_photo
    buf = await asyncio.to_thread(garden_card, disp(me), me.id)
    await _send_photo(msg, buf, _cap(me.id), reply_markup=_kb(me.id))


async def on_farm_btn(update, context):
    q = update.callback_query
    p = (q.data or "").split(":")
    if len(p) < 3 or not p[1].isdigit():
        return await q.answer()
    if q.from_user.id != int(p[1]):
        return await q.answer("Это чужой огород. Свой: «огород»", show_alert=True)
    me = q.from_user
    touch(me)
    act = p[2]
    if act == "plant" and len(p) >= 5:
        ok, msg = plant(me.id, int(p[3]), p[4])
        await q.answer(msg, show_alert=not ok)
    elif act == "harvest":
        lines, coins, xp = harvest(me.id)
        if not lines:
            return await q.answer("Пока нечего собирать", show_alert=True)
        if xp:
            from services.xp import give_xp
            give_xp(me.id, xp)
        await q.answer(f"Урожай собран: +{coins} славКоин")
        await context.bot.send_message(q.message.chat_id, f"🧺 {link(me.id, disp(me))} собрал(а) урожай:\n" + "\n".join(lines) +
                                       f"\nИтого +{coins} {COIN}, +{xp} опыта", parse_mode=HTML)
    else:
        await q.answer()
    from handlers.finance import _send_photo
    try:
        from telegram import InputMediaPhoto
        buf = await asyncio.to_thread(garden_card, disp(me), me.id)
        await q.edit_message_media(InputMediaPhoto(buf, caption=_cap(me.id), parse_mode=HTML), reply_markup=_kb(me.id))
    except Exception:
        pass
