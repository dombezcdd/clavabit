# -*- coding: utf-8 -*-
"""Бизнес и биржа: «бизнес», «собрать доход», «биржа», «купить акции КЛВ 5», «портфель», «топ инвесторов»."""

import asyncio
import re
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest, NetworkError, RetryAfter, TimedOut

from config import ALLOWED, CHAT_ID, HTML, QUIET_HOURS
from core.durations import fmt_minutes
from core.logger import log
from core.helpers import reply
from core.utils import disp, esc, link, now, touch, urow
from database.db import db
from database.state import state_get
from handlers.monopoly import SLOW
from services.charts import alert, overview
from services.virus import BOOST_PCT, has_boost
from services.economy import COIN, coins_of, give_coins
from services.finance import (BIZ, BIZ_CAP_H, STOCK_ALERT, STOCK_DAY_LIMIT, STOCK_FEE, STOCK_MAX_QTY, biz_accrued,
                              biz_of, biz_roll_event, biz_upgrade_cost, buy_stock, find_stock, history, holding, pop_event,
                              init_stocks, sell_stock, spent_today, tick_prices, STOCK_TICK_SEC)

BUY_RE = re.compile(r"^купить акци[июя]\s+(\S+)(?:\s+(\d+))?$")
SELL_RE = re.compile(r"^продать акци[июя]\s+(\S+)(?:\s+(\d+|все|всё))?$")


async def handle_finance_text(update, context, low, text):
    if update.effective_chat.id not in ALLOWED:
        return False
    me = update.effective_user
    if low in ("бизнес", "мой бизнес"):
        return await _biz_info(update, me)
    if low in ("купить бизнес", "открыть бизнес"):
        return await _biz_buy(update, me)
    if low in ("улучшить бизнес", "прокачать бизнес"):
        return await _biz_up(update, me)
    if low in ("собрать доход", "доход", "собрать"):
        return await _biz_collect(update, me)
    if low == "продать бизнес":
        return await _biz_sell(update, me)
    if low in ("биржа", "акции", "курс акций", "котировки"):
        return await _market(update, context)
    if low in ("портфель", "мои акции"):
        return await _portfolio(update, me)
    if low in ("топ инвесторов", "инвесторы"):
        return await _top(update)
    m = BUY_RE.match(low)
    if m:
        return await _buy(update, me, m.group(1), int(m.group(2) or 1))
    m = SELL_RE.match(low)
    if m:
        q = m.group(2)
        return await _sell(update, me, m.group(1), None if q in ("все", "всё") else int(q or 1))
    return False


# ---------------- бизнес ----------------
async def _biz_info(update, me):
    touch(me)
    b = biz_of(me.id)
    if not b:
        lines = ["🏪 <b>Бизнес</b>: копит прибыль, пока тебя нет (до 24 ч), потом «собрать доход».\n"]
        for i, (n, price, inc) in enumerate(BIZ, 1):
            lines.append(f"{i}. {n}: {price} {COIN}, {inc} {COIN}/час")
        lines.append("\nОткрыть: «купить бизнес» (начнёшь с ларька). Потом «улучшить бизнес»")
        await reply(update, "\n".join(lines))
        return True
    name, price, inc = BIZ[b["level"] - 1]
    acc, hours = biz_accrued(b)
    lines = [f"🏪 <b>{name}</b> · уровень {b['level']} из {len(BIZ)}",
             f"Доход: {inc} {COIN}/час · накоплено {acc} {COIN} ({hours:.1f} ч из {BIZ_CAP_H})"]
    if b["level"] < len(BIZ):
        lines.append(f"Улучшить до «{BIZ[b['level']][0]}»: {biz_upgrade_cost(b['level'])} {COIN} («улучшить бизнес»)")
    lines.append("Забрать: «собрать доход». Могут быть проверки, поломки и удачные дни. Продать: «продать бизнес» (50% цены)")
    await reply(update, "\n".join(lines))
    return True


