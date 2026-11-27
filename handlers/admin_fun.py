# -*- coding: utf-8 -*-
"""Приколы владельца: золотой дождь, событие часа, случайный подарок, титул, тревога, мут-рулетка, «сказать», лотерея."""

import asyncio
import random
import time

from telegram import ChatPermissions

from config import ALLOWED, HTML
from core.helpers import reply, resolve_target
from core.logger import log
from core.utils import disp, esc, is_owner, link, urow
from database.db import db
from services.casino import chips_add, chips_of
from services.economy import COIN, give_coins
from services.events import KINDS, ev_set
from services.vip import STAR, stars_add

LOT = {}          # chat_id -> лотерея


def _active(minutes, limit=30):
    rows = db.execute("SELECT user_id, name FROM users WHERE last_seen>? ORDER BY RANDOM() LIMIT ?",
                      (time.time() - minutes * 60, limit)).fetchall()
    return rows


async def _rain(update, context, args):
    top = int(args[0]) if args and args[0].isdigit() else 5
    top = max(1, min(top, 50))
    rows = _active(60)
    if not rows:
        return await reply(update, "За последний час никто не писал")
    out = []
    for r in rows:
        n = random.randint(1, top)
        give_coins(r["user_id"], n)
        out.append(f"{link(r['user_id'], r['name'])} +{n}")
    await context.bot.send_message(update.effective_chat.id, f"🌧💰 <b>ЗОЛОТОЙ ДОЖДЬ!</b> Монеты упали на активных ({len(rows)}):\n"
                                   + "\n".join(out) + f"\n\n{COIN}, ловите!", parse_mode=HTML)


async def _event(update, context, args):
    kind = args[0] if args else ""
    if kind not in KINDS:
        return await reply(update, "Типы: <code>событие опыт</code>, <code>событие зарплата</code>, <code>событие скидка</code> "
                                   "(можно добавить минуты, по умолчанию 60)")
    mins = int(args[1]) if len(args) > 1 and args[1].isdigit() else 60
    mins = max(1, min(mins, 24 * 60))
    key, title = KINDS[kind]
    ev_set(key, mins)
    await context.bot.send_message(update.effective_chat.id, f"🎉 <b>СОБЫТИЕ!</b> {title} на {mins} мин. Успей воспользоваться!", parse_mode=HTML)


async def _gift(update, context):
    rows = _active(24 * 60, 1)
    if not rows:
        return await reply(update, "Нет активных людей за сутки")
    r = rows[0]
    uid = r["user_id"]
    kind = random.choice(("coins", "chips", "star", "vip"))
    if kind == "coins":
        n = random.randint(5, 15)
        give_coins(uid, n)
        what = f"{n} {COIN}"
    elif kind == "chips":
        chips_add(uid, 300)
        what = "300 💵 славБакс"
    elif kind == "star":
        stars_add(uid, 1)
        what = f"1 {STAR} звёздик"
    else:
        base = max(urow(uid)["vip_until"] or 0, time.time())
        db.execute("UPDATE users SET vip_until=? WHERE user_id=?", (base + 86400, uid))
        db.commit()
        what = "👑 VIP на сутки"
    await context.bot.send_message(update.effective_chat.id, f"🎁 Бот выбрал случайного счастливчика: {link(uid, r['name'])}!\nПодарок: <b>{what}</b>",
                                   parse_mode=HTML)


async def _title(update, context, args):
    uid, name, rest, err = resolve_target(update, args)
    if err or uid is None:
        return await reply(update, err or "Укажи человека. Пример: <code>титул @юз Король чата</code> (без текста: убрать)")
    t = " ".join(rest).strip()[:30]
    db.execute("UPDATE users SET ztitle=? WHERE user_id=?", (t, uid))
    db.commit()
    await reply(update, f"🏷 {esc(name)}: титул «{esc(t)}»" if t else f"🏷 {esc(name)}: титул убран")


