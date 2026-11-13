# -*- coding: utf-8 -*-
"""Отношения: предложение, ответы, дети, обиды, кнопки и ежедневное содержание."""

import random
import re
import time
from types import SimpleNamespace

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import CHAT_ID, HTML
from core.helpers import reply, target_user
from core.logger import log
from core.utils import disp, esc, fmt_when, link, today, touch, urow
from database.db import db
from database.state import state_del, state_get, state_set
from handlers.dates_gifts import date_kb
from handlers.houses_pets import life_houses, life_pet_shop
from services.certificate import send_certificate
from services.economy import coins_of, give_coins
from services.jobs import HOUSES
from services.media import send_with_pic
from services.relations import ACCEPT, DATE_WORDS, DAUGHTERS, DECLINE, DIVORCE_COST, KIDS_MAX, KID_COST, LEAVE, LIST_WORDS, PROPOSE, REL_ASK_SEC, REL_START, REL_TXT_ACCEPT, REL_TXT_DECLINE, REL_TXT_PROPOSE, SONS, SPARK_RATE, STATUS_OTHER, STATUS_SELF, TOPPAIRS, delete_pair, ea, fmt_dur, kids_of, offended_block, pair_by_id, pair_of, partner_of, spark_add, spark_line, uname, upkeep


def pair_profile_text(row, uid):
    p = partner_of(row, uid)
    kids = kids_of(row["id"])
    sons = sum(1 for k in kids if k["gender"] == "м")
    me_r, p_r = urow(uid), urow(p)
    hs = [HOUSES[r["house"]][0] for r in (me_r, p_r) if r and r["house"] in HOUSES]
    pets = db.execute("SELECT * FROM pets WHERE owner IN (?,?)", (uid, p)).fetchall()
    lines = [f"❤️ Твоя половинка: {link(p, uname(p))}", f"🆔 ID отношений: {row['id']}"]
    if row["married_at"]:
        lines.append(f"💍 В браке с {fmt_when(row['married_at'])}")
    lines.append(spark_line(row))
    lines.append(f"🕙 Длительность: {fmt_dur(time.time() - row['since'])}")
    if hs:
        lines.append("🏠 Дом: " + ", ".join(hs[:1]))
    if pets:
        lines.append("🐾 Питомцы: " + ", ".join(esc(x["name"]) for x in pets))
    lines.append(f"👶 Сыновья: {sons}\n👩 Дочери: {len(kids) - sons}")
    lines.append(f"🎯 Действий: {row['actions'] or 0}")
    if row["offended"]:
        lines.append(f"🙁 {esc(uname(row['offended']))} обиделся(ась)")
    return "\n".join(lines)


def pair_kb(uid):
    B = InlineKeyboardButton
    return InlineKeyboardMarkup([
        [B("💰 Купить искры", callback_data=f"rel:menu:buy:{uid}"), B("🏠 Дом", callback_data=f"rel:menu:house:{uid}")],
        [B("🐾 Питомцы", callback_data=f"rel:menu:pets:{uid}"), B("👶 Дети", callback_data=f"rel:menu:kids:{uid}")],
        [B("📊 История", callback_data=f"rel:menu:hist:{uid}")]])


