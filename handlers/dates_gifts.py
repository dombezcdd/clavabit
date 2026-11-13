# -*- coding: utf-8 -*-
"""Свидания, подарки партнёру и семейный счёт."""

import re
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from core.helpers import reply
from core.utils import link, today
from database.db import db
from handlers.minigames import games_text
from services.economy import coins_of, give_coins
from services.media import send_with_pic
from services.relations import ea, is_married, offended_block, pair_of, partner_of, spark_add, uname


# ---------- свидания с выбором места ----------
DATE_PLACES = {"парк": ("🌳 Парк", 0, 50), "кино": ("🎬 Кино", 20, 80),
               "ресторан": ("🍽 Ресторан", 50, 130), "концерт": ("🎤 Концерт", 80, 200)}


def date_kb(uid):
    rows = []
    for k, (nm, cost, gain) in DATE_PLACES.items():
        rows.append([InlineKeyboardButton(f"{nm} · {cost} 🪙 → +{gain} 🔥" if cost else f"{nm} · бесплатно → +{gain} 🔥",
                                          callback_data=f"date:{uid}:{k}")])
    return InlineKeyboardMarkup(rows)


def date_go(uid, place):
    """-> (ok, сообщение). Платит тот, кто выбрал место."""
    row = pair_of(uid)
    if not row:
        return False, "У тебя нет пары"
    if row["date_day"] == today():
        return False, "Сегодня вы уже ходили на свидание 🌹"
    pid = partner_of(row, uid)
    if offended_block(uid, pid):
        return False, "Ваша половинка обижена, действия недоступны"
    nm, cost, gain = DATE_PLACES[place]
    if cost and coins_of(uid) < cost:
        return False, f"Нужно {cost} 🪙, у тебя {coins_of(uid)}"
    if cost:
        give_coins(uid, -cost, commit=False)
    db.execute("UPDATE pairs SET date_day=?, last_action=?, actions=actions+1 WHERE id=?",
               (today(), time.time(), row["id"]))
    db.commit()
    new = spark_add(row["id"], gain, "свидание", uname(uid))
    return True, (f"🌹 {link(uid, uname(uid))} и {link(pid, uname(pid))} сходили на свидание: <b>{nm}</b>!\n"
                  f"+{gain} 🔥 · всего искр: {new}" + (f" · потрачено {cost} 🪙" if cost else ""))


async def on_date_btn(update, context):
    q = update.callback_query
    p = (q.data or "").split(":")
    if len(p) != 3 or not p[1].isdigit() or p[2] not in DATE_PLACES:
        return await q.answer()
    if q.from_user.id != int(p[1]):
        return await q.answer("Это меню не для тебя", show_alert=True)
    ok, msg = date_go(int(p[1]), p[2])
    if not ok:
        return await q.answer(msg, show_alert=True)
    await q.answer()
    try:
        await q.message.delete()
    except Exception:
        pass
    await send_with_pic(context.bot, q.message.chat_id, msg, ["свид:" + p[2]])


# ---------- подарки партнёру ----------
GIFTS = {"цветы": ("💐 Цветы", 90, 40), "шоколад": ("🍫 Шоколад", 60, 25),
         "мишка": ("🧸 Плюшевый мишка", 250, 110), "украшение": ("💎 Украшение", 700, 320)}


GIFT_MENU_WORDS = {"подарок партнёру", "подарок партнеру", "подарить партнёру", "подарить партнеру"}


def gift_kb(uid):
    return InlineKeyboardMarkup([[InlineKeyboardButton(f"{nm} · {cost} 🪙 → +{gain} 🔥",
                                                       callback_data=f"gift:{uid}:{k}")]
                                 for k, (nm, cost, gain) in GIFTS.items()])


