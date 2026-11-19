# -*- coding: utf-8 -*-
"""Живое табло акций: сообщение само обновляется как биржевой терминал, можно покупать и продавать кнопками."""

import asyncio
import time
from collections import deque

from telegram import InlineKeyboardButton as B, InlineKeyboardMarkup
from telegram.error import BadRequest

from config import ALLOWED, HTML
from core.helpers import reply
from core.logger import log
from core.utils import esc, link, now, touch, urow
from database.db import db
from services.economy import COIN
from services.finance import (HIST_KEEP, STOCK_DAY_LIMIT, buy_stock, find_stock, history, holding, init_stocks, micro_tick,
                              sell_stock, spent_today)

STEP_SEC = 5
SESSION_SEC = 150
BARS = "▁▂▃▄▅▆▇█"
LIVE = {}            # chat_id -> сессия


def _spark(vals, n=22):
    vals = list(vals)[-n:]
    if len(vals) < 2:
        return BARS[3] * 8
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-9:
        return BARS[3] * len(vals)
    return "".join(BARS[min(7, int((v - lo) / (hi - lo) * 7.999))] for v in vals)


def _stocks():
    return db.execute("SELECT * FROM stocks ORDER BY rowid").fetchall()


def _chg(s):
    return (s["price"] - s["prev"]) / s["prev"] * 100 if s["prev"] else 0.0


def _arrow(x):
    return "▲" if x > 0.005 else "▼" if x < -0.005 else "■"


def _clock():
    return now().strftime("%H:%M:%S")


def _left(sess):
    return max(0, int(sess["until"] - time.time()))


def _render_all(sess):
    lines = [f"📡 <b>LIVE · БИРЖА</b>   <code>{_clock()}</code>   🔴 REC", "<pre>"]
    for s in _stocks():
        c = _chg(s)
        sp = _spark(list(sess["pts"].get(s["sym"], [])) or history(s["sym"]))
        lines.append(f"{s['sym']} {s['price']:>7.2f} {_arrow(c)}{c:+5.1f}% {sp}")
    lines.append("</pre>")
    lines.append(f"<i>Жми на тикер: график, покупка и продажа. Табло {_left(sess)} с</i>")
    return "\n".join(lines)


def _render_one(sess, sym):
    s = db.execute("SELECT * FROM stocks WHERE sym=?", (sym,)).fetchone()
    pts = list(sess["pts"].get(sym, []))
    c = _chg(s)
    hi, lo = (max(pts), min(pts)) if pts else (s["price"], s["price"])
    d = (pts[-1] - pts[-2]) if len(pts) > 1 else 0
    spread = max(0.01, round(s["price"] * 0.0015, 2))
    mood = "🟢 покупают" if d > 0 else "🔴 продают" if d < 0 else "⚪ штиль"
    vol = "▮" * min(8, 1 + int(abs(d) / max(0.01, s["price"]) * 1500)) 
    hist = history(sym)
    return (f"📡 <b>LIVE · {s['sym']}</b> · {esc(s['name'])}   <code>{_clock()}</code>\n<pre>"
            f"{s['price']:>8.2f} {COIN} {_arrow(c)} {c:+.2f}%\n"
            f"{_spark(pts or hist, 30)}\n"
            f"за сессию  {lo:.2f} … {hi:.2f}\n"
            f"за сутки   {min(hist):.2f} … {max(hist):.2f}\n"
            f"BID {s['price'] - spread / 2:.2f}  ASK {s['price'] + spread / 2:.2f}\n"
            f"поток {vol:<8} {mood}</pre>\n"
            f"<i>Сделки идут по этой цене. Табло {_left(sess)} с</i>")