async def rel_answer(bot, chat_id, me_id, accept, reply_to=None, token=None):
    """Ответ на предложение отношений (слова или кнопки). True, если предложение было."""
    pr = db.execute("SELECT * FROM proposals WHERE to_id=?", (me_id,)).fetchone()
    if not pr:
        return False
    if token is not None and int(pr["created"]) != token:
        return False                            # кнопка от старого предложения
    db.execute("DELETE FROM proposals WHERE to_id=?", (me_id,))
    db.commit()
    a = pr["from_id"]

    async def out(text, pic=None):
        await send_with_pic(bot, chat_id, text, ["отн:" + pic] if pic else [], reply_to=reply_to)

    if time.time() - pr["created"] > REL_ASK_SEC:
        await out("⌛ Время на ответ вышло (2 минуты), предложение отменено.")
        return True
    if not accept:
        await out(random.choice(REL_TXT_DECLINE).format(a=link(a, uname(a)), b=link(me_id, uname(me_id)),
                                                         ea=ea(me_id)))
    elif pair_of(a) or pair_of(me_id):
        await out("Кто-то из вас уже в отношениях.")
    else:
        cur = db.execute("INSERT INTO pairs(a,b,love,since,last_action) VALUES(?,?,?,?,?)",
                         (a, me_id, REL_START, time.time(), time.time()))
        db.execute("INSERT INTO spark_log(pair_id,delta,reason,who,ts,bal) VALUES(?,?,?,?,?,?)",
                   (cur.lastrowid, REL_START, "начало отношений", "", time.time(), REL_START))
        db.commit()
        txt = (random.choice(REL_TXT_ACCEPT).format(a=link(a, uname(a)), b=link(me_id, uname(me_id))) +
               f"\n🔥 Искры: {REL_START} (общий баланс пары, они тратятся раз в сутки)\n"
               f"Пополняйте искры: «поцеловать», «обнять», «свидание», задания на работе. "
               f"Профиль: «моя пара»")
        if not await send_certificate(bot, chat_id, pair_of(me_id), False, reply_to, caption=txt):
            await out(txt, "пара")
    return True


async def rel_leave_ask(update, context):
    me = update.effective_user
    row = pair_of(me.id)
    if not row:
        return False
    p = partner_of(row, me.id)
    cost = f"\nРазвод в браке стоит {DIVORCE_COST} 🪙." if row["married_at"] else ""
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("💔 Расторгнуть", callback_data=f"rel:leave:{me.id}"),
                                InlineKeyboardButton("Отмена", callback_data=f"rel:cancel:{me.id}")]])
    await send_with_pic(context.bot, update.effective_chat.id,
                        f"💔 {link(me.id, disp(me))}, вы действительно хотите расторгнуть отношения с "
                        f"{link(p, uname(p))}? Это действие навсегда: искры и дети пропадут, монеты семейного счёта делятся поровну."
                        + cost, [], reply_to=update.effective_message.message_id, markup=kb)
    return True


async def rel_leave_do(bot, chat_id, uid, reply_to=None):
    row = pair_of(uid)
    if not row:
        return False
    p = partner_of(row, uid)
    married = bool(row["married_at"])
    if married:
        if coins_of(uid) < DIVORCE_COST:
            await send_with_pic(bot, chat_id, f"Развод стоит {DIVORCE_COST} 🪙, а у тебя {coins_of(uid)}.", [],
                                reply_to=reply_to)
            return True
        give_coins(uid, -DIVORCE_COST)
    delete_pair(row["id"])
    await send_with_pic(bot, chat_id,
                        f"💔 {link(p, uname(p))}, к сожалению, {link(uid, uname(uid))} решил{ea(uid)} "
                        f"расторгнуть ваши отношения" + (f" (−{DIVORCE_COST} 🪙)." if married else "."),
                        ["отн:развод" if married else "отн:расставание"], reply_to=reply_to,
                        api_cat="cry")
    return True


async def rel_offend(update, context):
    me = update.effective_user
    row = pair_of(me.id)
    if not row:
        return False
    p = partner_of(row, me.id)
    if row["offended"] == me.id:
        db.execute("UPDATE pairs SET offended=0 WHERE id=?", (row["id"],))
        db.commit()
        txt = f"😊 {link(p, uname(p))}, твоя половинка больше не обижается. Все действия снова доступны!"
    elif row["offended"]:
        txt = "🙁 Ваша половинка уже обижена на вас, сначала помиритесь."
    else:
        db.execute("UPDATE pairs SET offended=? WHERE id=?", (me.id, row["id"]))
        db.commit()
        txt = (f"🙁 {link(p, uname(p))}, твоя половинка обиделась. Все действия будут временно заблокированы, "
               f"пока она не передумает.\n💭 {link(me.id, disp(me))}, чтобы перестать обижаться, "
               f"введите эту команду ещё раз.")
    await send_with_pic(context.bot, update.effective_chat.id, txt, ["отн:обида"],
                        reply_to=update.effective_message.message_id)
    return True


