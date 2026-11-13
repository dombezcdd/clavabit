# -*- coding: utf-8 -*-
"""Слова-команды жизни и кнопки; ежедневные события жизни."""

import re
import time
from datetime import datetime

from config import CHAT_ID, FMT, HTML, NOPREV
from core.helpers import reply, target_user
from core.logger import log
from core.utils import esc, link, today, urow
from database.db import db
from handlers.dates_gifts import handle_v21
from handlers.houses_pets import life_houses, life_pet_feed, life_pet_my, life_pet_rename, life_pet_shop
from handlers.marriage import life_family, life_marry_answer, life_marry_propose
from handlers.relations import rel_daily, rel_kid_ask, rel_kid_rename, rel_kids_list, rel_leave_ask, rel_offend
from handlers.work import finish_task, life_job_my, life_job_quit, life_jobs_find, life_work, task_check
from services.certificate import send_certificate
from services.economy import give_coins
from services.jobs import HOUSES, JOBS, JOB_GIF, PETS, PET_MAX, PET_RUNAWAY_DAYS, job_missing, load_custom_jobs, my_pets, open_task, shown_pay
from services.media import send_with_pic
from services.relations import KIDS_LIST_WORDS, KID_WORDS, OFFEND_WORDS, is_married, kids_of, pair_of, spark_add, uname


ANNIV_DAYS, ANNIV_SPARKS = 30, 100


JOB_WORDS_FIND = {"найти работу", "вакансии", "поиск работы"}


JOB_WORDS_WORK = {"работать", "выйти на смену", "пойти на работу"}


JOB_WORDS_QUIT = {"уволиться", "уволиться с работы"}


JOB_WORDS_MY = {"моя работа", "моя профессия"}


MARRY_PROPOSE = {"предложить брак", "предложить пожениться", "пожениться", "выйти за меня замуж",
                 "выходи за меня"}


MARRY_ACCEPT = {"принять брак", "согласна на брак", "согласен на брак", "да я согласна", "да я согласен"}


MARRY_DECLINE = {"отказать в браке", "отказаться от брака"}


DIVORCE = {"развод", "развестись"}


FAMILY = {"семья", "мой брак", "моя семья"}


HOUSE_WORDS = {"купить дом", "недвижимость", "купить жильё", "купить жилье", "магазин домов"}


PET_SHOP_WORDS = {"купить питомца", "питомцы магазин", "зоомагазин"}


PET_MY_WORDS = {"питомцы", "мои питомцы"}


PET_FEED_WORDS = {"покормить питомца", "покормить питомцев", "кормить питомца"}


