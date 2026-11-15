# -*- coding: utf-8 -*-
"""Рынок игроков: продажа купленных в магазине подарков другим игрокам за монеты."""

import re
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import ALLOWED
from core.helpers import group_only, reply
from core.utils import disp, esc, link, touch, urow
from database.db import db
from services.economy import COIN, coins_of
from services.finance import gift_left, mark_gift_bought

MARKET_FEE = 5          # комиссия рынка, % (монеты сгорают)
MAX_PRICE = 1_000_000
MAX_LISTINGS = 5        # лотов одновременно от одного игрока


def _fee(price):
    return price * MARKET_FEE // 100


@group_only
async def cmd_gifts(update, context):
    me = update.effective_user
    rows = db.execute("SELECT * FROM orders WHERE user_id=? AND status IN ('new','done') ORDER BY id DESC LIMIT 30",
                      (me.id,)).fetchall()
    if not rows:
        return await reply(update, "У тебя нет подарков из магазина. Загляни в «магазин» 🛍")
    lines = ["🎁 <b>Твои подарки</b>"]
    for r in rows:
        mark = "" if r["status"] == "done" else " · ждёт выдачи"
        lines.append(f"#{r['id']} · {esc(r['item'])} ({r['price']} {COIN}){mark}")
    lines.append(f"\nПродать другим: «продать 5 300» (номер подарка и цена). Комиссия {MARKET_FEE}%. "
                 "Рынок: «рынок»")
    await reply(update, "\n".join(lines))


@group_only
async def cmd_sell(update, context):
    args = list(context.args or [])
    if len(args) < 2 or not args[0].lstrip("#").isdigit() or not args[1].isdigit():
        return await reply(update, "Напиши: «продать 5 300» — номер подарка (см. «подарки») и цена в монетах")
    me = update.effective_user
    touch(me)
    oid, price = int(args[0].lstrip("#")), int(args[1])
    if not 1 <= price <= MAX_PRICE:
        return await reply(update, f"Цена должна быть от 1 до {MAX_PRICE} {COIN}")
    n = db.execute("SELECT COUNT(*) FROM market WHERE seller=? AND status='active'", (me.id,)).fetchone()[0]
    if n >= MAX_LISTINGS:
        return await reply(update, f"Не больше {MAX_LISTINGS} лотов одновременно. Сними лишний: «снять 3»")
    o = db.execute("SELECT * FROM orders WHERE id=? AND user_id=? AND status IN ('new','done')",
                   (oid, me.id)).fetchone()
    if not o:
        return await reply(update, "Такого подарка у тебя нет. Список: «подарки»")
    db.execute("UPDATE orders SET status='market' WHERE id=?", (oid,))
    cur = db.execute("INSERT INTO market(order_id,seller,seller_name,item,price,prev_status,created) "
                     "VALUES(?,?,?,?,?,?,?)", (oid, me.id, disp(me), o["item"], price, o["status"], time.time()))
    db.commit()
    await reply(update, f"🏷 Лот <b>#{cur.lastrowid}</b>: «{esc(o['item'])}» за {price} {COIN}\n"
                        f"Покупатель платит {price}, ты получишь {price - _fee(price)} (комиссия {MARKET_FEE}%). "
                        f"Снять: «снять {cur.lastrowid}». Смотреть: «рынок»")


@group_only
async def cmd_unsell(update, context):
    args = [a.lstrip("#") for a in (context.args or [])]
    if not args or not args[0].isdigit():
        return await reply(update, "Напиши: «снять 3» — номер лота из «рынок»")
    me = update.effective_user
    m = db.execute("SELECT * FROM market WHERE id=? AND seller=? AND status='active'",
                   (int(args[0]), me.id)).fetchone()
    if not m:
        return await reply(update, "Твоего активного лота с таким номером нет")
    db.execute("UPDATE market SET status='cancel' WHERE id=?", (m["id"],))
    db.execute("UPDATE orders SET status=? WHERE id=?", (m["prev_status"], m["order_id"]))
    db.commit()
    await reply(update, f"Лот #{m['id']} снят, «{esc(m['item'])}» снова у тебя 🎁")


@group_only
async def cmd_market(update, context):
    rows = db.execute("SELECT * FROM market WHERE status='active' ORDER BY id DESC LIMIT 15").fetchall()
    if not rows:
        return await reply(update, "🏪 На рынке пусто. Продай подарок: «подарки» → «продать 5 300»")
    lines = ["🏪 <b>Рынок игроков</b>\n"]
    kb = []
    for r in rows:
        lines.append(f"<b>#{r['id']}</b> · {esc(r['item'])} — {r['price']} {COIN} · {link(r['seller'], r['seller_name'])}")
        kb.append([InlineKeyboardButton(f"Купить #{r['id']} · {r['price']} славКоин", callback_data=f"mk:buy:{r['id']}")])
    lines.append(f"\nТвой баланс: {coins_of(update.effective_user.id)} {COIN}")
    await reply(update, "\n".join(lines), reply_markup=InlineKeyboardMarkup(kb[:10]))


async def on_market_btn(update, context):
    q = update.callback_query
    if not q.message or q.message.chat_id not in ALLOWED:
        return await q.answer()
    parts = (q.data or "").split(":")
    if len(parts) != 3 or parts[1] != "buy" or not parts[2].isdigit():
        return await q.answer()
    me = q.from_user
    touch(me)
    m = db.execute("SELECT * FROM market WHERE id=?", (int(parts[2]),)).fetchone()
    if not m or m["status"] != "active":
        return await q.answer("Лот уже продан или снят", show_alert=True)
    if m["seller"] == me.id:
        return await q.answer("Это твой лот", show_alert=True)
    gl = gift_left(urow(me.id))
    if gl > 0:
        return await q.answer(f"Пауза после покупки подарка ещё {gl // 3600 + 1} ч", show_alert=True)
    if coins_of(me.id) < m["price"]:
        return await q.answer(f"Не хватает славКоинов: нужно {m['price']}", show_alert=True)
    cur = db.execute("UPDATE market SET status='sold', buyer=? WHERE id=? AND status='active'", (me.id, m["id"]))
    if cur.rowcount == 0:
        db.commit()
        return await q.answer("Лот уже продан", show_alert=True)
    gain = m["price"] - _fee(m["price"])
    db.execute("UPDATE users SET coins=coins-? WHERE user_id=?", (m["price"], me.id))
    db.execute("UPDATE users SET coins=coins+? WHERE user_id=?", (gain, m["seller"]))
    db.execute("UPDATE orders SET user_id=?, name=?, status=? WHERE id=?",
               (me.id, disp(me), m["prev_status"], m["order_id"]))
    mark_gift_bought(me.id)
    db.commit()
    await q.answer("Куплено! 🎉")
    await context.bot.send_message(
        q.message.chat_id,
        f"🤝 {link(me.id, disp(me))} купил «{esc(m['item'])}» у {link(m['seller'], m['seller_name'])} "
        f"за {m['price']} {COIN} (продавец получил {gain}). Подарок #{m['order_id']} теперь у покупателя",
        parse_mode="HTML")