async def rel_kid_ask(update, context):
    me = update.effective_user
    row = pair_of(me.id)
    if not row or not row["married_at"]:
        return await reply(update, "Дети бывают только в браке 💍. Сначала «предложить брак».")
    if len(kids_of(row["id"])) >= KIDS_MAX:
        return await reply(update, f"В семье уже {KIDS_MAX} детей, это максимум 👨‍👩‍👧‍👦")
    if row["love"] < KID_COST + 100:
        return await reply(update, f"Ребёнок стоит {KID_COST} искр, а в запасе должно остаться ещё 100. "
                                   f"Сейчас у пары {row['love']}. Пополните искры.")
    p = partner_of(row, me.id)
    state_set(f"kidreq:{p}", f"{me.id}:{time.time()}")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("👶 Да", callback_data=f"rel:kidyes:{p}"),
                                InlineKeyboardButton("Нет", callback_data=f"rel:kidno:{p}")]])
    await send_with_pic(context.bot, update.effective_chat.id,
                        f"👶 {link(me.id, disp(me))} мечтает о ребёнке! {link(p, uname(p))}, вы согласны? "
                        f"(2 минуты, стоит {KID_COST} искр)", [], reply_to=update.effective_message.message_id,
                        markup=kb)


async def rel_kid_born(bot, chat_id, uid, reply_to=None):
    row = pair_of(uid)
    req = state_get(f"kidreq:{uid}")
    state_del(f"kidreq:{uid}")
    if not row or not req or time.time() - float(req.split(":")[1]) > REL_ASK_SEC:
        return "Время вышло или запрос уже не актуален."
    if not row["married_at"] or len(kids_of(row["id"])) >= KIDS_MAX or row["love"] < KID_COST + 100:
        return "Сейчас это невозможно."
    g = random.choice(["м", "ж"])
    name = random.choice(SONS if g == "м" else DAUGHTERS)
    db.execute("INSERT INTO kids(pair_id,name,gender,born) VALUES(?,?,?,?)", (row["id"], name, g, time.time()))
    db.commit()
    spark_add(row["id"], -KID_COST, "рождение ребёнка", uname(uid))
    a, b = row["a"], row["b"]
    await send_with_pic(bot, chat_id,
                        f"👶🎉 В семье пополнение! У {link(a, uname(a))} и {link(b, uname(b))} "
                        f"родил{'ся сын' if g == 'м' else 'ась дочь'}: <b>{esc(name)}</b>\n"
                        f"Переименовать: «назвать ребёнка Имя». Расход искр вырос на 10%.",
                        ["отн:ребёнок"], reply_to=reply_to, api_cat="happy")
    return None


async def rel_kids_list(update, context):
    row = pair_of(update.effective_user.id)
    kids = kids_of(row["id"]) if row else []
    if not kids:
        return await reply(update, "Детей пока нет. В браке: «завести ребёнка» 👶")
    lines = ["👨‍👩‍👧‍👦 <b>Дети</b>"]
    for k in kids:
        lines.append(f"{'👦' if k['gender'] == 'м' else '👧'} {esc(k['name'])}, {fmt_dur(time.time() - k['born'])}")
    await reply(update, "\n".join(lines))


async def rel_kid_rename(update, context, new):
    row = pair_of(update.effective_user.id)
    kids = kids_of(row["id"]) if row else []
    new = new.strip()[:20]
    if not kids:
        return await reply(update, "У вас нет детей.")
    if not new:
        return await reply(update, "Напиши имя: «назвать ребёнка Артём»")
    db.execute("UPDATE kids SET name=? WHERE id=?", (new, kids[-1]["id"]))
    db.commit()
    await reply(update, f"✏️ Теперь младшего зовут <b>{esc(new)}</b>")