# ---------- кнопки ----------
async def on_life_btn(update, context):
    q = update.callback_query
    p = (q.data or "").split(":")
    if len(p) != 4 or p[0] != "life" or not p[2].isdigit():
        return await q.answer()
    kind, uid, key = p[1], int(p[2]), p[3]
    if q.from_user.id != uid:
        return await q.answer("Это меню другого человека. Напиши команду сам 🙂", show_alert=True)
    if kind == "done":
        t = open_task(uid)
        if (not t or t["expires"] < time.time() or t["kind"] != "deliver"
                or str(int(t["created"])) != key):
            return await q.answer("Эта кнопка от другого задания, она уже недоступна", show_alert=True)
        await q.answer("Принято")
        try:
            await q.edit_message_reply_markup(None)
        except Exception:
            pass
        return await finish_task(context.bot, q.message.chat.id, uid, q.message.message_id)
    row = urow(uid)
    if not row:
        return await q.answer("Напиши что-нибудь в чат, чтобы бот тебя запомнил", show_alert=True)
    chat = q.message.chat.id
    text, api, pic, gif = None, None, None, None
    if kind == "job":
        if key not in JOBS:
            return await q.answer()
        miss = job_missing(row, JOBS[key][3])
        if miss:
            return await q.answer("Пока рано: нужно " + ", ".join(miss), show_alert=True)
        _t = open_task(uid)
        if _t and _t["expires"] > time.time():
            return await q.answer("Сначала закончи текущую смену", show_alert=True)
        db.execute("UPDATE users SET job=?, job_shifts=CASE WHEN job=? THEN job_shifts ELSE 0 END "
                   "WHERE user_id=?", (key, key, uid))
        db.commit()
        text = (f"✅ {link(uid, row['name'])} устроился: <b>{JOBS[key][0]}</b>\n"
                f"Зарплата {shown_pay(JOBS[key][1])} 🪙 за смену. Выходи на смену словом «работать»")
        pic, api, gif = "раб:" + key, "thumbsup", JOB_GIF.get(key)
    elif kind == "house":
        if key not in HOUSES:
            return await q.answer()
        name, price, bonus, url = HOUSES[key]
        old = row["house"] if row["house"] in HOUSES else None
        if old == key:
            return await q.answer("Этот дом у тебя уже есть", show_alert=True)
        refund = HOUSES[old][1] // 2 if old else 0
        if (row["coins"] or 0) + refund < price:
            return await q.answer(f"Не хватает монет: нужно {price - refund}, у тебя {row['coins'] or 0}",
                                  show_alert=True)
        give_coins(uid, refund - price, commit=False)
        db.execute("UPDATE users SET house=? WHERE user_id=?", (key, uid))
        db.commit()
        text = (f"🏠 {link(uid, row['name'])} купил(а): <b>{name}</b> за {price} 🪙"
                + (f" (старое жильё продано за {refund})" if refund else "")
                + f"\nБонус к зарплате: +{bonus}%")
        pic, api = "дом:" + key, "happy"
    elif kind == "pet":
        if key not in PETS:
            return await q.answer()
        if len([x for x in my_pets(uid)]) >= PET_MAX:
            return await q.answer(f"Больше {PET_MAX} питомцев держать нельзя", show_alert=True)
        name, price, em = PETS[key]
        if (row["coins"] or 0) < price:
            return await q.answer(f"Не хватает монет: нужно {price}, у тебя {row['coins'] or 0}", show_alert=True)
        give_coins(uid, -price, commit=False)
        db.execute("INSERT INTO pets(owner,kind,name,fed_day,bought) VALUES(?,?,?,?,?)",
                   (uid, key, name, today(), time.time()))
        db.commit()
        text = (f"{em} {link(uid, row['name'])} завёл(а) питомца: <b>{name}</b> за {price} 🪙\n"
                f"Дать имя: «назвать питомца Барсик», кормить: «покормить питомца»")
        pic, api = "пет:" + key, "pat"
    else:
        return await q.answer()
    await q.answer("Готово")
    try:
        await q.edit_message_reply_markup(None)
    except Exception:
        pass
    await send_with_pic(context.bot, chat, text, [pic], reply_to=q.message.message_id, api_cat=api,
                        gif_query=gif)