ALARMS = (
    ("🚨 <b>ВНИМАНИЕ! НАЛЁТ ПОЛИЦИИ!</b> Всем оставаться на местах и не трогать монеты!", "Это была учебная тревога 😄 Можно расслабиться"),
    ("🦠 <b>В чате обнаружен новый вирус!</b> Заражённые чувствуют себя странно…", "Ложная тревога, все здоровы 😅"),
    ("🕵️ <b>В чате завёлся мафиози!</b> Кто-то из вас не тот, за кого себя выдаёт…", "Шучу. Пока что 😏 Хотите настоящую? «мафия»"),
    ("🔔 <b>ВНИМАНИЕ!</b> Через минуту я заберу по монете у каждого, кто молчал весь день!", "Пошутил 😂 Монеты на месте"),
)


async def _alarm(update, context):
    chat = update.effective_chat.id
    a, b = random.choice(ALARMS)
    await context.bot.send_message(chat, a, parse_mode=HTML)

    async def later():
        await asyncio.sleep(45)
        try:
            await context.bot.send_message(chat, b, parse_mode=HTML)
        except Exception:
            pass
    asyncio.create_task(later())


async def _mute(update, context):
    chat = update.effective_chat.id
    rows = [r for r in _active(30, 15) if not is_owner(type("U", (), {"id": r["user_id"]})())]
    if not rows:
        return await reply(update, "Некого мутить: никто не писал за последние 30 минут")
    r = rows[0]
    try:
        await context.bot.restrict_chat_member(chat, r["user_id"], ChatPermissions(can_send_messages=False), until_date=int(time.time()) + 65)
    except Exception as e:
        log.warning("mute roulette: %r", e)
        return await reply(update, "Не вышло: у бота нет права ограничивать участников или это админ чата")
    await context.bot.send_message(chat, f"🔫 Мут-рулетка выбрала {link(r['user_id'], r['name'])}. Тишина на 1 минуту 🤐", parse_mode=HTML)


async def _say(update, context, text):
    body = text.split(None, 1)[1] if len(text.split(None, 1)) > 1 else ""
    to_all = body.lower().startswith("всем ")
    if to_all:
        body = body[5:]
    if not body.strip():
        return await reply(update, "Пример: <code>сказать Привет всем!</code> или <code>сказать всем Текст</code> (во все чаты)")
    msg = f"📣 <b>Сообщение от бота</b>\n\n{esc(body.strip())}"
    try:
        await update.effective_message.delete()
    except Exception:
        pass
    if to_all:
        from scheduler import send_all
        await send_all(context.bot, msg)
    else:
        await context.bot.send_message(update.effective_chat.id, msg, parse_mode=HTML)


# ------------------------------ лотерея ------------------------------
async def _lot_start(update, context, args):
    chat = update.effective_chat.id
    if chat in LOT:
        return await reply(update, "Лотерея уже идёт. Закончить: «лотерея итог»")
    price = int(args[0]) if args and args[0].isdigit() else 50
    mins = int(args[1]) if len(args) > 1 and args[1].isdigit() else 10
    bonus = int(args[2]) if len(args) > 2 and args[2].isdigit() else 0
    price = max(10, min(price, 1000))
    mins = max(1, min(mins, 120))
    LOT[chat] = dict(price=price, tickets={}, bonus=bonus, ends=time.time() + mins * 60)
    await context.bot.send_message(chat, f"🎟 <b>ЛОТЕРЕЯ!</b> Билет {price} 💵 славБакс. Купить: «билет» (до 10 штук на человека).\n"
                                         f"Приз: все деньги с билетов{f' + бонус {bonus}' if bonus else ''}. Итоги через {mins} мин.",
                                   parse_mode=HTML)

    async def finish():
        await asyncio.sleep(mins * 60)
        if chat in LOT:
            await _lot_end(context.bot, chat)
    asyncio.create_task(finish())


