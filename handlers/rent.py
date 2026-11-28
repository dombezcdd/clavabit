# -*- coding: utf-8 -*-
"""Аренда NFT-юзернеймов и подарков на 2 дня. Игрок платит славКоинами, владелец выдаёт вручную в личке.
Игрок: «аренда», «мои аренды». Владелец: «аренда добавить юзернейм @имя 500», «аренда добавить подарок Название 300»,
«аренда убрать 3», «аренды» (кто сейчас арендует)."""

import io
import re
import time

from PIL import Image, ImageDraw
from telegram import InlineKeyboardButton as B, InlineKeyboardMarkup

from config import ALLOWED, HTML
from core.helpers import reply
from core.utils import disp, esc, is_owner, link, touch, urow
from database.db import db
from services.economy import COIN, coins_of, give_coins
from services.monopoly_board import _font

DAYS = 2
ADD_RE = re.compile(r"^аренда\s+добавить\s+(юзернейм|подарок)\s+(.+?)\s+(\d{1,6})$", re.I)


def _init():
    db.execute("CREATE TABLE IF NOT EXISTS rent_items(id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, title TEXT, "
               "price INTEGER, active INTEGER DEFAULT 1)")
    db.execute("CREATE TABLE IF NOT EXISTS rent_orders(id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER, user_id INTEGER, "
               "status TEXT, created REAL, until REAL)")


def _items():
    _init()
    return db.execute("SELECT * FROM rent_items WHERE active=1 ORDER BY id").fetchall()


