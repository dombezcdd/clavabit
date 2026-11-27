# -*- coding: utf-8 -*-
"""Админ-панель владельца: «админка» и команды «выдать …», «вылечить», «освободить», «игрок»."""

import time

from telegram import InlineKeyboardButton as B, InlineKeyboardMarkup

from config import ALLOWED, HTML
from core.helpers import reply, resolve_target
from core.utils import esc, is_owner, link, today, urow
from database.db import db
from services.casino import chips_add, chips_of
from services.economy import COIN, coins_of, give_coins
from services.jobs import HOUSES, JOBS, PETS, my_pets
from services.virus import BOOST_PCT, cure, is_sick
from services.xp import give_xp

SECTIONS = {
    "money": ("💰 Деньги и очки",
              "• <code>выдать монеты @юз 500</code> (минус — забрать)\n"
              "• <code>выдать славБакс @юз 1000</code>\n"
              "• <code>выдать звёздики @юз 25</code>\n"
              "• <code>выдать вип @юз 30</code> (дней; -1 снять)\n"
              "• <code>выдать опыт @юз 300</code>\n"
              "• <code>выдать репутацию @юз 5</code>"),
    "health": ("💉 Здоровье",
               "• <code>выдать вакцину @юз 24</code> — вылечить и дать иммунитет на 24 ч (по умолчанию 24)\n"
               "• <code>вылечить @юз</code> — вылечить + бонус дохода\n"
               "• <code>выдать буст @юз 30</code> — +%d%% к доходу на 30 минут" % BOOST_PCT),
    "things": ("🏠 Дома, питомцы, работа",
               "• <code>выдать дом @юз " + "|".join(HOUSES) + "</code>\n• <code>забрать дом @юз</code>\n"
               "• <code>выдать питомца @юз " + "|".join(PETS) + "</code>\n• <code>забрать питомцев @юз</code>\n"
               "• <code>выдать работу @юз рыбак</code> (без требований)\n• <code>забрать работу @юз</code>"),
    "fun": ("🎪 Приколы",
            "• <code>обвал</code> / <code>поднять</code> [тикер или «все»] [процент] — биржа: обвал или взлёт цен (пример: <code>обвал SLC 30</code>)\n"
            "• <code>вернуть</code> [тикер или «все»] — вернуть цены акций к исходным\n"
            "• <code>золотой дождь 5</code> — монеты (1–5) всем, кто писал за час\n"
            "• <code>событие опыт|зарплата|скидка 60</code> — на N минут: ×2 опыт, +50% зарплаты, −20% в магазине\n"
            "• <code>случайный подарок</code> — бот дарит случайному активному (монеты, славБакс, звёздик, VIP на сутки)\n"
            "• <code>титул @юз Король чата</code> — титул в профиле (без текста: убрать)\n"
            "• <code>тревога</code> — шуточная «тревога» (налёт полиции, вирус…), через 45 с «отбой»\n"
            "• <code>мут рулетка</code> — случайный активный молчит 1 минуту (боту нужны права)\n"
            "• <code>сказать текст</code> / <code>сказать всем текст</code> — сообщение от бота\n"
            "• <code>лотерея 50 10 200</code> — цена билета, минуты, бонус к призу; «билет» покупают все; «лотерея итог» — закончить"),
    "law": ("⚖️ Порядок",
            "• <code>освободить @юз</code> — выпустить из тюрьмы\n"
            "• <code>сбросить паузы @юз</code> — смена, ограбление, заражение\n"
            "• <code>игрок @юз</code> — сводка по человеку\n"
            "• <code>рассылка текст</code> — сообщение во все чаты бота"),
}


def _kb():
    rows = [[B(v[0], callback_data=f"adm:{k}")] for k, v in SECTIONS.items()]
    rows.append([B("🛡 Команды модерации", callback_data="adm:mod")])
    return InlineKeyboardMarkup(rows)


def _panel():
    return ("🛠 <b>Админ-панель владельца</b>\n"
            "Команды работают в любом чате с ботом, в личке тоже. Цель: ответ на сообщение, @юз или числовой id.\n\n"
            "Выбери раздел:")


def _find(table, word):
    w = word.lower().replace("ё", "е")
    for k, v in table.items():
        if w == k.replace("ё", "е") or w == v[0].lower().replace("ё", "е"):
            return k
    return None