async def _biz_buy(update, me):
    touch(me)
    if biz_of(me.id):
        await reply(update, "У тебя уже есть бизнес: «бизнес», «улучшить бизнес»")
        return True
    price = BIZ[0][1]
    if coins_of(me.id) < price:
        await reply(update, f"Ларёк стоит {price} {COIN}, у тебя {coins_of(me.id)}")
        return True
    give_coins(me.id, -price, commit=False)
    db.execute("INSERT INTO business(user_id,level,last_collect,bought) VALUES(?,?,?,?)", (me.id, 1, time.time(), time.time()))
    db.commit()
    await reply(update, f"🏪 {link(me.id, disp(me))} открыл(а) <b>{BIZ[0][0]}</b>! Доход {BIZ[0][2]} {COIN}/час. "
                        f"Забирай: «собрать доход»")
    return True


async def _biz_up(update, me):
    b = biz_of(me.id)
    if not b:
        await reply(update, "Сначала открой бизнес: «купить бизнес»")
        return True
    if b["level"] >= len(BIZ):
        await reply(update, "У тебя максимальный уровень — завод 🏭")
        return True
    cost = biz_upgrade_cost(b["level"])
    if coins_of(me.id) < cost:
        await reply(update, f"Улучшение стоит {cost} {COIN}, у тебя {coins_of(me.id)}")
        return True
    acc, _ = biz_accrued(b)
    give_coins(me.id, acc - cost, commit=False)           # накопленное не теряется
    db.execute("UPDATE business SET level=level+1, last_collect=? WHERE user_id=?", (time.time(), me.id))
    db.commit()
    nxt = BIZ[b["level"]]
    await reply(update, f"⬆️ Бизнес улучшен до «{nxt[0]}»! Доход {nxt[2]} {COIN}/час"
                        + (f" (накопленные {acc} {COIN} получены)" if acc else ""))
    return True


async def _biz_collect(update, me):
    b = biz_of(me.id)
    if not b:
        await reply(update, "У тебя нет бизнеса: «купить бизнес»")
        return True
    acc, hours = biz_accrued(b)
    if acc < 1:
        await reply(update, "Пока нечего собирать, загляни позже ⏳")
        return True
    income, ev = biz_roll_event(acc)
    if has_boost(urow(me.id)):
        income = int(income * (1 + BOOST_PCT / 100))
        ev += ("\n" if ev else "") + f"💊 Бонус после лечения: +{BOOST_PCT}%"
    give_coins(me.id, income, commit=False)
    db.execute("UPDATE business SET last_collect=? WHERE user_id=?", (time.time(), me.id))
    db.commit()
    from services.xp import quest_hit
    await quest_hit(update.get_bot(), me.id, "biz", update.effective_chat.id)
    await reply(update, f"💰 {link(me.id, disp(me))} собрал(а) доход «{BIZ[b['level'] - 1][0]}»: <b>+{income}</b> {COIN}"
                        + (f"\n{ev}" if ev else "") + f"\nБаланс: {coins_of(me.id)} {COIN}")
    return True


async def _biz_sell(update, me):
    b = biz_of(me.id)
    if not b:
        await reply(update, "У тебя нет бизнеса")
        return True
    back = BIZ[b["level"] - 1][1] // 2
    acc, _ = biz_accrued(b)
    give_coins(me.id, back + acc, commit=False)
    db.execute("DELETE FROM business WHERE user_id=?", (me.id,))
    db.commit()
    await reply(update, f"Бизнес продан: +{back + acc} {COIN} (половина цены и накопленный доход)")
    return True


# ---------------- биржа ----------------
def _rows():
    return [(s["sym"], s["name"], s["price"], s["prev"], history(s["sym"])) for s in
            db.execute("SELECT * FROM stocks ORDER BY rowid").fetchall()]


UPLOAD_T = dict(read_timeout=25, write_timeout=25, connect_timeout=10, pool_timeout=10)
FAST_T = dict(read_timeout=10, write_timeout=10, connect_timeout=8, pool_timeout=8)


