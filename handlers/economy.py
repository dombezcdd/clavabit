# -*- coding: utf-8 -*-
"""Монеты, магазин и заказы."""

import re
import time

from core.helpers import group_only, reply, resolve_target, target_user
from core.ranks import need
from core.utils import disp, esc, link, owner_mention, touch, urow
from database.db import db
from services.economy import COIN, coins_of, give_coins, shop_price


@group_only
async def cmd_balance(update, context):
    u = target_user(update) or update.effective_user
    touch(u)
    r = urow(u.id)
    await reply(update, f"{COIN} Баланс {link(u.id, r['name'])}: <b>{r['coins'] or 0}</b>\n"
                        f"Монеты дают за сообщения (1 за каждые 30) и за работу («найти работу»).\n"
                        f"Потратить: «магазин»")


@group_only
async def cmd_bonus(update, context):
    await reply(update, "🎁 Ежедневного бонуса больше нет. Монеты начисляются за сообщения "
                        "(1 монета за каждые 30) и за работу: «найти работу».")


@group_only
async def cmd_topcoins(update, context):
    rows = db.execute("SELECT user_id,name,coins FROM users WHERE coins>0 "
                      "ORDER BY coins DESC LIMIT 10").fetchall()
    if not rows:
        return await reply(update, "Пока ни у кого нет монет. Пиши в чат и работай: «найти работу» 🪙")
    medals = ["🥇", "🥈", "🥉"]
    lines = [f"{COIN} <b>Топ по монетам</b>"]
    for i, r in enumerate(rows):
        lines.append(f"{medals[i] if i < 3 else str(i + 1) + '.'} {link(r['user_id'], r['name'])} — {r['coins']}")
    await reply(update, "\n".join(lines))


@group_only
async def cmd_duels(update, context):
    u = target_user(update) or update.effective_user
    touch(u)
    r = urow(u.id)
    w, l = r["duel_w"] or 0, r["duel_l"] or 0
    lines = [f"⚔️ <b>Дуэли {esc(r['name'])}</b>: побед {w}, поражений {l}"
             + (f" ({round(100 * w / (w + l))}%)" if w + l else "")]
    top = db.execute("SELECT user_id,name,duel_w,duel_l FROM users WHERE duel_w>0 "
                     "ORDER BY duel_w DESC LIMIT 5").fetchall()
    if top:
        lines.append("\n🏆 <b>Лучшие дуэлянты</b>")
        for i, t in enumerate(top, 1):
            lines.append(f"{i}. {link(t['user_id'], t['name'])} — {t['duel_w']} поб. / {t['duel_l']} пор.")
    else:
        lines.append("Дуэлей ещё не было. Ответь «дуэль» на сообщение соперника")
    await reply(update, "\n".join(lines))


@group_only
async def cmd_shop(update, context):
    items = db.execute("SELECT * FROM shop_items WHERE active=1 ORDER BY id").fetchall()
    if not items:
        return await reply(update, "🛍 Магазин пока пуст. Админы добавят товары командой "
                                   "«добавить товар Название цена»")
    lines = [f"🛍 <b>Магазин подарков</b>\nТвой баланс: <b>{coins_of(update.effective_user.id)}</b> {COIN}\n"]
    for it in items:
        stock = "" if it["stock"] < 0 else f" · осталось {it['stock']}"
        lines.append(f"<b>{it['id']}.</b> {esc(it['name'])} — {shop_price(it)} {COIN}{stock}")
    lines.append("\nКупить: «купить 1» (номер товара). Приз выдаёт владелец вручную")
    await reply(update, "\n".join(lines))