def gift_give(uid, key):
    row = pair_of(uid)
    if not row:
        return False, "У тебя нет пары"
    pid = partner_of(row, uid)
    if offended_block(uid, pid):
        return False, "Ваша половинка обижена, действия недоступны"
    nm, cost, gain = GIFTS[key]
    if coins_of(uid) < cost:
        return False, f"Нужно {cost} 🪙, у тебя {coins_of(uid)}"
    give_coins(uid, -cost, commit=False)
    new = spark_add(row["id"], gain, "подарок", uname(uid))
    return True, (f"🎁 {link(uid, uname(uid))} подарил(а) {link(pid, uname(pid))}: {nm}!\n"
                  f"+{gain} 🔥 · всего искр: {new}").replace("(а)", ea(uid))


async def on_gift_btn(update, context):
    q = update.callback_query
    p = (q.data or "").split(":")
    if len(p) != 3 or not p[1].isdigit() or p[2] not in GIFTS:
        return await q.answer()
    if q.from_user.id != int(p[1]):
        return await q.answer("Это меню не для тебя", show_alert=True)
    ok, msg = gift_give(int(p[1]), p[2])
    if not ok:
        return await q.answer(msg, show_alert=True)
    await q.answer("Подарок отправлен 🎁")
    await send_with_pic(context.bot, q.message.chat_id, msg, [])


# ---------- семейный счёт ----------
async def handle_v21(update, context, clean):
    if await games_text(update, context, clean, clean):
        return True
    me = update.effective_user
    msg = update.effective_message
    m_in = re.match(r"^(?:в семью|положить в семью|пополнить семью)\s+(\d{1,7})$", clean)
    m_out = re.match(r"^(?:из семьи|снять из семьи|снять с семьи)\s+(\d{1,7})$", clean)
    gm = re.match(r"^подарить\s+(цветы|шоколад|мишка|мишку|украшение)$", clean)
    if not (m_in or m_out or gm or clean in GIFT_MENU_WORDS
            or clean in ("семейный счёт", "семейный счет", "семейный бюджет", "общий счёт", "общий счет")):
        return False
    row = pair_of(me.id)
    if gm or clean in GIFT_MENU_WORDS:
        if not row:
            return False
        if gm:
            key = "мишка" if gm.group(1) == "мишку" else gm.group(1)
            ok, text = gift_give(me.id, key)
            await send_with_pic(context.bot, update.effective_chat.id, text if ok else "🙁 " + text, [],
                                reply_to=msg.message_id)
        else:
            await send_with_pic(context.bot, update.effective_chat.id, "🎁 Что подарим половинке?", [],
                                reply_to=msg.message_id, markup=gift_kb(me.id))
        return True
    if not row or not is_married(row):
        return False
    bank = row["bank"] or 0
    if m_in:
        n = int(m_in.group(1))
        cur = db.execute("UPDATE users SET coins=coins-? WHERE user_id=? AND coins>=?", (n, me.id, n))
        if n <= 0 or cur.rowcount == 0:
            db.rollback()
            return await reply(update, f"У тебя {coins_of(me.id)} 🪙, этого мало.") or True
        db.execute("UPDATE pairs SET bank=bank+? WHERE id=?", (n, row["id"]))
        db.commit()
        await reply(update, f"🏦 {n} 🪙 положено на семейный счёт. Теперь там {bank + n} 🪙")
    elif m_out:
        n = int(m_out.group(1))
        cur = db.execute("UPDATE pairs SET bank=bank-? WHERE id=? AND bank>=?", (n, row["id"], n))
        if n <= 0 or cur.rowcount == 0:
            db.rollback()
            return await reply(update, f"На семейном счёте {bank} 🪙, этого мало.") or True
        give_coins(me.id, n, commit=False)
        db.commit()
        await reply(update, f"🏦 Снято {n} 🪙. На семейном счёте осталось {bank - n} 🪙")
    else:
        await reply(update, f"🏦 <b>Семейный счёт</b>: {bank} 🪙\n«в семью 100» положить, «из семьи 100» снять")
    return True
