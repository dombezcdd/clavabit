# -*- coding: utf-8 -*-
"""Админ-команды для списка профессий."""

import json
import re

from core.helpers import reply
from core.ranks import need
from core.utils import esc
from database.db import db
from services.jobs import BUILTIN_JOBS, JOBS, shown_pay


async def cmd_jobs_list_impl(update):
    lines = ["💼 <b>Список работ</b>"]
    for k, (name, pay, cd, req) in JOBS.items():
        r = ", ".join(f"{lbl} {req[f]}" for f, lbl in (("level", "ур."), ("days", "дн."), ("msgs", "сообщ.")) if f in req)
        lines.append(f"• <b>{esc(name)}</b> ({esc(k)}): {shown_pay(pay)} 🪙, пауза {cd} ч." + (f" · нужно: {r}" if r else "")
                     + ("" if k in BUILTIN_JOBS else " · своя"))
    await reply(update, "\n".join(lines))


@need("список работ")
async def cmd_jobs_list(update, context):
    await cmd_jobs_list_impl(update)


@need("добавить работу")
async def cmd_job_add(update, context):
    a = list(context.args or [])
    usage = ("Формат: добавить работу Грузчик 45 3 ур=2 дн=1 сообщ=100\n"
             "(название одним словом, оплата за смену в 🪙, пауза в часах; условия ур=, дн=, сообщ= можно не писать)")
    if len(a) < 3 or not a[1].isdigit() or not a[2].isdigit():
        return await reply(update, usage)
    key = a[0].lower()[:20]
    if key in BUILTIN_JOBS:
        return await reply(update, "Такая работа уже есть в боте, выбери другое название.")
    pay, cd = int(a[1]), int(a[2])
    if not (1 <= pay <= 5000) or not (1 <= cd <= 48):
        return await reply(update, "Оплата от 1 до 5000 🪙, пауза от 1 до 48 часов.")
    req = {}
    for x in a[3:]:
        m = re.fullmatch(r"(ур|дн|сообщ)=(\d{1,6})", x.lower())
        if not m:
            return await reply(update, usage)
        req[{"ур": "level", "дн": "days", "сообщ": "msgs"}[m.group(1)]] = int(m.group(2))
    name = key[:1].upper() + key[1:]
    db.execute("INSERT OR REPLACE INTO custom_jobs(key,name,pay,cd,req) VALUES(?,?,?,?,?)",
               (key, name, pay, cd, json.dumps(req)))
    db.commit()
    JOBS[key] = (name, pay, cd, req)
    await reply(update, f"✅ Работа добавлена: <b>{esc(name)}</b>, {pay} 🪙 за смену, пауза {cd} ч. "
                        f"Она появится в «найти работу».")


@need("удалить работу")
async def cmd_job_del(update, context):
    a = list(context.args or [])
    key = a[0].lower() if a else ""
    if key in BUILTIN_JOBS:
        return await reply(update, "Встроенные работы удалить нельзя, только добавленные командой.")
    if key not in JOBS:
        return await reply(update, "Такой работы нет. Список: «список работ»")
    JOBS.pop(key, None)
    db.execute("DELETE FROM custom_jobs WHERE key=?", (key,))
    db.execute("UPDATE users SET job='' WHERE job=?", (key,))
    db.commit()
    await reply(update, f"🗑 Работа «{esc(key)}» удалена, у работавших она снята.")
