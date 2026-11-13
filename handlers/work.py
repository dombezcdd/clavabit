# -*- coding: utf-8 -*-
"""Работа: поиск, смены, задания и увольнение."""

import random
import time

from telegram import InlineKeyboardButton

from core.durations import fmt_minutes
from core.helpers import reply
from core.utils import disp, esc, link, urow
from database.db import db
from handlers.common import life_send, own_kb
from services.economy import coins_of, give_coins
from services.jobs import CAREER, DELIVER, JOBS, JOB_GIF, MATH_FLAVOR, PLACES_DOC, PLACES_TAXI, TASK_MIN, WORDS, _math_task, career_next, career_title, house_bonus_pct, job_missing, job_pay, open_task, shown_pay, tag_user
from services.media import send_with_pic
from services.miniapp import mini_enabled, mini_link, mini_open
from services.relations import pair_of, spark_add


async def life_jobs_find(update, context):
    me = update.effective_user
    row = urow(me.id)
    lines = ["💼 <b>Биржа труда</b>"]
    if row["job"] in JOBS:
        lines.append(f"Сейчас ты работаешь: <b>{JOBS[row['job']][0]}</b>. «Работать» чтобы выйти на смену, "
                     f"«уволиться» чтобы сменить работу.\n")
    avail, locked = [], []
    for k, (name, pay, cd, req) in JOBS.items():
        miss = job_missing(row, req)
        (locked if miss else avail).append((k, name, pay, cd, miss))
    offers = random.sample(avail, min(3, len(avail)))
    lines.append("<b>Тебе предлагают:</b>")
    for k, name, pay, cd, _ in offers:
        lines.append(f"• {name}: {shown_pay(pay)} 🪙 за смену, раз в {cd} ч.")
    if locked:
        lines.append("\n<b>Пока недоступно:</b>")
        for k, name, pay, cd, miss in locked[:4]:
            lines.append(f"🔒 {name} ({shown_pay(pay)} 🪙): нужно {', '.join(miss)}")
    kb = own_kb([[InlineKeyboardButton(f"💼 {name} · {shown_pay(pay)}🪙", callback_data=f"life:job:{me.id}:{k}")]
                 for k, name, pay, cd, _ in offers])
    await life_send(update, context, "\n".join(lines), kb=kb)


async def life_work(update, context):
    me = update.effective_user
    row = urow(me.id)
    if row["job"] not in JOBS:
        return await reply(update, "У тебя нет работы. Напиши «найти работу» 💼")
    t = open_task(me.id)
    if t and t["expires"] > time.time():
        return await reply(update, "Ты уже на смене, сначала закончи задание выше ☝️ "
                                   f"(осталось {fmt_minutes((t['expires'] - time.time()) // 60 + 1)})")
    name, base, cd, req = JOBS[row["job"]]
    left = (row["last_work"] or 0) + cd * 3600 - time.time()
    if left > 0:
        return await reply(update, f"Смена ещё не началась. Отдыхай: через {fmt_minutes(left // 60 + 1)} ⏳")
    job = row["job"]
    n = random.randint(100, 999)
    kind, answer, target, extra = "word", "", 0, ""
    if job in DELIVER:
        others = db.execute("SELECT * FROM users WHERE user_id!=? AND last_seen>? ORDER BY RANDOM() LIMIT 1",
                            (me.id, time.time() - 3 * 86400)).fetchone()
        if others:
            kind, target = "deliver", others["user_id"]
            tpl, phrase = DELIVER[job]
            place = random.choice(PLACES_TAXI if job == "таксист" else PLACES_DOC)
            text = tpl.format(n=n, t=tag_user(others), place=place)
            answer = phrase
            hint = (f"\n\nНапиши: «{phrase}» (можно ответом на его сообщение) или нажми кнопку. "
                    f"Время: {TASK_MIN} мин.")
    if kind != "deliver":
        if job in MATH_FLAVOR:
            kind = "math"
            q, ans = _math_task(job)
            answer = str(ans)
            text = MATH_FLAVOR[job].format(q=q, n=n)
            hint = f"\n\nНапиши ответ числом. Время: {TASK_MIN} мин."
        else:
            kind, answer = "word", random.choice(WORDS)
            text = (f"🧹 <b>Уборка.</b> Наведите порядок: напишите слово «{answer}»" if job == "уборщик"
                    else f"🛠 <b>Рабочее задание.</b> Напишите слово «{answer}»")
            hint = f"\n\nВремя: {TASK_MIN} мин."
    created = time.time()
    db.execute("INSERT OR REPLACE INTO job_tasks(user_id,job,kind,answer,target_id,created,expires) "
               "VALUES(?,?,?,?,?,?,?)", (me.id, job, kind, answer, target, created,
                                        created + TASK_MIN * 60))
    db.execute("UPDATE users SET last_work=? WHERE user_id=?", (time.time(), me.id))
    db.commit()
    rows = []
    if kind == "deliver":
        rows.append([InlineKeyboardButton("✅ Выполнить", callback_data=f"life:done:{me.id}:{int(created)}")])
    if mini_enabled():
        sid = mini_open(me.id, update.effective_chat.id, update.effective_message.message_id, job, created)
        rows.append([InlineKeyboardButton("🎮 Сыграть в смену (мини-игра)",
                                          url=mini_link(context.bot.username, sid))])
        hint += "\n🎮 Или пройди мини-игру смены по кнопке: чем лучше результат, тем выше оплата."
    kb = own_kb(rows) if rows else None
    await life_send(update, context, f"{link(me.id, disp(me))}, новое задание!\n{text}{hint}", key="раб:" + job,
                    api="thumbsup", gif=JOB_GIF.get(job), kb=kb)