def hist_text(pid):
    rows = db.execute("SELECT * FROM spark_log WHERE pair_id=? ORDER BY id DESC LIMIT 10", (pid,)).fetchall()
    row = pair_by_id(pid)
    if not rows:
        return "История пока пуста."
    lines = [f"📊 <b>История искр</b>\n🔥 Текущий баланс: {row['love']}\n"]
    for r in rows:
        mark = "📈" if r["delta"] >= 0 else "📉"
        who = f" • {esc(r['who'])}" if r["who"] else ""
        lines.append(f"{mark} {r['delta']:+d} | {esc(r['reason'])}{who}\n   {fmt_when(r['ts'])} | баланс {r['bal']}")
    return "\n".join(lines)


def top_text(cat):
    if cat == "act":
        rows = db.execute("SELECT * FROM pairs ORDER BY actions DESC LIMIT 10").fetchall()
        val = lambda r: f"{r['actions'] or 0} действий"
        title = "🔄 Общая активность"
    elif cat == "sp":
        rows = db.execute("SELECT * FROM pairs ORDER BY love DESC LIMIT 10").fetchall()
        val = lambda r: f"{r['love']} 🔥"
        title = "🔥 Искры"
    else:
        rows = db.execute("SELECT * FROM pairs ORDER BY since ASC LIMIT 10").fetchall()
        val = lambda r: fmt_dur(time.time() - r["since"])
        title = "⏳ Длительность"
    if not rows:
        return "Пока нет ни одной пары 💔"
    return f"🏆 <b>Топ по «{title}»</b>\n\n" + "\n".join(
        f"{i}. {esc(uname(r['a']))} + {esc(uname(r['b']))} — {val(r)}" for i, r in enumerate(rows, 1))


def top_kb(uid):
    B = InlineKeyboardButton
    return InlineKeyboardMarkup([[B("🔄 Общая активность", callback_data=f"rel:top:act:{uid}")],
                                 [B("🔥 Искры", callback_data=f"rel:top:sp:{uid}")],
                                 [B("⏳ Длительность", callback_data=f"rel:top:dur:{uid}")]])