async def handle_admin_text(update, context, low, text):
    me = update.effective_user
    parts = low.split()
    first = parts[0] if parts else ""
    if first.lstrip("/") not in ("админка", "админ-панель", "выдать", "забрать", "вылечить", "освободить",
                                 "сбросить", "игрок", "рассылка") or not is_owner(me):
        return False
    if first.lstrip("/") in ("админка", "админ-панель"):
        await update.effective_message.reply_text(_panel(), parse_mode=HTML, reply_markup=_kb())
        return True
    if first.lstrip("/") == "рассылка":
        body = text.split(None, 1)[1].strip() if len(text.split(None, 1)) > 1 else ""
        if not body:
            await reply(update, "Напиши текст: <code>рассылка Текст сообщения</code> (уйдёт во все чаты бота)")
            return True
        from scheduler import send_all
        n = await send_all(context.bot, body)
        await reply(update, f"📣 Рассылка отправлена в чатов: {n} из {len(ALLOWED)}")
        return True
    args = text.split()[1:]
    uid, name, rest, err = resolve_target(update, args)
    if first == "выдать" or first == "забрать":
        what = rest[0].lower() if rest else ""
        rest2 = rest[1:]
        # цель могла стоять до «что»: «выдать @юз монеты 5»
        if uid is None and what:
            uid, name, rest3, err = resolve_target(update, rest)
            what, rest2 = (rest3[0].lower() if rest3 else ""), rest3[1:]
        return await _give(update, first, uid, name, what, rest2, err)
    if err or uid is None:
        await reply(update, err or "Укажи человека: ответом на сообщение, @юз или id")
        return True
    if not urow(uid):
        await reply(update, "Этого человека нет в базе бота (он ещё ничего не писал)")
        return True
    who = link(uid, name)
    if first == "вылечить":
        cure(uid)
        await reply(update, f"💉 {who} вылечен(а), иммунитет и бонус дохода выданы")
    elif first == "освободить":
        db.execute("UPDATE users SET jail_until=0 WHERE user_id=?", (uid,))
        db.commit()
        await reply(update, f"🔓 {who} выпущен(а) из тюрьмы")
    elif first == "сбросить":
        db.execute("UPDATE users SET last_work=0, rob_at=0, infect_at=0, gift_until=0 WHERE user_id=?", (uid,))
        db.execute("DELETE FROM job_tasks WHERE user_id=?", (uid,))
        db.commit()
        await reply(update, f"⏱ Паузы у {who} сброшены (смены, ограбление, заражение, подарки)")
    elif first == "игрок":
        await reply(update, _info(uid))
    return True