async def _lot_end(bot, chat):
    lot = LOT.pop(chat, None)
    if not lot:
        return
    pool = [u for u, n in lot["tickets"].items() for _ in range(n)]
    if not pool:
        return await bot.send_message(chat, "🎟 Лотерея закончилась: никто не купил билет 😢")
    win = random.choice(pool)
    prize = len(pool) * lot["price"] + lot["bonus"]
    chips_add(win, prize)
    r = urow(win)
    await bot.send_message(chat, f"🎉 <b>Лотерея окончена!</b> Билетов продано: {len(pool)}\nПобедитель: {link(win, r['name'])}\n"
                                 f"Приз: <b>{prize}</b> 💵 славБакс", parse_mode=HTML)


async def _market(update, args, up):
    """обвал / поднять [тикер|все] [процент]"""
    from services.finance import admin_move, find_stock
    target, pct = None, 0.0
    for a in args:
        a = a.strip("%")
        if a.isdigit():
            pct = max(1, min(60, int(a))) / 100
        elif a not in ("все", "всё", "всех", "рынок"):
            target = a
    if target and not find_stock(target):
        return await reply(update, f"Не нашёл акцию «{esc(target)}». Тикеры: «биржа»")
    res = admin_move(target, pct, up)
    lines = [("🚀 <b>Рынок взлетает!</b>" if up else "💥 <b>Обвал на бирже!</b>")]
    for s, old, new in res:
        lines.append(f"{'📈' if up else '📉'} <b>{s['sym']}</b> {old:.2f} → {new:.2f} ({(new / old - 1) * 100:+.1f}%)")
    txt = "\n".join(lines)
    bot = update.get_bot()
    dest = update.effective_chat.id
    if update.effective_chat.type == "private":          # из лички: результат уходит в основной чат
        from config import CHAT_ID
        dest = CHAT_ID
        await reply(update, txt + "\n\n(отправлено в основной чат)")
    await _announce_gifs(bot, dest, res, up, txt, quiet=update.effective_chat.type == "private")


async def _announce_gifs(bot, chat, res, up, txt, quiet=False):
    """Гифка графика: акция взлетает или падает. Одна акция: гифка с подписью; несколько: текст и гифки трёх самых сильных."""
    import io
    from services.finance import history
    from services.stock_gif import make_gif
    movers = sorted(res, key=lambda r: abs(r[2] / r[1] - 1), reverse=True)[:3]
    sent = 0
    for i, (s, old, new) in enumerate(movers):
        try:
            hist = history(s["sym"])[:-1][-10:]
            pts = hist[:-1] + [old] if hist else [old]
            pts = [float(x) for x in pts]
            steps = 8
            pts += [old + (new - old) * (k / steps) ** 1.4 for k in range(1, steps + 1)]
            chg = (new / old - 1) * 100
            data = await asyncio.to_thread(make_gif, s["sym"], s["name"], pts, new, chg)
            if not data:
                continue
            bio = io.BytesIO(data)
            bio.name = "stock.gif"
            word = "🚀 взлетает" if up else "💥 обвал"
            cap = txt if len(movers) == 1 else f"{word}: <b>{s['sym']}</b> {old:.2f} → {new:.2f} ({chg:+.1f}%)"
            await bot.send_animation(chat, bio, caption=cap[:1000], parse_mode=HTML, read_timeout=25, write_timeout=25)
            sent += 1
        except Exception as e:
            log.warning("market gif: %r", e)
    if sent == 0 or len(res) > 1:                       # сводка текстом: для нескольких акций и если гифка не вышла
        try:
            await bot.send_message(chat, txt, parse_mode=HTML)
        except Exception as e:
            log.warning("market announce: %r", e)


