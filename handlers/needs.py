# -*- coding: utf-8 -*-
"""«поесть» / «купить еду» (магазин, кафе, ресторан) и «поспать» (мини-игра из трёх шагов)."""

import random

from telegram import InlineKeyboardButton as B, InlineKeyboardMarkup

from config import ALLOWED, HTML
from core.helpers import reply
from core.utils import disp, link, touch, urow
from services.economy import COIN, coins_of, give_coins
from services.needs import FOOD, is_heavy, mark, missing, state

FOOD_WORDS = {"поесть", "купить еду", "еда", "пообедать", "перекусить", "купить поесть"}
SLEEP_WORDS = {"поспать", "лечь спать", "сон", "спать"}
STEPS = ["💡 Выключить свет", "🪟 Закрыть шторы", "📵 Убрать телефон", "🛏 Лечь"]


def banner(uid):
    if not is_heavy(uid):
        return ""
    m = missing(uid)
    if m:
        return ("\n\n⚫ <b>Тяжёлый день!</b> Зарплата вдвое меньше, пока не " + " и не ".join(
            {"поесть": "поешь («поесть»)", "поспать": "поспишь («поспать»)"}[x] for x in m) + ".")
    return "\n\n⚫ Тяжёлый день, но ты поел и выспался: зарплата полная 💪"


def _food_kb(uid):
    return InlineKeyboardMarkup([[B(f"{n} · {p} {COIN} ({w})", callback_data=f"nd:{uid}:eat:{k}")]
                                 for k, (n, p, w) in FOOD.items()])


def _sleep_kb(uid, done):
    order = list(range(len(STEPS)))
    random.Random(uid + len(done)).shuffle(order)
    return InlineKeyboardMarkup([[B(("✅ " if i in done else "") + STEPS[i], callback_data=f"nd:{uid}:sl:{i}")] for i in order])


async def handle_needs_text(update, context, low, text):
    low = low.strip()
    if low not in FOOD_WORDS and low not in SLEEP_WORDS:
        return False
    if update.effective_chat.id not in ALLOWED:
        return False
    me = update.effective_user
    touch(me)
    fed, slept = state(me.id)
    if low in FOOD_WORDS:
        if fed:
            await reply(update, "🍽 Ты сегодня уже поел(а). Завтра снова проголодаешься.")
        else:
            await reply(update, f"🍽 <b>Что берём?</b> Баланс: {coins_of(me.id)} {COIN}", reply_markup=_food_kb(me.id))
    else:
        if slept:
            await reply(update, "😴 Ты сегодня уже выспал(ся).")
        else:
            await reply(update, "😴 <b>Пора спать.</b> Нажми шаги по порядку: свет → шторы → телефон → лечь.",
                        reply_markup=_sleep_kb(me.id, []))
    return True


async def on_needs_btn(update, context):
    q = update.callback_query
    p = (q.data or "").split(":")
    if len(p) < 4 or not p[1].isdigit():
        return await q.answer()
    if q.from_user.id != int(p[1]):
        return await q.answer("Это не твоё меню", show_alert=True)
    uid = int(p[1])
    if p[2] == "eat":
        if state(uid)[0]:
            return await q.answer("Ты уже поел(а)", show_alert=True)
        it = FOOD.get(p[3])
        if not it or not urow(uid):
            return await q.answer()
        if coins_of(uid) < it[1]:
            return await q.answer(f"Не хватает: нужно {it[1]} {COIN}", show_alert=True)
        give_coins(uid, -it[1])
        mark(uid, "fed")
        await q.answer("Вкусно!")
        return await q.edit_message_text(f"{it[0]} из места «{it[2]}»: {link(uid, disp(q.from_user))} поел(а) за {it[1]} {COIN} 😋" + banner(uid), parse_mode=HTML)
    if p[2] == "sl":
        if state(uid)[1]:
            return await q.answer("Ты уже выспал(ся)", show_alert=True)
        done = [int(x) for x in context.user_data.get("nd_sl", [])]
        i = int(p[3])
        if i != len(done):
            context.user_data["nd_sl"] = []
            await q.answer("Не по порядку! Начни сначала", show_alert=True)
            return await q.edit_message_reply_markup(_sleep_kb(uid, []))
        done.append(i)
        if len(done) == len(STEPS):
            context.user_data["nd_sl"] = []
            mark(uid, "slept")
            await q.answer("Спокойной ночи!")
            return await q.edit_message_text(f"😴 {link(uid, disp(q.from_user))} выспал(ся) и полон сил ✨" + banner(uid), parse_mode=HTML)
        context.user_data["nd_sl"] = done
        await q.answer("Ок")
        await q.edit_message_reply_markup(_sleep_kb(uid, done))
