# -*- coding: utf-8 -*-
"""Вирус: «заразить», «аптека», «лечиться», «больные»."""

import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import ALLOWED
from core.helpers import reply, resolve_target, target_user
from core.utils import disp, esc, link, touch, urow
from core.durations import fmt_minutes
from database.db import db
from services.economy import COIN, coins_of
from services.virus import (IMMUNE_HOURS, INFECT_CHANCE, SICK_HOURS, SICK_PAY_MULT, cure, cure_price, is_immune,
                            is_sick, try_infect)

VIRUS_WORDS = {"заразить", "заразить его", "заразить её", "инфицировать"}
CURE_WORDS = {"лечиться", "вылечиться", "купить лекарство", "выпить лекарство", "лекарство"}


async def handle_virus_text(update, context, low, text):
    if update.effective_chat.id not in ALLOWED:
        return False
    first = low.split()[0] if low.split() else ""
    if first == "заразить" and len(low.split()) <= 3:
        return await _infect(update, context, text)
    if low in CURE_WORDS:
        return await _cure(update, update.effective_user)
    if low in ("аптека", "болезнь", "мой вирус"):
        return await _pharmacy(update, update.effective_user)
    if low in ("больные", "заражённые", "зараженные"):
        return await _sick_list(update)
    return False


async def _infect(update, context, text):
    me = update.effective_user
    touch(me)
    t = target_user(update)
    if not t:
        uid, name, _, err = resolve_target(update, text.split()[1:])
        if err:
            await reply(update, err)
            return True
        if not uid:
            await reply(update, "Ответь командой «заразить» на сообщение или напиши «заразить @юзернейм» 🦠")
            return True
    else:
        uid, name = t.id, disp(t)
        if getattr(t, "is_bot", False):
            await reply(update, "Боты неуязвимы 🤖")
            return True
    code, extra = try_infect(me.id, uid)
    who = link(uid, name)
    msg = {
        "self": "Себя заражать нельзя 🙃",
        "none": "Не нашёл такого игрока в базе",
        "cd": f"Вирус ещё размножается. Следующая попытка через {fmt_minutes(extra // 60 + 1)} ⏳",
        "already": f"{who} уже болен(на) 🤒",
        "immune": f"У {who} иммунитет после лечения ещё {fmt_minutes(extra // 60 + 1)} 💉",
        "fail": f"🦠 {link(me.id, disp(me))} чихнул(а) на {who}, но тот(а) увернулся(ась). Заражение не удалось",
        "ok": f"🦠 {link(me.id, disp(me))} заразил(а) {who}! Болезнь {SICK_HOURS} ч: зарплата −{int((1 - SICK_PAY_MULT) * 100)}%. "
              f"Лечение: «аптека»",
    }[code]
    await reply(update, msg)
    return True


async def _pharmacy(update, me):
    touch(me)
    row = urow(me.id)
    if is_sick(row):
        left = (row["sick_until"] - time.time()) // 60 + 1
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"💊 Купить лекарство · {cure_price(row)} славКоин",
                                                         callback_data=f"vir:cure:{me.id}")]])
        await reply(update, f"🤒 Ты болен(на), осталось {fmt_minutes(left)} · зарплата −{int((1 - SICK_PAY_MULT) * 100)}%.\n"
                            f"Лекарство: {cure_price(row)} {COIN} (чем дольше болезнь, тем дороже), после него "
                            f"иммунитет {IMMUNE_HOURS} ч. Баланс: {coins_of(me.id)} {COIN}", reply_markup=kb)
    elif is_immune(row):
        await reply(update, f"💉 У тебя иммунитет ещё {fmt_minutes((row['immune_until'] - time.time()) // 60 + 1)}")
    else:
        await reply(update, f"Ты здоров 💪 Заразить другого: «заразить» (ответом на сообщение), шанс {int(INFECT_CHANCE * 100)}%")
    return True


async def _cure(update, me):
    touch(me)
    row = urow(me.id)
    if not is_sick(row):
        await reply(update, "Ты и так здоров 💪")
        return True
    price = cure_price(row)
    if coins_of(me.id) < price:
        await reply(update, f"Не хватает славКоинов: лекарство {price} {COIN}, у тебя {coins_of(me.id)}")
        return True
    db.execute("UPDATE users SET coins=coins-? WHERE user_id=?", (price, me.id))
    cure(me.id)
    await reply(update, f"💊 {link(me.id, disp(me))} вылечился(ась) за {price} {COIN}. Иммунитет {IMMUNE_HOURS} ч")
    return True


async def _sick_list(update):
    rows = db.execute("SELECT user_id,name,sick_until FROM users WHERE sick_until>? ORDER BY sick_until DESC LIMIT 20",
                      (time.time(),)).fetchall()
    if not rows:
        return await reply(update, "Все здоровы 🎉") or True
    lines = ["🤒 <b>Больные</b>"] + [f"{link(r['user_id'], r['name'] or '?')} — ещё {fmt_minutes((r['sick_until'] - time.time()) // 60 + 1)}"
                                   for r in rows]
    await reply(update, "\n".join(lines))
    return True


async def on_virus_btn(update, context):
    q = update.callback_query
    p = (q.data or "").split(":")
    if len(p) != 3 or p[1] != "cure" or not p[2].isdigit() or q.from_user.id != int(p[2]):
        return await q.answer("Это лекарство не для тебя", show_alert=True)
    row = urow(q.from_user.id)
    if not is_sick(row):
        return await q.answer("Ты уже здоров", show_alert=True)
    price = cure_price(row)
    if coins_of(q.from_user.id) < price:
        return await q.answer(f"Не хватает славКоинов: нужно {price}", show_alert=True)
    db.execute("UPDATE users SET coins=coins-? WHERE user_id=?", (price, q.from_user.id))
    cure(q.from_user.id)
    await q.answer("Вылечился! 💊")
    await context.bot.send_message(q.message.chat_id,
                                   f"💊 {link(q.from_user.id, disp(q.from_user))} вылечился(ась) за {price} {COIN}. "
                                   f"Иммунитет {IMMUNE_HOURS} ч", parse_mode="HTML")