async def finish_task(bot, chat_id, uid, reply_to=None, mult=1.0, score=None):
    t = open_task(uid)
    row = urow(uid)
    if not t or not row:
        return
    cur = db.execute("DELETE FROM job_tasks WHERE user_id=?", (uid,))
    db.commit()
    if cur.rowcount == 0:
        return                                  # задание уже закрыто (двойное нажатие)
    if row["job"] not in JOBS or t["job"] != row["job"]:
        return                                  # профессию сменили: за прежнее задание не платим
    pay = job_pay(row)
    note = ""
    r = random.random()
    if r < 0.10:
        pay = int(pay * 1.5)
        note = "\n🎉 Премия! Начальство довольно, зарплата +50%"
    elif r > 0.95:
        pay = int(pay * 0.5)
        note = "\n😬 Клиент недоволен, зарплата вдвое меньше"
    if score is not None:
        pay = max(1, int(pay * mult))
        note += f"\n🎮 Мини-игра: {score}/100 · оплата ×{mult:g}"
    shifts = (row["job_shifts"] or 0) + 1
    db.execute("UPDATE users SET job_shifts=? WHERE user_id=?", (shifts, uid))
    db.commit()
    give_coins(uid, pay)
    for _i, (_n, _nm) in enumerate(CAREER):
        if _i and _n == shifts:
            give_coins(uid, 25 * _i)
            note += f"\n🎖 Повышение! Теперь ты: <b>{_nm}</b> · бонус +{25 * _i} 🪙"
    spark_note = ""
    pr_ = pair_of(uid)
    if pr_:
        bonus = max(1, pay // 5)
        spark_add(pr_["id"], bonus, "работа", row["name"])
        spark_note = f" · паре +{bonus} 🔥"
    extra = ""
    if t["kind"] == "deliver" and t["target_id"]:
        tr = urow(t["target_id"])
        if tr:
            extra = f"\n📬 {link(tr['user_id'], tr['name'])} обслужен(а)"
    await send_with_pic(bot, chat_id,
                        f"💼 {link(uid, row['name'])} выполнил(а) задание: <b>{JOBS[row['job']][0]}</b>{extra}\n"
                        f"+{pay} 🪙 · баланс {coins_of(uid)} · смен всего {shifts}{spark_note}" + note,
                        ["раб:" + row["job"]], reply_to=reply_to, api_cat="thumbsup",
                        gif_query=JOB_GIF.get(row["job"]))


async def task_check(update, context, clean):
    """Вызывается на каждое сообщение. True, если сообщение было ответом на задание."""
    me = update.effective_user
    t = open_task(me.id)
    if not t:
        return False
    if t["expires"] < time.time():
        db.execute("DELETE FROM job_tasks WHERE user_id=?", (me.id,))
        db.commit()
        await reply(update, "⌛ Время вышло: задание провалено, оплата за смену не начислена.")
        return False
    ok = False
    if t["kind"] == "deliver":
        ok = clean.startswith(t["answer"]) or clean in ("готово", "доставил", "доставила")
    elif t["kind"] == "math":
        ok = clean.replace(" ", "") == t["answer"]
    else:
        ok = clean == t["answer"]
    if not ok:
        return False
    await finish_task(context.bot, update.effective_chat.id, me.id, update.effective_message.message_id)
    return True


async def life_job_quit(update, context):
    me = update.effective_user
    row = urow(me.id)
    if row["job"] not in JOBS:
        return await reply(update, "Ты и так без работы 🙂")
    t = open_task(me.id)
    if t and t["expires"] > time.time():
        return await reply(update, "Сначала закончи текущую смену, потом можно уволиться.")
    db.execute("UPDATE users SET job='' WHERE user_id=?", (me.id,))
    db.commit()
    await reply(update, f"📤 Ты уволился с должности «{JOBS[row['job']][0]}». Новая работа: «найти работу»")


async def life_job_my(update, context):
    me = update.effective_user
    row = urow(me.id)
    if row["job"] not in JOBS:
        return await reply(update, "У тебя нет работы. Напиши «найти работу» 💼")
    name, base, cd, req = JOBS[row["job"]]
    left = (row["last_work"] or 0) + cd * 3600 - time.time()
    nxt = "можно выходить на смену прямо сейчас" if left <= 0 else f"следующая смена через {fmt_minutes(left // 60 + 1)}"
    bonus = house_bonus_pct(me.id)
    sh = row["job_shifts"] or 0
    nx = career_next(sh)
    grow = f" (до «{nx[1]}» ещё {nx[0] - sh})" if nx else " (высшая должность)"
    text = (f"💼 <b>{esc(name)}</b> · {career_title(sh)}\nЗарплата за смену: {job_pay(row)} 🪙 (база {shown_pay(base)}, "
            f"+стаж {min(sh, 100) // 2}%" + (f", +дом {bonus}%" if bonus else "") +
            f")\nСмен отработано: {sh}{grow}\n{nxt}")
    await life_send(update, context, text, key="проф:" + row["job"])