def _left(t):
    h = max(0, int((t - time.time()) // 3600))
    return f"{h // 24} д {h % 24} ч" if h >= 24 else f"{h} ч"


def card(items):
    W, tw, th, g = 900, 420, 150, 20
    rows = max(1, (len(items) + 1) // 2)
    H = 110 + rows * (th + g)
    img = Image.new("RGB", (W, H), (16, 14, 36))
    d = ImageDraw.Draw(img)
    d.text((W // 2, 44), "АРЕНДА", font=_font(36, True), fill=(250, 205, 90), anchor="mm")
    d.text((W // 2, 82), f"NFT-юзернеймы и подарки на {DAYS} дня", font=_font(18), fill=(190, 195, 225), anchor="mm")
    for i, it in enumerate(items):
        x, y = 20 + (i % 2) * (tw + 20), 108 + (i // 2) * (th + g)
        gift = it["kind"] == "подарок"
        col = (230, 110, 170) if gift else (80, 150, 250)
        d.rounded_rectangle((x, y, x + tw, y + th), 20, fill=(30, 32, 58), outline=col, width=3)
        d.ellipse((x + 18, y + 25, x + 108, y + 115), fill=col)
        if gift:
            d.rectangle((x + 40, y + 55, x + 86, y + 98), fill=(255, 255, 255))
            d.rectangle((x + 60, y + 55, x + 66, y + 98), fill=col)
            d.rectangle((x + 40, y + 70, x + 86, y + 76), fill=col)
            d.ellipse((x + 46, y + 38, x + 63, y + 56), outline=(255, 255, 255), width=4)
            d.ellipse((x + 63, y + 38, x + 80, y + 56), outline=(255, 255, 255), width=4)
        else:
            d.text((x + 63, y + 70), "@", font=_font(56, True), fill=(255, 255, 255), anchor="mm")
        t = it["title"][:20]
        d.text((x + 124, y + 42), t, font=_font(26 if len(t) < 14 else 21, True), fill=(255, 255, 255), anchor="lm")
        d.text((x + 124, y + 82), f"{it['price']} СК · {DAYS} дня", font=_font(24, True), fill=(130, 235, 170), anchor="lm")
        d.text((x + 124, y + 118), f"№{it['id']} · " + ("подарок" if gift else "NFT-юзернейм"), font=_font(17), fill=(190, 195, 225), anchor="lm")
    bio = io.BytesIO()
    img.save(bio, "JPEG", quality=88)
    bio.seek(0)
    return bio


async def handle_rent_text(update, context, low, text):
    low = low.strip()
    me = update.effective_user
    if low in ("аренда", "арендовать", "аренда юзернеймов", "аренда подарков"):
        if update.effective_chat.id not in ALLOWED and update.effective_chat.type != "private":
            return False
        touch(me)
        items = _items()
        if not items:
            await reply(update, "🛍 Аренда пока пуста, скоро добавим лоты.")
            return True
        kb = InlineKeyboardMarkup([[B(f"{'🎁' if i['kind'] == 'подарок' else '@'} {i['title'][:22]} · {i['price']} СК",
                                      callback_data=f"rn:buy:{me.id}:{i['id']}")] for i in items])
        cap = (f"🛍 <b>Аренда на {DAYS} дня</b>\nБаланс: {coins_of(me.id)} {COIN}. Оплатил, и владелец выдаст лот "
               "тебе в личку. По окончании срока вернёшь.")
        from handlers.finance import _send_photo
        await _send_photo(update.effective_message, lambda: card(items), cap, reply_markup=kb)
        return True
    if low in ("мои аренды",):
        rows = db.execute("SELECT o.*, i.title FROM rent_orders o JOIN rent_items i ON i.id=o.item_id "
                          "WHERE o.user_id=? AND o.status IN ('new','active') ORDER BY o.id DESC", (me.id,)).fetchall()
        _init()
        if not rows:
            await reply(update, "Активных аренд нет. «аренда» — выбрать лот")
        else:
            await reply(update, "🛍 <b>Твои аренды</b>\n" + "\n".join(
                f"• {esc(r['title'])}: " + ("ждёт выдачи от владельца" if r["status"] == "new" else f"до конца {_left(r['until'])}")
                for r in rows))
        return True
    if not is_owner(me):
        return False
    m = ADD_RE.match(text.strip())
    if m or low.startswith("аренда убрать") or low == "аренды":
        _init()
        if m:
            db.execute("INSERT INTO rent_items(kind,title,price) VALUES(?,?,?)", (m.group(1).lower(), m.group(2).strip(), int(m.group(3))))
            db.commit()
            await reply(update, f"✅ Добавлено в аренду: {esc(m.group(2))} за {m.group(3)} {COIN}")
        elif low == "аренды":
            rows = db.execute("SELECT o.*, i.title FROM rent_orders o JOIN rent_items i ON i.id=o.item_id "
                              "WHERE o.status IN ('new','active') ORDER BY o.id").fetchall()
            await reply(update, "🛍 <b>Аренды сейчас</b>\n" + ("\n".join(
                f"• #{r['id']} {esc(r['title'])} → {link(r['user_id'], esc(str(r['user_id'])))}: "
                + ("ждёт выдачи" if r["status"] == "new" else f"ещё {_left(r['until'])}") for r in rows) or "пусто"))
        else:
            n = re.sub(r"\D", "", low)
            db.execute("UPDATE rent_items SET active=0 WHERE id=?", (int(n or 0),))
            db.commit()
            await reply(update, f"Лот №{n} убран из аренды.")
        return True
    return False


async def on_rent_btn(update, context):
    q = update.callback_query
    p = (q.data or "").split(":")
    if len(p) < 4:
        return await q.answer()
    _init()
    me = q.from_user
    if p[1] == "buy":
        if me.id != int(p[2]):
            return await q.answer("Это не твоё меню. Открой: «аренда»", show_alert=True)
        it = db.execute("SELECT * FROM rent_items WHERE id=? AND active=1", (int(p[3]),)).fetchone()
        if not it or not urow(me.id):
            return await q.answer("Лот недоступен", show_alert=True)
        busy = db.execute("SELECT 1 FROM rent_orders WHERE item_id=? AND status IN ('new','active')", (it["id"],)).fetchone()
        if busy:
            return await q.answer("Этот лот уже арендован, загляни позже", show_alert=True)
        if coins_of(me.id) < it["price"]:
            return await q.answer(f"Не хватает: нужно {it['price']} {COIN}", show_alert=True)
        give_coins(me.id, -it["price"])
        cur = db.execute("INSERT INTO rent_orders(item_id,user_id,status,created) VALUES(?,?,'new',?)", (it["id"], me.id, time.time()))
        db.commit()
        oid = cur.lastrowid
        await q.answer("Оплачено! Владелец выдаст в личке", show_alert=True)
        from config import OWNER_ID
        from database.state import state_get
        try:
            await context.bot.send_message(int(OWNER_ID or state_get("owner_id")), f"🛍 <b>Новая аренда #{oid}</b>\n{esc(it['title'])} ({it['kind']}) на {DAYS} дня\n"
                                           f"Арендатор: {link(me.id, disp(me))} (id {me.id}). Выдай и нажми кнопку.", parse_mode=HTML,
                                           reply_markup=InlineKeyboardMarkup([[B("✅ Выдал", callback_data=f"rn:done:{oid}:0")]]))
        except Exception:
            pass
    elif p[1] == "done":
        from core.utils import is_owner as _io
        if not _io(me):
            return await q.answer("Только владелец", show_alert=True)
        o = db.execute("SELECT * FROM rent_orders WHERE id=? AND status='new'", (int(p[2]),)).fetchone()
        if not o:
            return await q.answer("Уже выдано", show_alert=True)
        until = time.time() + DAYS * 86400
        db.execute("UPDATE rent_orders SET status='active', until=? WHERE id=?", (until, o["id"]))
        db.commit()
        await q.answer("Отмечено")
        await q.edit_message_text(q.message.text + f"\n\n✅ Выдано, срок {DAYS} дня")
        try:
            await context.bot.send_message(o["user_id"], f"✅ Лот выдан на {DAYS} дня. Приятного пользования! Не забудь вернуть в срок.")
        except Exception:
            pass
        if context.job_queue:
            async def end(ctx, oid=o["id"], uid=o["user_id"]):
                db.execute("UPDATE rent_orders SET status='done' WHERE id=?", (oid,))
                db.commit()
                try:
                    await ctx.bot.send_message(uid, "⌛ Срок аренды закончился. Верни лот владельцу, спасибо!")
                except Exception:
                    pass
            context.job_queue.run_once(end, DAYS * 86400)
    else:
        await q.answer()