def _kb(sess):
    syms = [s["sym"] for s in _stocks()]
    sid = sess["sid"]
    if sess["mode"] == "all":
        rows = [[B(x, callback_data=f"lv:{sid}:o:{x}") for x in syms[i:i + 4]] for i in range(0, len(syms), 4)]
    else:
        x = sess["mode"]
        rows = [[B("🟢 Купить 1", callback_data=f"lv:{sid}:b1:{x}"), B("🟢 ×5", callback_data=f"lv:{sid}:b5:{x}")],
                [B("🔴 Продать 1", callback_data=f"lv:{sid}:s1:{x}"), B("🔴 Всё", callback_data=f"lv:{sid}:sa:{x}")],
                [B("🎞 GIF графика", callback_data=f"lv:{sid}:gif:{x}")],
                [B("⬅️ Табло", callback_data=f"lv:{sid}:all"), B("💼 Портфель", callback_data=f"lv:{sid}:pf")]]
    rows.append([B("⏹ Стоп", callback_data=f"lv:{sid}:stop")])
    return InlineKeyboardMarkup(rows)


GIF_MOVE = 1.2       # % за ~30 секунд, после которого шлём GIF
GIF_GAP = 45         # не чаще раза в N секунд на чат


async def _send_gif(bot, sess, s, force=False):
    """GIF: акция взлетает или падает. Ошибки не мешают табло."""
    try:
        pts = list(sess["pts"].get(s["sym"], []))
        if len(pts) < 3:
            return False
        chg = (pts[-1] - pts[0]) / pts[0] * 100 if pts[0] else 0.0
        import io
        from services.stock_gif import make_gif
        data = await asyncio.to_thread(make_gif, s["sym"], s["name"], pts, pts[-1], chg)
        if not data:
            return False
        bio = io.BytesIO(data)
        bio.name = "stock.gif"
        word = "🚀 взлетает" if chg >= 0 else "📉 падает"
        await bot.send_animation(sess["chat"], bio, caption=f"{word}: <b>{s['sym']}</b> {s['price']:.2f} {COIN} ({chg:+.1f}%)",
                                 parse_mode=HTML, read_timeout=25, write_timeout=25)
        sess["gif_t"] = time.time()
        return True
    except Exception as e:
        log.warning("live gif: %r", e)
        return False


async def _auto_gif(bot, sess):
    if time.time() - sess.get("gif_t", 0) < GIF_GAP:
        return
    best, bc = None, 0.0
    for s in _stocks():
        pts = list(sess["pts"].get(s["sym"], []))[-7:]
        if len(pts) < 5 or not pts[0]:
            continue
        c = (pts[-1] - pts[0]) / pts[0] * 100
        if abs(c) > abs(bc):
            best, bc = s, c
    if best is not None and abs(bc) >= GIF_MOVE:
        sess["gif_t"] = time.time()
        await _send_gif(bot, sess, best)


async def _edit(bot, sess, text, kb):
    if text == sess.get("last") and kb is None:
        return
    try:
        await bot.edit_message_text(text, chat_id=sess["chat"], message_id=sess["msg"], parse_mode=HTML, reply_markup=kb)
        sess["last"] = text
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            log.warning("live edit: %r", e)
    except Exception as e:
        log.warning("live edit: %r", e)


def _render(sess):
    return _render_all(sess) if sess["mode"] == "all" else _render_one(sess, sess["mode"])


async def _loop(bot, sess):
    try:
        while time.time() < sess["until"] and sess["alive"]:
            micro_tick(STEP_SEC - 1)
            for s in _stocks():
                sess["pts"].setdefault(s["sym"], deque(maxlen=40)).append(s["price"])
            await _edit(bot, sess, _render(sess), _kb(sess))
            await _auto_gif(bot, sess)
            await asyncio.sleep(STEP_SEC)
    except asyncio.CancelledError:
        pass
    finally:
        sess["alive"] = False
        if LIVE.get(sess["chat"]) is sess:
            LIVE.pop(sess["chat"], None)
        again = InlineKeyboardMarkup([[B("▶️ Запустить табло", callback_data="lv:new:all")]])
        try:
            await bot.edit_message_text(_render(sess).replace("🔴 REC", "⏹ СТОП"), chat_id=sess["chat"],
                                        message_id=sess["msg"], parse_mode=HTML, reply_markup=again)
        except Exception:
            pass


