# -*- coding: utf-8 -*-
"""Автопокупка звёздиков за Telegram Stars (XTR): оплатил в чате или в личке, звёздики пришли сразу."""

import time

from telegram import InlineKeyboardButton as B, InlineKeyboardMarkup, LabeledPrice

from config import ALLOWED, HTML, OWNER_ID
from core.helpers import reply
from core.logger import log
from core.utils import disp, esc, touch, urow
from database.db import db
from services.vip import STAR, stars_add, stars_of

PACKS = (10, 25, 50, 100)      # сколько звёздиков в наборе
XTR_PER_STAR = 1               # сколько Telegram Stars стоит 1 звёздик (поменяй, если нужен другой курс)

db.executescript("""
CREATE TABLE IF NOT EXISTS payments(
  charge_id TEXT PRIMARY KEY, user_id INTEGER, stars INTEGER, xtr INTEGER, ts REAL);
""")
db.commit()


def packs_kb(uid):
    rows, row = [], []
    for n in PACKS:
        row.append(B(f"{STAR} {n} · {n * XTR_PER_STAR} Stars", callback_data=f"pay:{uid}:{n}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)


async def show_packs(update, context):
    me = update.effective_user
    touch(me)
    await reply(update, f"{STAR} <b>Пополнение звёздиков</b>\nУ тебя: {stars_of(me.id)}\n"
                        "Оплата Telegram Stars прямо здесь, звёздики приходят сразу. VIP стоит 25 звёздиков.\nВыбери набор:",
                reply_markup=packs_kb(me.id))


async def cmd_stars(update, context):
    await show_packs(update, context)


async def handle_pay_text(update, context, low, text):
    if update.effective_chat.id not in ALLOWED:
        return False
    if low in ("пополнить", "пополнить звёздики", "пополнить звездики", "купить звёздики", "купить звездики", "донат"):
        await show_packs(update, context)
        return True
    return False


async def on_pay_btn(update, context):
    q = update.callback_query
    p = (q.data or "").split(":")
    if len(p) != 3 or not p[1].isdigit() or not p[2].isdigit() or int(p[2]) not in PACKS:
        return await q.answer()
    if q.from_user.id != int(p[1]):
        return await q.answer("Это кнопки другого игрока. Свои: «пополнить»", show_alert=True)
    n = int(p[2])
    touch(q.from_user)
    await q.answer()
    try:
        await context.bot.send_invoice(
            chat_id=q.message.chat_id, title=f"{n} звёздиков", description=f"{n} звёздиков для бота: VIP, пасс и бонусы",
            payload=f"stars:{q.from_user.id}:{n}", currency="XTR", provider_token="",
            prices=[LabeledPrice(f"{n} звёздиков", n * XTR_PER_STAR)])
    except Exception as e:
        log.warning("invoice: %r", e)
        await context.bot.send_message(q.message.chat_id, "Не получилось выставить счёт. Попробуй чуть позже или напиши владельцу.")


def _parse(payload):
    p = (payload or "").split(":")
    if len(p) == 3 and p[0] == "stars" and p[1].isdigit() and p[2].isdigit() and int(p[2]) in PACKS:
        return int(p[1]), int(p[2])
    return None


async def on_precheckout(update, context):
    q = update.pre_checkout_query
    parsed = _parse(q.invoice_payload)
    if not parsed or parsed[0] != q.from_user.id or not urow(q.from_user.id):
        return await q.answer(ok=False, error_message="Счёт устарел, выбери набор заново: «пополнить»")
    await q.answer(ok=True)


async def on_paid(update, context):
    m = update.effective_message
    sp = m.successful_payment
    parsed = _parse(sp.invoice_payload)
    if not parsed:
        log.warning("оплата с чужим payload: %r", sp.invoice_payload)
        return
    uid, n = parsed
    cur = db.execute("INSERT OR IGNORE INTO payments VALUES(?,?,?,?,?)",
                     (sp.telegram_payment_charge_id, uid, n, sp.total_amount, time.time()))
    db.commit()
    if cur.rowcount == 0:         # такая оплата уже была зачислена
        return
    stars_add(uid, n)
    await m.reply_text(f"✅ Оплата прошла! Тебе начислено {n} {STAR}. Баланс: {stars_of(uid)}\nКупить VIP: «купить вип»")
    if OWNER_ID.isdigit():
        try:
            await context.bot.send_message(int(OWNER_ID), f"💳 {esc(disp(update.effective_user))} оплатил {sp.total_amount} Stars → {n} звёздиков "
                                                           f"(charge {sp.telegram_payment_charge_id})")
        except Exception:
            pass