async def handle_relation(update, context, low):
    clean = re.sub(r"[!.?,]+$", "", low).strip()
    if not (clean in PROPOSE or clean in ACCEPT or clean in DECLINE or clean in LEAVE
            or clean in STATUS_SELF or clean in STATUS_OTHER or clean in DATE_WORDS
            or clean in TOPPAIRS or clean in LIST_WORDS):
        return False
    msg, me, chat = update.effective_message, update.effective_user, update.effective_chat
    bot = context.bot

    async def say(text, pic=None, markup=None):
        await send_with_pic(bot, chat.id, text, ["отн:" + pic] if pic else [], reply_to=msg.message_id,
                            markup=markup)

    if clean in PROPOSE:
        other = target_user(update)
        if not other or other.id == me.id:
            await say("Ответь этими словами на сообщение человека: «предложить отношения» 💌")
        elif pair_of(me.id):
            await say("Ты уже в отношениях. Сначала «расстаться».")
        elif pair_of(other.id):
            await say(f"У {esc(disp(other))} уже есть пара.")
        else:
            touch(other)
            ts = int(time.time())
            db.execute("INSERT OR REPLACE INTO proposals(to_id,from_id,created,msg_id) VALUES(?,?,?,?)",
                       (other.id, me.id, ts, msg.message_id))
            db.commit()
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("💖 Да", callback_data=f"rel:yes:{ts}:{other.id}"),
                                        InlineKeyboardButton("💔 Нет", callback_data=f"rel:no:{ts}:{other.id}")]])
            await say(random.choice(REL_TXT_PROPOSE).format(a=link(me.id, disp(me)),
                                                            b=link(other.id, disp(other))),
                      "предложение", kb)
        return True

    if clean in ACCEPT or clean in DECLINE:
        return await rel_answer(bot, chat.id, me.id, clean in ACCEPT, msg.message_id)

    if clean in LEAVE:
        return await rel_leave_ask(update, context)

    if clean in STATUS_SELF or clean in STATUS_OTHER:
        u = target_user(update) if clean in STATUS_OTHER else None
        if clean in STATUS_OTHER and not u:
            return False
        u = u or me
        row = pair_of(u.id)
        if not row:
            await say("У тебя нет пары. Ответь на сообщение человека: «предложить отношения»."
                      if u.id == me.id else f"У {esc(disp(u))} нет пары.")
        else:
            await say(pair_profile_text(row, u.id), None, pair_kb(u.id) if u.id == me.id else None)
        return True

    if clean in DATE_WORDS:
        row = pair_of(me.id)
        if not row:
            return False
        p = partner_of(row, me.id)
        if offended_block(me.id, p):
            await say("🙁 Ваша половинка обижена на вас, все действия недоступны.")
        elif row["date_day"] == today():
            await say("Сегодня вы уже ходили на свидание 🌹")
        else:
            await say("🌹 Куда пойдёте на свидание? Платит тот, кто выбирает место.", None, date_kb(me.id))
        return True

    if clean in LIST_WORDS:
        rows = db.execute("SELECT * FROM pairs ORDER BY since LIMIT 30").fetchall()
        if not rows:
            await say("Пока нет ни одной пары 💔")
        else:
            await say("💞 <b>Пары чата</b>\n" + "\n".join(
                f"{i}. {'💍' if r['married_at'] else '❤️'} {esc(uname(r['a']))} + {esc(uname(r['b']))} "
                f"({fmt_dur(time.time() - r['since'])})" for i, r in enumerate(rows, 1)))
        return True

    await say("📊 Выберите категорию для топа отношений:", None, top_kb(me.id))
    return True