async def _send_photo(target, data, caption, reply_markup=None, key=None, **kw):
    """target: сообщение (reply_photo) или (bot, chat_id).
    key: постоянная картинка (карточка роли и т. п.): после первой загрузки шлём её по file_id, без загрузки файла.
    data: BytesIO или функция, которая его создаёт. Одна попытка загрузки, при провале сразу текст."""
    from database.state import state_get, state_set

    async def go(photo, t):
        if isinstance(target, tuple):
            return await target[0].send_photo(target[1], photo, caption=caption, parse_mode=HTML,
                                              reply_markup=reply_markup, **t, **kw)
        return await target.reply_photo(photo, caption=caption, parse_mode=HTML, reply_markup=reply_markup, **t, **kw)

    fid = state_get("fid_" + key) if key else None
    if fid:
        try:
            return await go(fid, FAST_T)
        except Exception as ex:
            log.warning("фото по file_id (%s): %r", key, ex)
            if isinstance(ex, (TimedOut, NetworkError)) and not isinstance(ex, BadRequest):
                fid = "timeout"
            else:
                state_set("fid_" + key, "")
    if fid != "timeout":
        for attempt in (1, 2):
            try:
                photo = data() if callable(data) else data
                if not callable(data) and hasattr(photo, "seek"):
                    photo.seek(0)
                m = await go(photo, UPLOAD_T)
                if key and getattr(m, "photo", None):
                    state_set("fid_" + key, m.photo[-1].file_id)
                return m
            except Exception as ex:
                log.warning("send_photo (%s) попытка %d: %r", key or "без ключа", attempt, ex)
                # серверная ошибка Telegram/прокси (500, 502) обычно разовая: одна быстрая повторная попытка; таймаут не повторяем
                if attempt == 1 and isinstance(ex, NetworkError) and not isinstance(ex, TimedOut):
                    await asyncio.sleep(1.5)
                    continue
                break
    if isinstance(target, tuple):
        return await target[0].send_message(target[1], caption, parse_mode=HTML, reply_markup=reply_markup)
    return await target.reply_text(caption, parse_mode=HTML, reply_markup=reply_markup)


def _caption():
    init_stocks()
    lines = ["📈 <b>Биржа</b>"]
    for s in db.execute("SELECT * FROM stocks ORDER BY rowid").fetchall():
        ch = (s["price"] - s["prev"]) / s["prev"] * 100 if s["prev"] else 0
        lines.append(f"{'🟢' if ch >= 0 else '🔴'} <b>{s['sym']}</b> {esc(s['name'])}: {s['price']:.2f} ({ch:+.1f}%)")
    lines.append(f"\n«купить акции SVD 5» · «продать акции SVD все» · «портфель»\n"
                 f"Цены меняются раз в 45 мин (следующее обновление через ~{_next_update()} мин). Лимит вложений {STOCK_DAY_LIMIT} {COIN}/сутки, "
                 f"до {STOCK_MAX_QTY} акций одной компании, комиссия {int(STOCK_FEE * 100)}% при продаже")
    return "\n".join(lines)


def _list_kb():
    syms = [s["sym"] for s in db.execute("SELECT sym FROM stocks ORDER BY rowid").fetchall()]
    rows = [[InlineKeyboardButton(x, callback_data=f"stk:o:{x}") for x in syms[i:i + 4]] for i in range(0, len(syms), 4)]
    rows.append([InlineKeyboardButton("📡 Табло LIVE", callback_data="lv:new:all")])
    rows.append([InlineKeyboardButton("💼 Портфель", callback_data="stk:p"),
                 InlineKeyboardButton("🏆 Топ инвесторов", callback_data="stk:t")])
    return InlineKeyboardMarkup(rows)


def _card(uid, s):
    h = holding(uid, s["sym"])
    ch = (s["price"] - s["prev"]) / s["prev"] * 100 if s["prev"] else 0
    hist = history(s["sym"])
    lines = [f"{'🟢' if ch >= 0 else '🔴'} <b>{s['sym']}</b> · {esc(s['name'])}",
             f"Цена: <b>{s['price']:.2f}</b> {COIN} ({ch:+.1f}%) · за сутки: {min(hist):.2f}…{max(hist):.2f}",
             f"У тебя: {h['qty'] if h else 0} шт. · баланс {coins_of(uid)} {COIN}",
             f"Лимит вложений сегодня: {spent_today(uid)}/{STOCK_DAY_LIMIT} · комиссия продажи {int(STOCK_FEE * 100)}%"]
    if h:
        lines.append(f"Вложено {h['cost']}, сейчас {int(s['price'] * h['qty'])}")
    return "\n".join(lines)