async def _reset(update, args):
    """вернуть [тикер|все] — цены к исходным"""
    from services.finance import admin_reset, find_stock
    target = None
    for a in args:
        if a not in ("все", "всё", "всех", "рынок", "акции", "акцию"):
            target = a
    if target and not find_stock(target):
        return False
    res = [r for r in admin_reset(target) if abs(r[2] / r[1] - 1) > 0.001]
    if not res:
        await reply(update, "Цены и так на исходном уровне")
        return True
    lines = ["♻️ <b>Цены возвращены к исходным</b>"]
    for s, old, new in res:
        lines.append(f"{'📈' if new >= old else '📉'} <b>{s['sym']}</b> {old:.2f} → {new:.2f} ({(new / old - 1) * 100:+.1f}%)")
    txt = "\n".join(lines)
    bot = update.get_bot()
    dest = update.effective_chat.id
    if update.effective_chat.type == "private":
        from config import CHAT_ID
        dest = CHAT_ID
        await reply(update, txt + "\n\n(отправлено в основной чат)")
    movers = [r for r in res]
    up = sum(r[2] - r[1] for r in movers) >= 0
    await _announce_gifs(bot, dest, res, up, txt)
    return True


async def handle_market_private(update, context, low):
    """Команды биржи владельца в личке бота."""
    w = low.split()
    if not w or not is_owner(update.effective_user):
        return False
    up = w[0] in ("поднять", "взлёт", "взлет", "памп")
    if w[0] in ("обвал", "крах") or (up and len(w) <= 3):
        await _market(update, w[1:], up)
        return True
    if w[0] in ("вернуть", "сбросить") and len(w) <= 3:
        return bool(await _reset(update, w[1:]))
    return False


async def handle_adminfun_text(update, context, low, text):
    me = update.effective_user
    chat = update.effective_chat.id
    w = low.split()
    if not w:
        return False
    # билет может купить любой
    if w[0] in ("билет", "билеты") and chat in LOT:
        lot = LOT[chat]
        n = int(w[1]) if len(w) > 1 and w[1].isdigit() else 1
        have = lot["tickets"].get(me.id, 0)
        n = max(1, min(n, 10 - have))
        if have >= 10:
            return await reply(update, "У тебя уже 10 билетов, это максимум") or True
        cost = n * lot["price"]
        if chips_of(me.id) < cost:
            return await reply(update, f"Не хватает славБакс: нужно {cost}, у тебя {chips_of(me.id)}") or True
        chips_add(me.id, -cost, disp(me))
        lot["tickets"][me.id] = have + n
        total = sum(lot["tickets"].values())
        await reply(update, f"🎟 {link(me.id, disp(me))} купил(а) билетов: {n} (у тебя {have + n}). Всего в игре: {total}, "
                            f"банк {total * lot['price'] + lot['bonus']} 💵")
        return True
    if not is_owner(me):
        return False
    args = w[1:]
    if low.startswith("золотой дождь"):
        await _rain(update, context, w[2:])
    elif w[0] == "событие":
        await _event(update, context, args)
    elif low in ("случайный подарок", "рандом подарок"):
        await _gift(update, context)
    elif w[0] in ("обвал", "крах") or (w[0] in ("поднять", "взлёт", "взлет", "памп") and len(w) <= 3):
        await _market(update, args, w[0] in ("поднять", "взлёт", "взлет", "памп"))
    elif w[0] in ("вернуть", "сбросить") and len(w) <= 3 and await _reset(update, args):
        pass
    elif w[0] == "титул":
        await _title(update, context, text.split()[1:])
    elif low in ("тревога", "фейк тревога", "мафия тревога"):
        await _alarm(update, context)
    elif low in ("мут рулетка", "мут-рулетка"):
        await _mute(update, context)
    elif w[0] == "сказать":
        await _say(update, context, text)
    elif w[0] == "лотерея":
        if args and args[0] in ("итог", "конец", "стоп"):
            if chat in LOT:
                await _lot_end(context.bot, chat)
            else:
                await reply(update, "Лотереи нет")
        else:
            await _lot_start(update, context, args)
    else:
        return False
    return True