# ---------- маршрутизация слов ----------
async def handle_life(update, context, low, text):
    clean = re.sub(r"[!.?,]+$", "", low).strip()
    if await task_check(update, context, clean):
        return True
    if await handle_v21(update, context, clean):
        return True
    if clean in ("свидетельство", "сертификат", "свидетельство о браке"):
        who = target_user(update) or update.effective_user
        prow = pair_of(who.id)
        if not prow:
            await reply(update, "У этого человека нет пары." if who.id != update.effective_user.id
                        else "У тебя нет пары. Ответь «предложить встречаться» 💌")
        else:
            await send_certificate(context.bot, update.effective_chat.id, prow, is_married(prow),
                                   update.effective_message.message_id)
        return True
    if clean in JOB_WORDS_FIND:
        await life_jobs_find(update, context)
    elif clean in JOB_WORDS_WORK:
        await life_work(update, context)
    elif clean in JOB_WORDS_QUIT:
        await life_job_quit(update, context)
    elif clean in JOB_WORDS_MY:
        await life_job_my(update, context)
    elif clean in MARRY_PROPOSE:
        await life_marry_propose(update, context)
    elif clean in MARRY_ACCEPT or clean in MARRY_DECLINE:
        if not db.execute("SELECT 1 FROM marry_proposals WHERE to_id=?", (update.effective_user.id,)).fetchone():
            return False
        await life_marry_answer(update, context, clean in MARRY_ACCEPT)
    elif clean in DIVORCE:
        if not pair_of(update.effective_user.id):
            return False                  # обычное слово в разговоре
        await rel_leave_ask(update, context)
    elif clean in OFFEND_WORDS:
        if not await rel_offend(update, context):
            return False
    elif clean in KID_WORDS:
        await rel_kid_ask(update, context)
    elif clean in KIDS_LIST_WORDS:
        prow = pair_of(update.effective_user.id)
        if not prow or not kids_of(prow["id"]):
            return False
        await rel_kids_list(update, context)
    elif clean.startswith(("назвать ребёнка ", "назвать ребенка ")):
        await rel_kid_rename(update, context, text.strip().split(" ", 2)[2] if len(text.split()) > 2 else "")
    elif re.fullmatch(r"мой ?пол [мж]", clean):
        g = clean[-1]
        db.execute("UPDATE users SET gender=? WHERE user_id=?", (g, update.effective_user.id))
        db.commit()
        await reply(update, "✅ Пол сохранён: " + ("мужской" if g == "м" else "женский") +
                    ". Теперь в текстах будут правильные окончания.")
    elif clean in FAMILY:
        if not pair_of(update.effective_user.id) and not target_user(update):
            return False
        await life_family(update, context)
    elif clean in HOUSE_WORDS:
        await life_houses(update, context)
    elif clean in PET_SHOP_WORDS:
        await life_pet_shop(update, context)
    elif clean in PET_MY_WORDS:
        if not my_pets(update.effective_user.id):
            return False
        await life_pet_my(update, context)
    elif clean in PET_FEED_WORDS:
        await life_pet_feed(update, context)
    elif clean.startswith("назвать питомца "):
        await life_pet_rename(update, context, text.strip()[len("назвать питомца "):])
    else:
        return False
    return True


async def life_daily(bot):
    await rel_daily(bot)
    d = today()
    # годовщины
    for row in db.execute("SELECT * FROM pairs WHERE married_at>0").fetchall():
        days = int((time.time() - row["married_at"]) // 86400)
        if days and days % ANNIV_DAYS == 0 and row["anniv_day"] != d:
            db.execute("UPDATE pairs SET anniv_day=? WHERE id=?", (d, row["id"]))
            db.commit()
            spark_add(row["id"], ANNIV_SPARKS, "годовщина", "бот")
            try:
                await send_with_pic(bot, CHAT_ID,
                                    f"🎂 {link(row['a'], uname(row['a']))} и {link(row['b'], uname(row['b']))} "
                                    f"женаты уже {days} дн.! Подарок паре: +{ANNIV_SPARKS} 🔥",
                                    ["отн:годовщина"], api_cat="happy")
            except Exception:
                log.exception("anniv")
    # питомцы без еды уходят
    for p in db.execute("SELECT * FROM pets").fetchall():
        last = p["fed_day"] or ""
        try:
            gap = (datetime.strptime(d, FMT) - datetime.strptime(last, FMT)).days if last else 99
        except ValueError:
            gap = 99
        if gap >= PET_RUNAWAY_DAYS:
            db.execute("DELETE FROM pets WHERE id=?", (p["id"],))
            db.commit()
            try:
                await bot.send_message(CHAT_ID, f"😿 Питомец «{esc(p['name'])}» ({esc(uname(p['owner']))}) "
                                                f"ушёл: его давно не кормили", parse_mode=HTML,
                                       link_preview_options=NOPREV)
            except Exception:
                log.exception("pet run")


load_custom_jobs()