def _card_kb(sym):
    B = InlineKeyboardButton
    return InlineKeyboardMarkup([
        [B(f"📥 Купить {n}", callback_data=f"stk:b:{sym}:{n}") for n in (1, 5, 10)],
        [B("📤 Продать 1", callback_data=f"stk:s:{sym}:1"), B("📤 Продать 5", callback_data=f"stk:s:{sym}:5"),
         B("📤 Всё", callback_data=f"stk:s:{sym}:0")],
        [B("🔄 Обновить", callback_data=f"stk:o:{sym}"), B("◀ Все акции", callback_data="stk:m")]])


def _next_update():
    last = float(state_get("stk_tick") or 0)
    left = max(0, int(last + STOCK_TICK_SEC - time.time()) // 60)
    return left


async def _market(update, context):
    touch(update.effective_user)
    init_stocks()
    data = await asyncio.to_thread(lambda: overview(_rows()))
    await _send_photo(update.effective_message, data, _caption(), reply_markup=_list_kb())
    return True


async def on_stock_btn(update, context):
    q = update.callback_query
    if not q.message or q.message.chat_id not in ALLOWED:
        return await q.answer()
    me = q.from_user
    touch(me)
    init_stocks()
    p = (q.data or "").split(":")
    act = p[1] if len(p) > 1 else ""

    async def show(text, kb):
        try:
            if q.message.photo:          # сообщение с картинкой: меняем подпись, а не шлём новое
                await q.edit_message_caption(caption=text[:1000], parse_mode=HTML, reply_markup=kb)
            else:
                await q.edit_message_text(text, parse_mode=HTML, reply_markup=kb)
        except BadRequest:
            pass            # «message is not modified»
        except RetryAfter:
            pass            # слишком частые нажатия: карточка обновится при следующем

    if act == "m":
        await q.answer()
        return await show(_caption(), _list_kb())
    if act == "p":
        await q.answer()
        rows = db.execute("SELECT h.*, s.price, s.name FROM holdings h JOIN stocks s ON s.sym=h.sym WHERE h.user_id=?",
                          (me.id,)).fetchall()
        if not rows:
            return await q.answer("Портфель пуст", show_alert=True)
        total = sum(int(r["price"] * r["qty"]) for r in rows)
        txt = "💼 <b>Портфель</b> · " + esc(disp(me)) + "\n" + "\n".join(
            f"{r['sym']}: {r['qty']} шт. · {int(r['price'] * r['qty'])} {COIN}" for r in rows) + f"\nВсего: {total} {COIN}"
        return await show(txt, _list_kb())
    if act == "t":
        rows = db.execute("SELECT i.profit, u.name FROM investors i JOIN users u ON u.user_id=i.user_id "
                          "ORDER BY i.profit DESC LIMIT 5").fetchall()
        if not rows:
            return await q.answer("Пока нет закрытых сделок", show_alert=True)
        await q.answer()
        return await show("🏆 <b>Топ инвесторов</b>\n" + "\n".join(
            f"{i}. {esc(r['name'] or '?')}: {r['profit']:+d}" for i, r in enumerate(rows, 1)), _list_kb())
    s = find_stock(p[2]) if len(p) > 2 else None
    if not s:
        return await q.answer("Компания не найдена", show_alert=True)
    if act == "o":
        await q.answer()
        return await show(_card(me.id, s), _card_kb(s["sym"]))
    if act in ("b", "s") and len(p) == 4 and p[3].isdigit():
        n = int(p[3])
        if act == "b":
            ok, res = buy_stock(me.id, s, n)
            await q.answer((f"Куплено {n} шт. за {res} {COIN}" if ok else res) + __import__("re").sub("<[^>]+>", "", pop_event()), show_alert=not ok)
            if ok:
                from services.xp import quest_hit
                await quest_hit(context.bot, me.id, "stock", q.message.chat_id)
        else:
            h = holding(me.id, s["sym"])
            ok, res = sell_stock(me.id, s, n or (h["qty"] if h else 1))
            await q.answer((f"Продано {res[3]} шт.: +{res[0]} {COIN} (итог {res[1]:+d})" if ok else res) + __import__("re").sub("<[^>]+>", "", pop_event()), show_alert=not ok)
            if ok:
                from services.xp import quest_hit
                await quest_hit(context.bot, me.id, "stock", q.message.chat_id)
        return await show(_card(me.id, s), _card_kb(s["sym"]))
    await q.answer()


async def _buy(update, me, name, qty):
    touch(me)
    init_stocks()
    s = find_stock(name)
    if not s:
        await reply(update, "Нет такой компании. Список: «биржа»")
        return True
    ok, res = buy_stock(me.id, s, qty)
    if not ok:
        await reply(update, res)
        return True
    from services.xp import quest_hit
    await quest_hit(update.get_bot(), me.id, "stock", update.effective_chat.id)
    await reply(update, f"📥 {link(me.id, disp(me))} купил(а) {qty} шт. <b>{s['sym']}</b> по {s['price']:.2f} "
                        f"за {res} {COIN}. Сегодня вложено {spent_today(me.id)} из {STOCK_DAY_LIMIT}" + pop_event())
    return True


async def _sell(update, me, name, qty):
    touch(me)
    init_stocks()
    s = find_stock(name)
    if not s:
        await reply(update, "Нет такой компании. Список: «биржа»")
        return True
    h = holding(me.id, s["sym"]) if s else None
    if h and qty is None:
        qty = h["qty"]
    ok, res = sell_stock(me.id, s, qty or 1)
    if not ok:
        await reply(update, res)
        return True
    net, profit, fee, n = res
    from services.xp import quest_hit
    await quest_hit(update.get_bot(), me.id, "stock", update.effective_chat.id)
    await reply(update, f"📤 {link(me.id, disp(me))} продал(а) {n} шт. <b>{s['sym']}</b> по {s['price']:.2f}: "
                        f"+{net} {COIN} (комиссия {fee}). Итог сделки: {'📈 +' if profit >= 0 else '📉 '}{profit} {COIN}" + pop_event())
    return True


async def _portfolio(update, me):
    touch(me)
    init_stocks()
    rows = db.execute("SELECT h.*, s.price, s.name FROM holdings h JOIN stocks s ON s.sym=h.sym WHERE h.user_id=?",
                      (me.id,)).fetchall()
    if not rows:
        await reply(update, "Портфель пуст. Купить: «купить акции SVD 5», список: «биржа»")
        return True
    total, lines = 0, ["💼 <b>Портфель</b>"]
    for r in rows:
        val = int(r["price"] * r["qty"])
        total += val
        diff = val - r["cost"]
        lines.append(f"{r['sym']} {esc(r['name'])}: {r['qty']} шт. · {val} {COIN} ({'+' if diff >= 0 else ''}{diff})")
    lines.append(f"Всего: {total} {COIN}. Баланс: {coins_of(me.id)} {COIN}")
    await reply(update, "\n".join(lines))
    return True


async def _top(update):
    rows = db.execute("SELECT i.profit, u.user_id, u.name FROM investors i JOIN users u ON u.user_id=i.user_id "
                      "ORDER BY i.profit DESC LIMIT 10").fetchall()
    if not rows:
        await reply(update, "Пока нет закрытых сделок. Купи и продай акции: «биржа»")
        return True
    lines = ["🏆 <b>Топ инвесторов</b> (прибыль от продаж)"]
    for i, r in enumerate(rows, 1):
        lines.append(f"{i}. {link(r['user_id'], r['name'] or '?')} — {'+' if r['profit'] >= 0 else ''}{r['profit']} {COIN}")
    await reply(update, "\n".join(lines))
    return True


async def stocks_tick(bot):
    """Планировщик: раз в 45 минут двигает цены и присылает картинку при сильном скачке."""
    init_stocks()
    moves = tick_prices()
    if not moves or QUIET_HOURS[0] <= now().hour < QUIET_HOURS[1]:
        return
    s, old, new = max(moves, key=lambda m: abs(m[2] - m[1]) / m[1])
    if abs(new - old) / old < STOCK_ALERT:
        return
    try:
        data = await asyncio.to_thread(lambda: alert(s["sym"], s["name"], new, old, history(s["sym"])))
        up = new > old
        await _send_photo((bot, CHAT_ID), data,
                          f"{'🚀' if up else '📉'} <b>{s['sym']}</b> {esc(s['name'])}: "
                          f"{'взлетает' if up else 'падает'} {abs(new - old) / old * 100:.1f}% → {new:.2f}")
    except Exception:
        log.exception("stocks alert")