@group_only
async def cmd_buy(update, context):
    args = list(context.args or [])
    if not args or not args[0].isdigit():
        return await reply(update, "Напиши: «купить 1» (номер товара из «магазин»)")
    me = update.effective_user
    touch(me)
    it = db.execute("SELECT * FROM shop_items WHERE id=? AND active=1", (int(args[0]),)).fetchone()
    if not it:
        return await reply(update, "Нет такого товара. Список: «магазин»")
    if it["stock"] == 0:
        return await reply(update, "Товар закончился 😔")
    bal = coins_of(me.id)
    price = shop_price(it)
    if bal < price:
        return await reply(update, f"Не хватает монет: нужно {price}, у тебя {bal} {COIN}")
    db.execute("UPDATE users SET coins=coins-? WHERE user_id=?", (price, me.id))
    if it["stock"] > 0:
        db.execute("UPDATE shop_items SET stock=stock-1 WHERE id=?", (it["id"],))
    cur = db.execute("INSERT INTO orders(user_id,name,item,price,created,status) VALUES(?,?,?,?,?, 'new')",
                     (me.id, disp(me), it["name"], price, time.time()))
    db.commit()
    await reply(update, f"✅ {link(me.id, disp(me))} купил «{esc(it['name'])}» за {price} {COIN}\n"
                        f"Заказ <b>#{cur.lastrowid}</b>. {owner_mention()}, нужно выдать приз 🎁\n"
                        f"Остаток: {coins_of(me.id)} {COIN}")


def _parse_item(args):
    """название... цена [остаток] -> (name, price, stock) или None"""
    a = list(args)
    stock = -1
    if len(a) >= 3 and a[-1].isdigit() and a[-2].isdigit():
        stock = int(a.pop())
    if len(a) >= 2 and a[-1].isdigit():
        price = int(a.pop())
        return " ".join(a)[:60], price, stock
    return None


@need("добавить товар")
async def cmd_item_add(update, context):
    p = _parse_item(context.args or [])
    if not p or p[1] < 1:
        return await reply(update, "Формат: добавить товар Мишка 500 (название, цена) "
                                   "или добавить товар Мишка 500 3 (ещё и количество)")
    name, price, stock = p
    cur = db.execute("INSERT INTO shop_items(name,price,stock,active) VALUES(?,?,?,1)", (name, price, stock))
    db.commit()
    await reply(update, f"✅ Товар <b>#{cur.lastrowid}</b> «{esc(name)}» — {price} {COIN}"
                        + ("" if stock < 0 else f", количество {stock}"))


@need("удалить товар")
async def cmd_item_del(update, context):
    a = list(context.args or [])
    if not a or not a[0].isdigit():
        return await reply(update, "Формат: удалить товар 1")
    db.execute("UPDATE shop_items SET active=0 WHERE id=?", (int(a[0]),))
    db.commit()
    await reply(update, f"🗑 Товар #{a[0]} убран из магазина")


@need("выдать монеты")
async def cmd_coins_give(update, context):
    uid, name, rest, err = resolve_target(update, list(context.args or []))
    if err:
        return await reply(update, err)
    nums = [x for x in rest if re.fullmatch(r"-?\d+", x)]
    if not uid or not nums:
        return await reply(update, "Формат: выдать монеты @юзернейм 100 (или ответом: выдать монеты 100; "
                                   "отрицательное число забирает)")
    if not urow(uid):
        return await reply(update, "Этого участника нет в базе бота.")
    n = int(nums[0])
    give_coins(uid, n)
    await reply(update, f"{COIN} {link(uid, name)}: {'+' if n >= 0 else ''}{n}. Баланс: {coins_of(uid)}")


@need("заказы")
async def cmd_orders(update, context):
    rows = db.execute("SELECT * FROM orders WHERE status='new' ORDER BY id LIMIT 30").fetchall()
    if not rows:
        return await reply(update, "Невыданных заказов нет ✅")
    lines = ["📦 <b>Невыданные заказы</b>"]
    for r in rows:
        lines.append(f"#{r['id']} · {link(r['user_id'], r['name'])} · {esc(r['item'])} ({r['price']} {COIN})")
    lines.append("\nПосле выдачи: «выдан 5»")
    await reply(update, "\n".join(lines))


@need("выдан")
async def cmd_order_done(update, context):
    a = list(context.args or [])
    if not a or not a[0].isdigit():
        return await reply(update, "Формат: выдан 5 (номер заказа из «заказы»)")
    r = db.execute("SELECT * FROM orders WHERE id=?", (int(a[0]),)).fetchone()
    if not r:
        return await reply(update, "Нет такого заказа.")
    db.execute("UPDATE orders SET status='done' WHERE id=?", (r["id"],))
    db.commit()
    await reply(update, f"✅ Заказ #{r['id']} выдан: {link(r['user_id'], r['name'])} получил «{esc(r['item'])}»")
