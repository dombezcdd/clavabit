# -*- coding: utf-8 -*-
"""Дома и питомцы."""

from telegram import InlineKeyboardButton

from core.helpers import reply
from core.utils import disp, esc, link, today, urow
from database.db import db
from handlers.common import life_send, own_kb
from services.economy import coins_of, give_coins
from services.jobs import HOUSES, PETS, PET_FEED_COST, PET_MAX, PET_RUNAWAY_DAYS, my_pets
from services.relations import uname


# ---------- дома ----------
async def life_houses(update, context):
    me = update.effective_user
    row = urow(me.id)
    cur = row["house"] if row["house"] in HOUSES else None
    lines = ["🏠 <b>Недвижимость</b>", f"Твой баланс: {row['coins'] or 0} 🪙"]
    if cur:
        lines.append(f"Сейчас у тебя: {HOUSES[cur][0]} (старое жильё продаётся за 50%)")
    lines.append("Жильё даёт прибавку к зарплате и общее для супругов.\n")
    btns = []
    for k, (name, price, bonus, url) in HOUSES.items():
        lines.append(f"• {name}: {price} 🪙, +{bonus}% к зарплате")
        r = [InlineKeyboardButton(f"🏠 {name} · {price}🪙", callback_data=f"life:house:{me.id}:{k}")]
        if url:
            r.append(InlineKeyboardButton("👀 Посмотреть", url=url))
        btns.append(r)
    await life_send(update, context, "\n".join(lines), kb=own_kb(btns))


async def life_pet_shop(update, context):
    me = update.effective_user
    lines = ["🐾 <b>Зоомагазин</b>", f"Баланс: {coins_of(me.id)} 🪙. Питомцев можно держать до {PET_MAX}.",
             f"Кормить: «покормить питомца» ({PET_FEED_COST} 🪙 в день за каждого). "
             f"Без еды {PET_RUNAWAY_DAYS} дней питомец уходит.\n"]
    btns = []
    for k, (name, price, em) in PETS.items():
        lines.append(f"{em} {name}: {price} 🪙")
        btns.append([InlineKeyboardButton(f"{em} {name} · {price}🪙", callback_data=f"life:pet:{me.id}:{k}")])
    await life_send(update, context, "\n".join(lines), kb=own_kb(btns))


async def life_pet_my(update, context):
    pets = my_pets(update.effective_user.id)
    if not pets:
        return await reply(update, "Питомцев нет. Купить: «купить питомца» 🐾")
    lines = ["🐾 <b>Питомцы</b>"]
    for p in pets:
        em = PETS[p["kind"]][2] if p["kind"] in PETS else "🐾"
        fed = "накормлен сегодня" if p["fed_day"] == today() else "голодный"
        lines.append(f"{em} {esc(p['name'])} ({esc(uname(p['owner']))}): {fed}")
    await reply(update, "\n".join(lines) + "\n\nПереименовать: «назвать питомца Барсик»")


async def life_pet_feed(update, context):
    me = update.effective_user
    pets = [p for p in my_pets(me.id) if p["fed_day"] != today()]
    if not my_pets(me.id):
        return await reply(update, "Питомцев нет. Купить: «купить питомца» 🐾")
    if not pets:
        return await reply(update, "Все питомцы уже сыты сегодня 😺")
    cost = PET_FEED_COST * len(pets)
    if coins_of(me.id) < cost:
        return await reply(update, f"Корм стоит {cost} 🪙, а у тебя {coins_of(me.id)}.")
    give_coins(me.id, -cost)
    for p in pets:
        db.execute("UPDATE pets SET fed_day=? WHERE id=?", (today(), p["id"]))
    db.commit()
    await life_send(update, context, f"🍖 {link(me.id, disp(me))} покормил(а) питомцев: "
                                     + ", ".join(esc(p["name"]) for p in pets) + f" (−{cost} 🪙)",
                    key="пет:кормление", api="feed")


async def life_pet_rename(update, context, new):
    me = update.effective_user
    pets = [p for p in my_pets(me.id) if p["owner"] == me.id]
    if not pets:
        return await reply(update, "У тебя нет своих питомцев.")
    new = new.strip()[:20]
    if not new:
        return await reply(update, "Напиши имя: «назвать питомца Барсик»")
    db.execute("UPDATE pets SET name=? WHERE id=?", (new, pets[-1]["id"]))
    db.commit()
    await reply(update, f"✏️ Теперь питомца зовут <b>{esc(new)}</b>")