async def on_rel_btn(update, context):
    q = update.callback_query
    p = (q.data or "").split(":")
    if len(p) < 3 or p[0] != "rel":
        return await q.answer()
    kind = p[1]
    uid = int(p[-1]) if p[-1].isdigit() else 0
    if q.from_user.id != uid:
        return await q.answer("Это кнопка для другого человека 🙂", show_alert=True)
    chat = q.message.chat.id
    mid = q.message.message_id
    bot = context.bot
    shim = SimpleNamespace(effective_user=q.from_user, effective_chat=q.message.chat,
                                 effective_message=q.message)

    async def drop_markup():
        try:
            await q.edit_message_reply_markup(None)
        except Exception:
            pass

    if kind in ("yes", "no"):
        touch(q.from_user)
        tok = int(p[2]) if len(p) == 4 and p[2].isdigit() else -1
        ok = await rel_answer(bot, chat, uid, kind == "yes", mid, tok)
        await q.answer("Готово" if ok else "Предложение уже неактуально")
        return await drop_markup()
    if kind == "leave":
        await q.answer()
        await drop_markup()
        return await rel_leave_do(bot, chat, uid, mid)
    if kind == "cancel":
        await q.answer("Отменено")
        return await drop_markup()
    if kind in ("kidyes", "kidno"):
        await drop_markup()
        if kind == "kidno":
            state_del(f"kidreq:{uid}")
            return await q.answer("Отказано")
        err = await rel_kid_born(bot, chat, uid, mid)
        return await q.answer(err or "Поздравляем!", show_alert=bool(err))
    if kind == "top":
        await q.answer()
        try:
            await q.edit_message_text(top_text(p[2]), parse_mode=HTML,
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
                                          "< Назад", callback_data=f"rel:topback:{uid}")]]))
        except Exception:
            pass
        return
    if kind == "topback":
        await q.answer()
        try:
            await q.edit_message_text("📊 Выберите категорию для топа отношений:", reply_markup=top_kb(uid))
        except Exception:
            pass
        return
    row = pair_of(uid)
    if not row:
        return await q.answer("У тебя нет пары", show_alert=True)
    if kind == "menu":
        what = p[2]
        await q.answer()
        if what == "buy":
            B = InlineKeyboardButton
            kb = InlineKeyboardMarkup([[B(f"{c} 🪙 → {c * SPARK_RATE} искр", callback_data=f"rel:buy2:{c}:{uid}")]
                                       for c in (50, 200, 500)])
            return await send_with_pic(bot, chat, f"💰 Купить искры. Курс: 1 🪙 = {SPARK_RATE} искр. "
                                                  f"У тебя {coins_of(uid)} 🪙", [], reply_to=mid, markup=kb)
        if what == "house":
            return await life_houses(shim, context)
        if what == "pets":
            return await life_pet_shop(shim, context)
        if what == "kids":
            return await rel_kids_list(shim, context)
        if what == "hist":
            return await send_with_pic(bot, chat, hist_text(row["id"]), [], reply_to=mid)
        return
    if kind == "buy2":
        c = int(p[2])
        if c not in (50, 200, 500):
            return await q.answer()
        if coins_of(uid) < c:
            return await q.answer(f"Не хватает монет: нужно {c}, у тебя {coins_of(uid)}", show_alert=True)
        give_coins(uid, -c)
        new = spark_add(row["id"], c * SPARK_RATE, "покупка искр", uname(uid))
        await q.answer("Готово")
        await drop_markup()
        return await send_with_pic(bot, chat, f"💰 {link(uid, uname(uid))} купил(а) {c * SPARK_RATE} искр "
                                              f"за {c} 🪙. Всего искр: {new}", [], reply_to=mid)
    await q.answer()


async def rel_daily(bot):
    """Раз в сутки: списываем содержание пар. Данные читаются заново и меняются без пауз между чтением и записью."""
    d = today()
    for pid in [r["id"] for r in db.execute("SELECT id FROM pairs").fetchall()]:
        try:
            row = pair_by_id(pid)
            if not row or (row["maint_day"] or "") == d:
                continue                                    # пары нет или сегодня уже обслужена
            up = upkeep(row)
            a, b = row["a"], row["b"]
            names = f"{link(a, uname(a))} и {link(b, uname(b))}"
            if row["love"] - up <= 0 and not row["married_at"]:
                dur = fmt_dur(time.time() - row["since"])
                delete_pair(pid)
                await send_with_pic(bot, CHAT_ID,
                                    f"💔 Отношения между {names}, длившиеся {dur}, были завершены: "
                                    f"искры закончились.", ["отн:расставание"])
                continue
            # одна короткая операция: относительное списание + отметка «обслужена»
            db.execute("UPDATE pairs SET love=CASE WHEN love-?<=0 THEN 10 ELSE love-? END, maint_day=? WHERE id=?",
                       (up, up, d, pid))
            fresh = pair_by_id(pid)
            db.execute("INSERT INTO spark_log(pair_id,delta,reason,who,ts,bal) VALUES(?,?,?,?,?,?)",
                       (pid, fresh["love"] - row["love"], "ежедневное содержание", "", time.time(), fresh["love"]))
            db.commit()
            new = fresh["love"]
            nxt = upkeep(fresh)
            if new < nxt and not fresh["married_at"]:
                await send_with_pic(
                    bot, CHAT_ID,
                    f"🚨 Отношения между {names} на грани распада! Осталось {new} искр, а для содержания "
                    f"нужно {nxt}. Срочно пополните искры («моя пара», кнопка «Купить искры» или "
                    f"«поцеловать», «свидание»), иначе отношения будут разрушены!", ["отн:скучаю"])
        except Exception:
            log.exception("rel_daily")
