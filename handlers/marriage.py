# -*- coding: utf-8 -*-
"""Брак, развод и семья."""

import time

from core.helpers import reply, target_user
from core.utils import disp, esc, fmt_when, link, urow
from database.db import db
from handlers.common import life_send
from services.certificate import send_certificate
from services.economy import coins_of, give_coins
from services.jobs import HOUSES, JOBS, PETS
from services.relations import DIVORCE_COST, MARRY_COST, MARRY_MIN_DAYS, MARRY_MIN_LOVE, MARRY_PIC_API, delete_pair, ea, is_married, pair_of, partner_of, spark_add, spark_line, uname


async def life_marry_propose(update, context):
    msg, me = update.effective_message, update.effective_user
    other = target_user(update)
    row = pair_of(me.id)
    if not other or other.id == me.id:
        return await reply(update, "Ответь на сообщение любимого человека: «предложить брак» 💍")
    if not row or partner_of(row, me.id) != other.id:
        return await reply(update, "Сначала нужно встречаться: «предложить встречаться».")
    if is_married(row):
        return await reply(update, "Вы уже в браке 💞")
    days = int((time.time() - row["since"]) // 86400)
    if days < MARRY_MIN_DAYS:
        return await reply(update, f"Рановато. Вы вместе {days} дн., нужно хотя бы {MARRY_MIN_DAYS}. "
                                   f"Узнайте друг друга получше 🌹")
    if row["love"] < MARRY_MIN_LOVE:
        return await reply(update, f"Искр пока маловато: {row['love']}/{MARRY_MIN_LOVE}. "
                                   f"Больше внимания: «свидание», «поцеловать», «обнять»")
    if coins_of(me.id) < MARRY_COST:
        return await reply(update, f"Свадьба стоит {MARRY_COST} 🪙, у тебя {coins_of(me.id)}. "
                                   f"Заработай: «работать» и сообщения в чате")
    db.execute("INSERT OR REPLACE INTO marry_proposals(to_id,from_id,created,pair_id) VALUES(?,?,?,?)",
               (other.id, me.id, time.time(), row["id"]))
    db.commit()
    await life_send(update, context,
                    f"💍 {link(me.id, disp(me))} делает предложение {link(other.id, disp(other))}!\n"
                    f"Ответ в течение суток: «принять брак» или «отказать в браке».\n"
                    f"Свадьба оплачивается из кошелька жениха/невесты: {MARRY_COST} 🪙",
                    key="отн:предложение брака", api="handhold")


async def life_marry_answer(update, context, accept):
    me = update.effective_user
    pr = db.execute("SELECT * FROM marry_proposals WHERE to_id=?", (me.id,)).fetchone()
    if not pr:
        return await reply(update, "Тебе никто не делал предложение брака.")
    db.execute("DELETE FROM marry_proposals WHERE to_id=?", (me.id,))
    db.commit()
    a = pr["from_id"]
    if time.time() - pr["created"] > 86400:
        return await reply(update, "Предложение устарело (прошли сутки).")
    if not accept:
        return await reply(update, f"💔 {link(me.id, disp(me))} отказал{ea(me.id)} {link(a, uname(a))} в браке.")
    row = pair_of(me.id)
    if (not row or partner_of(row, me.id) != a or is_married(row)
            or (pr["pair_id"] is not None and row["id"] != pr["pair_id"])):
        return await reply(update, "Что-то изменилось, свадьба не получится.")
    if int((time.time() - row["since"]) // 86400) < MARRY_MIN_DAYS or row["love"] < MARRY_MIN_LOVE:
        return await reply(update, "Условия свадьбы (срок отношений и искры) сейчас не выполнены.")
    if coins_of(a) < MARRY_COST:
        return await reply(update, f"У {esc(uname(a))} не хватило монет на свадьбу ({MARRY_COST} 🪙).")
    give_coins(a, -MARRY_COST, commit=False)
    db.execute("UPDATE pairs SET married_at=?, last_action=? WHERE id=?", (time.time(), time.time(), row["id"]))
    db.commit()
    spark_add(row["id"], 200, "свадьба", uname(a))
    txt = (f"🎉💍 <b>Свадьба!</b>\n{link(a, uname(a))} и {link(me.id, disp(me))} теперь муж и жена!\n"
           f"Дальше можно купить дом («купить дом»), завести питомцев («купить питомца») "
           f"и копить на семейное счастье. Профиль семьи: «семья»")
    if not await send_certificate(context.bot, update.effective_chat.id, pair_of(me.id), True,
                                  update.effective_message.message_id, caption=txt):
        await life_send(update, context, txt, key="отн:свадьба", api=MARRY_PIC_API)


async def life_divorce(update, context):
    me = update.effective_user
    row = pair_of(me.id)
    if not is_married(row):
        return await reply(update, "Ты не в браке.")
    if coins_of(me.id) < DIVORCE_COST:
        return await reply(update, f"Развод стоит {DIVORCE_COST} 🪙, а у тебя {coins_of(me.id)}.")
    p = partner_of(row, me.id)
    give_coins(me.id, -DIVORCE_COST, commit=False)
    delete_pair(row["id"])
    await life_send(update, context,
                    f"💔 {link(me.id, disp(me))} подал(а) на развод с {link(p, uname(p))} (−{DIVORCE_COST} 🪙).",
                    key="отн:развод", api="cry")


async def life_family(update, context):
    u = target_user(update) or update.effective_user
    row = pair_of(u.id)
    if not row:
        return await reply(update, "У этого человека нет пары." if u.id != update.effective_user.id
                                   else "У тебя нет пары. Ответь «предложить встречаться» 💌")
    a, b = row["a"], row["b"]
    lines = [f"👨‍👩‍👧 <b>Семья</b>: {link(a, uname(a))} ❤ {link(b, uname(b))}",
             spark_line(row)]
    if is_married(row):
        lines.append(f"💍 В браке с {fmt_when(row['married_at'])}, "
                     f"{int((time.time() - row['married_at']) // 86400) + 1} дн.")
    else:
        lines.append(f"💞 Встречаются {int((time.time() - row['since']) // 86400) + 1} дн. "
                     f"(брак доступен с {MARRY_MIN_DAYS} дн. и {MARRY_MIN_LOVE} искр)")
    for i in (a, b):
        r = urow(i)
        if not r:
            continue
        job = JOBS[r["job"]][0] if r["job"] in JOBS else "без работы"
        lines.append(f"• {esc(r['name'])}: {job}, {r['coins'] or 0} 🪙")
    hs = {urow(i)["house"] for i in (a, b) if urow(i) and urow(i)["house"] in HOUSES}
    if hs:
        lines.append("🏠 Жильё: " + ", ".join(HOUSES[h][0] for h in hs))
    pets = db.execute("SELECT * FROM pets WHERE owner IN (?,?)", (a, b)).fetchall()
    if pets:
        lines.append("🐾 Питомцы: " + ", ".join(f"{PETS[p['kind']][2]} {esc(p['name'])}" for p in pets
                                                if p["kind"] in PETS))
    await life_send(update, context, "\n".join(lines))