async def start_live(bot, chat, mode="all", reply_to=None):
    old = LIVE.get(chat)
    if old and old["alive"]:
        return None
    init_stocks()
    sess = {"chat": chat, "mode": mode, "sid": str(int(time.time()) % 100000), "pts": {}, "alive": True,
            "until": time.time() + SESSION_SEC, "last": ""}
    micro_tick(0)
    for s in _stocks():
        sess["pts"][s["sym"]] = deque(history(s["sym"])[-20:] + [s["price"]], maxlen=40)
    m = await bot.send_message(chat, _render(sess), parse_mode=HTML, reply_markup=_kb(sess))
    sess["msg"] = m.message_id
    LIVE[chat] = sess
    sess["task"] = asyncio.create_task(_loop(bot, sess))
    return sess


async def handle_live_text(update, context, low, text):
    if update.effective_chat.id not in ALLOWED:
        return False
    words = low.split()
    if not words or words[0] not in ("табло", "следить", "слежка", "трейдинг") or len(words) > 2:
        return False
    touch(update.effective_user)
    init_stocks()
    mode = "all"
    if len(words) == 2:
        s = find_stock(words[1])
        if not s:
            await reply(update, "Нет такой компании. Список тикеров: «табло»")
            return True
        mode = s["sym"]
    sess = await start_live(context.bot, update.effective_chat.id, mode)
    if sess is None:
        await reply(update, "📡 Табло уже идёт в этом чате, смотри выше. Остановить можно кнопкой «Стоп»")
    return True


async def on_live_btn(update, context):
    q = update.callback_query
    p = (q.data or "").split(":")
    if len(p) < 3:
        return await q.answer()
    chat = q.message.chat_id if q.message else None
    if chat not in ALLOWED:
        return await q.answer()
    if p[1] == "new":
        if await start_live(context.bot, chat, "all") is None:
            return await q.answer("Табло уже идёт", show_alert=True)
        return await q.answer()
    sess = LIVE.get(chat)
    if not sess or sess["sid"] != p[1] or not sess["alive"]:
        return await q.answer("Табло закрыто. Запусти заново: «табло»", show_alert=True)
    act, sym = p[2], (p[3] if len(p) > 3 else "")
    me = q.from_user
    touch(me)
    if act == "stop":
        sess["alive"] = False
        sess["task"].cancel()
        return await q.answer("Табло остановлено")
    if act == "all":
        sess["mode"] = "all"
        await q.answer()
        return await _edit(context.bot, sess, _render(sess), _kb(sess))
    if act == "o":
        sess["mode"] = sym
        await q.answer()
        return await _edit(context.bot, sess, _render(sess), _kb(sess))
    if act == "pf":
        rows = db.execute("SELECT h.*, s.price FROM holdings h JOIN stocks s ON s.sym=h.sym WHERE h.user_id=?", (me.id,)).fetchall()
        if not rows:
            return await q.answer("Портфель пуст", show_alert=True)
        tot = sum(int(r["price"] * r["qty"]) for r in rows)
        pl = tot - sum(r["cost"] for r in rows)
        txt = "; ".join(f"{r['sym']} {r['qty']}" for r in rows)
        return await q.answer(f"{txt}\nСтоимость {tot}, итог {pl:+d} {COIN}", show_alert=True)
    s = db.execute("SELECT * FROM stocks WHERE sym=?", (sym,)).fetchone()
    if not s:
        return await q.answer()
    if act == "gif":
        if time.time() - sess.get("gif_t", 0) < 15:
            return await q.answer("Подожди пару секунд", show_alert=False)
        await q.answer("Рисую GIF…")
        return await _send_gif(context.bot, sess, s, True)
    if act in ("b1", "b5"):
        qty = 1 if act == "b1" else 5
        ok, res = buy_stock(me.id, s, qty)
        return await q.answer(f"📥 Куплено {qty} {sym} по {s['price']:.2f}: −{res} {COIN}" if ok else res, show_alert=not ok)
    if act in ("s1", "sa"):
        h = holding(me.id, sym)
        qty = 1 if act == "s1" else (h["qty"] if h else 1)
        ok, res = sell_stock(me.id, s, qty)
        if not ok:
            return await q.answer(res, show_alert=True)
        net, profit, fee, n = res
        return await q.answer(f"📤 Продано {n} {sym}: +{net} {COIN}, сделка {profit:+d}", show_alert=True)
    await q.answer()