async def _give(update, verb, uid, name, what, rest, err):
    if err or uid is None or not what:
        await reply(update, err or "Формат: «выдать монеты @юз 500». Список: «админка»")
        return True
    r = urow(uid)
    if not r:
        await reply(update, "Этого человека нет в базе бота (он ещё ничего не писал)")
        return True
    who = link(uid, name)
    num = None
    if rest:
        try:
            num = int(rest[0])
        except ValueError:
            num = None
    if verb == "забрать":
        if what == "дом":
            db.execute("UPDATE users SET house='' WHERE user_id=?", (uid,))
            db.commit()
            msg = f"🏚 У {who} забран дом"
        elif what in ("питомцев", "питомца"):
            db.execute("DELETE FROM pets WHERE owner=?", (uid,))
            db.commit()
            msg = f"🐾 У {who} забраны питомцы"
        elif what == "работу":
            db.execute("UPDATE users SET job='' WHERE user_id=?", (uid,))
            db.execute("DELETE FROM job_tasks WHERE user_id=?", (uid,))
            db.commit()
            msg = f"📤 У {who} забрана работа"
        else:
            await reply(update, "Забрать можно: дом, питомцев, работу. Монеты: «выдать монеты @юз -100»")
            return True
        await reply(update, msg)
        return True
    if what in ("монеты", "монет", "славкоины", "славкоин", "коины"):
        if num is None:
            return await _need(update, "число")
        give_coins(uid, num)
        msg = f"💰 {who}: {num:+d} {COIN}. Баланс {coins_of(uid)}"
    elif what in ("фишки", "фишек"):
        if num is None:
            return await _need(update, "число")
        chips_add(uid, num, name)
        msg = f"💵 {who}: {num:+d} славБакс. Баланс {chips_of(uid)}"
    elif what in ("звёздики", "звездики", "звёзд", "звезд", "звёздиков", "звездиков"):
        if num is None:
            return await _need(update, "число")
        from services.vip import STAR, stars_add, stars_of
        stars_add(uid, num)
        msg = f"{STAR} {who}: {num:+d} звёздиков. Баланс {stars_of(uid)}"
    elif what in ("вип", "vip"):
        import time as _t
        from services.vip import vip_until
        days = num if num is not None else 30
        base = max(vip_until(uid), _t.time())
        db.execute("UPDATE users SET vip_until=? WHERE user_id=?", (max(0, base + days * 86400) if days >= 0 else 0, uid))
        db.commit()
        msg = f"👑 {who}: VIP {days:+d} дн."
    elif what in ("опыт", "xp", "хп"):
        if num is None:
            return await _need(update, "число")
        give_xp(uid, num)
        msg = f"⭐ {who}: {num:+d} опыта"
    elif what in ("репутацию", "репутация", "реп"):
        if num is None:
            return await _need(update, "число")
        db.execute("UPDATE users SET rep=rep+? WHERE user_id=?", (num, uid))
        db.commit()
        msg = f"✨ {who}: репутация {num:+d}"
    elif what in ("вакцину", "вакцина", "иммунитет"):
        hours = num if num and num > 0 else 24
        cure(uid)
        db.execute("UPDATE users SET immune_until=? WHERE user_id=?", (time.time() + hours * 3600, uid))
        db.commit()
        msg = f"💉 {who}: вакцина! Вылечен(а), иммунитет к вирусу на {hours} ч"
    elif what == "буст":
        mins = num if num and num > 0 else 10
        db.execute("UPDATE users SET boost_until=? WHERE user_id=?", (time.time() + mins * 60, uid))
        db.commit()
        msg = f"🚀 {who}: +{BOOST_PCT}% к доходу на {mins} мин"
    elif what == "дом":
        k = _find(HOUSES, rest[0]) if rest else None
        if not k:
            return await _need(update, "дом: " + ", ".join(HOUSES))
        db.execute("UPDATE users SET house=? WHERE user_id=?", (k, uid))
        db.commit()
        msg = f"🏠 {who} получает: <b>{HOUSES[k][0]}</b> (бонус к зарплате +{HOUSES[k][2]}%)"
    elif what in ("питомца", "питомец"):
        k = _find(PETS, rest[0]) if rest else None
        if not k:
            return await _need(update, "питомца: " + ", ".join(PETS))
        pname = " ".join(rest[1:])[:20] or PETS[k][0]
        db.execute("INSERT INTO pets(owner,kind,name,fed_day,bought) VALUES(?,?,?,?,?)",
                   (uid, k, pname, today(), time.time()))
        db.commit()
        msg = f"{PETS[k][2]} {who} получает питомца: <b>{esc(pname)}</b>"
    elif what == "работу":
        k = _find(JOBS, rest[0]) if rest else None
        if not k:
            return await _need(update, "работу: " + ", ".join(JOBS))
        db.execute("UPDATE users SET job=?, last_work=0 WHERE user_id=?", (k, uid))
        db.commit()
        msg = f"💼 {who} теперь: <b>{JOBS[k][0]}</b>"
    else:
        await reply(update, "Не понял, что выдавать. Список команд: «админка»")
        return True
    await reply(update, msg)
    return True


async def _need(update, what):
    await reply(update, f"Не хватает аргумента: {what}")
    return True


def _info(uid):
    r = urow(uid)
    pets = ", ".join(f"{PETS[p['kind']][2] if p['kind'] in PETS else ''}{esc(p['name'])}" for p in my_pets(uid)) or "нет"
    now = time.time()
    st = []
    if is_sick(r):
        st.append("🤒 болен")
    if (r["immune_until"] or 0) > now:
        st.append("🛡 иммунитет")
    if (r["jail_until"] or 0) > now:
        st.append("🔒 в тюрьме")
    return (f"🔎 <b>{link(uid, r['name'])}</b> · id <code>{uid}</code>\n"
            f"💰 {coins_of(uid)} {COIN} · 💵 {chips_of(uid)} славБакс · ⭐ {r['xp']} опыта · ✨ реп. {r['rep']}\n"
            f"💼 {JOBS[r['job']][0] if r['job'] in JOBS else 'без работы'} (смен {r['job_shifts'] or 0})\n"
            f"🏠 {HOUSES[r['house']][0] if r['house'] in HOUSES else 'нет'} · 🐾 {pets}\n"
            f"Состояние: {', '.join(st) or 'всё в порядке'}")


async def on_admin_btn(update, context):
    q = update.callback_query
    if not is_owner(q.from_user):
        return await q.answer("Только для владельца", show_alert=True)
    sec = (q.data or "").split(":", 1)[-1]
    if sec == "mod":
        from content.texts import ADMIN_HELP
        txt, kb = ADMIN_HELP[:3900], InlineKeyboardMarkup([[B("⬅️ Назад", callback_data="adm:back")]])
    elif sec in SECTIONS:
        title, body = SECTIONS[sec]
        txt = f"{title}\n\n{body}\n\nЦель: ответом на сообщение, @юз или id."
        kb = InlineKeyboardMarkup([[B("⬅️ Назад", callback_data="adm:back")]])
    else:
        txt, kb = _panel(), _kb()
    try:
        await q.edit_message_text(txt, parse_mode=HTML, reply_markup=kb)
    except Exception:
        pass
    await q.answer()
