# -*- coding: utf-8 -*-
"""Ограбления, тюрьма и суд: «ограбить», «суд», «адвокаты», «нанять адвоката», «залог»."""

import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest

from config import ALLOWED, HTML
from core.durations import fmt_minutes
from core.helpers import reply, resolve_target, target_user
from core.logger import log
from core.ranks import has_rank
from core.utils import disp, esc, link, touch, urow
from database.db import db
from services.court import (BAIL, FILE_WINDOW, JAIL_HOURS, LAWYER_FEE, LAWYER_WEIGHT, MIN_VOTES, ROB_CD, TRIAL_MIN,
                            active_case_of, case_by_id, close_case, hire_lawyer, jail_left, open_case, pay_bail, rob,
                            tally, vote)
from services.economy import COIN

CRIME_WORDS = {"ограбить", "украсть", "обокрасть"}


async def handle_court_text(update, context, low, text):
    if update.effective_chat.id not in ALLOWED:
        return False
    me = update.effective_user
    word = low.split()[0] if low.split() else ""
    if word in CRIME_WORDS and len(low.split()) <= 3:
        return await _rob(update, context, me, text)
    if low in ("суд", "моё дело", "мое дело", "дело"):
        return await _case_info(update, me)
    if low in ("адвокаты", "список адвокатов"):
        return await _lawyers(update)
    if low.startswith("нанять адвоката"):
        return await _hire(update, me, text)
    if low in ("залог", "внести залог", "выйти из тюрьмы"):
        ok, res = pay_bail(me.id)
        await reply(update, f"🔓 Залог {BAIL} {COIN} внесён, ты на свободе" if ok else res)
        return True
    if low in ("тюрьма", "заключённые", "заключенные"):
        rows = db.execute("SELECT user_id,name,jail_until FROM users WHERE jail_until>? LIMIT 20", (time.time(),)).fetchall()
        await reply(update, "🔒 <b>Тюрьма</b>\n" + "\n".join(
            f"{link(r['user_id'], r['name'] or '?')} — ещё {fmt_minutes((r['jail_until'] - time.time()) // 60 + 1)}"
            for r in rows) if rows else "Тюрьма пуста 🕊")
        return True
    if low.startswith(("приговор виновен", "приговор оправдать", "отменить суд")):
        return await _admin_verdict(update, context, me, low)
    return False


async def _rob(update, context, me, text):
    touch(me)
    t = target_user(update)
    if t:
        vid, vname = t.id, disp(t)
        if getattr(t, "is_bot", False):
            await reply(update, "Боты ничего не носят с собой 🤖")
            return True
    else:
        vid, vname, _, err = resolve_target(update, text.split()[1:])
        if err or not vid:
            await reply(update, err or "Ответь на сообщение жертвы командой «ограбить» или напиши «ограбить @юз»")
            return True
    if vid == me.id:
        await reply(update, "Сам у себя красть смысла нет 🙃")
        return True
    code, data = rob(me.id, vid)
    who = link(vid, vname)
    me_l = link(me.id, disp(me))
    if code == "jail":
        await reply(update, f"🔒 Ты в тюрьме ещё {fmt_minutes(data // 60 + 1)}. Залог: «залог» ({BAIL} {COIN})")
    elif code == "cd":
        await reply(update, f"Полиция ещё ищет тебя. Следующая попытка через {fmt_minutes(data // 60 + 1)} ⏳")
    elif code == "poor":
        await reply(update, f"У {who} почти ничего нет (меньше {data} {COIN}). Не стоит рисковать")
    elif code == "caught":
        await reply(update, f"🚨 {me_l} попытался(ась) ограбить {who}, но охрана поймала. Штраф {data} {COIN}")
    else:
        cid, amount = data
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⚖️ Подать в суд", callback_data=f"crt:file:{cid}")]])
        await reply(update, f"🕶 {me_l} ограбил(а) {who} на <b>{amount}</b> {COIN}!\n"
                            f"{who}, ты можешь подать в суд в течение {FILE_WINDOW // 60} минут", reply_markup=kb)
    return True


def _case_text(case):
    g, i, n = tally(case)
    p, d = urow(case["plaintiff"]), urow(case["defendant"])
    left = max(0, int(case["end"] - time.time()) // 60)
    lines = [f"⚖️ <b>Дело №{case['id']}</b> · кража {case['amount']} {COIN}",
             f"Истец: {link(case['plaintiff'], p['name'])} · Ответчик: {link(case['defendant'], d['name'])}"]
    if case["lawyer_p"]:
        lines.append(f"Адвокат истца: {link(case['lawyer_p'], urow(case['lawyer_p'])['name'])}")
    if case["lawyer_d"]:
        lines.append(f"Адвокат ответчика: {link(case['lawyer_d'], urow(case['lawyer_d'])['name'])}")
    lines.append(f"\nГолосуют присяжные (любой участник чата, кроме сторон): виновен {g:g} · невиновен {i:g} "
                 f"(голосов {n}, нужно минимум {MIN_VOTES})")
    lines.append(f"До приговора ~{left} мин. Нанять адвоката: «нанять адвоката @юз» ({LAWYER_FEE} {COIN})")
    return "\n".join(lines)


def _vote_kb(cid):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔴 Виновен", callback_data=f"crt:g:{cid}"),
                                  InlineKeyboardButton("🟢 Невиновен", callback_data=f"crt:i:{cid}")]])


async def _case_info(update, me):
    c = active_case_of(me.id)
    if not c:
        await reply(update, "У тебя нет открытого дела. Если тебя ограбили — нажми «Подать в суд» под сообщением об ограблении")
        return True
    await reply(update, _case_text(c), reply_markup=_vote_kb(c["id"]))
    return True


async def _lawyers(update):
    rows = db.execute("SELECT user_id,name,job_shifts FROM users WHERE job='адвокат' ORDER BY job_shifts DESC LIMIT 15").fetchall()
    await reply(update, "⚖️ <b>Адвокаты</b>\n" + "\n".join(
        f"{link(r['user_id'], r['name'] or '?')} · смен {r['job_shifts'] or 0}" for r in rows)
        + f"\nУслуги: {LAWYER_FEE} {COIN}, адвокат даёт стороне +{LAWYER_WEIGHT:g} голоса. "
          "Нанять: «нанять адвоката @юз» (когда идёт твоё дело)"
        if rows else "Адвокатов пока нет. Профессия «адвокат» доступна в «найти работу»")
    return True


async def _hire(update, me, text):
    case = active_case_of(me.id)
    if not case:
        await reply(update, "У тебя нет открытого дела")
        return True
    t = target_user(update)
    if t:
        lid = t.id
    else:
        lid, _, _, err = resolve_target(update, text.split()[2:])
        if not lid:
            await reply(update, err or "Ответь на сообщение адвоката или напиши «нанять адвоката @юз»")
            return True
    ok, res = hire_lawyer(case, me.id, lid)
    if not ok:
        await reply(update, res)
        return True
    c2 = case_by_id(case["id"])
    await reply(update, f"⚖️ Адвокат {link(lid, urow(lid)['name'])} взялся за дело №{case['id']} (оплата {LAWYER_FEE} {COIN})")
    return True


async def _admin_verdict(update, context, me, low):
    if not has_rank(me, "ban"):
        await reply(update, "Выносить приговор вне очереди может только администрация")
        return True
    t = target_user(update)
    parts = low.split()
    case = None
    if len(parts) >= 3 and parts[-1].isdigit():
        case = case_by_id(int(parts[-1]))
    elif t:
        case = active_case_of(t.id)
    if not case or case["status"] != "vote":
        await reply(update, "Укажи номер активного дела: «приговор виновен 3» или «приговор оправдать 3»")
        return True
    force = None if low.startswith("отменить") else low.startswith("приговор виновен")
    if force is None:
        db.execute("UPDATE court_cases SET status='void' WHERE id=?", (case["id"],)); db.commit()
        await reply(update, f"Дело №{case['id']} отменено администрацией")
        return True
    await _announce(context.bot, case, *close_case(case, force=force))
    return True


async def _announce(bot, case, guilty, data):
    g, i, n, paid = data
    d, p = urow(case["defendant"]), urow(case["plaintiff"])
    if guilty is None:
        text = f"⚖️ Дело №{case['id']} закрыто: присяжных меньше {MIN_VOTES}. Приговора нет"
    elif guilty:
        text = (f"🔨 <b>Приговор по делу №{case['id']}: ВИНОВЕН</b>\n{link(d['user_id'], d['name'])} возвращает "
                f"{paid} {COIN} и отправляется в тюрьму на {JAIL_HOURS} ч. Голоса: {g:g} : {i:g}")
    else:
        text = (f"🕊 <b>Приговор по делу №{case['id']}: НЕВИНОВЕН</b>\n{link(d['user_id'], d['name'])} оправдан(а). "
                f"Голоса: {g:g} : {i:g}")
    try:
        await bot.send_message(case["chat_id"], text, parse_mode=HTML)
    except Exception:
        log.exception("court announce")


async def on_court_btn(update, context):
    q = update.callback_query
    if not q.message or q.message.chat_id not in ALLOWED:
        return await q.answer()
    p = (q.data or "").split(":")
    if len(p) != 3 or not p[2].isdigit():
        return await q.answer()
    act, num = p[1], int(p[2])
    u = q.from_user
    touch(u)
    if act == "file":
        case = open_case(num, u.id, q.message.chat_id)
        if not case:
            return await q.answer("Подать иск может только потерпевший в течение 30 минут", show_alert=True)
        await q.answer("Дело открыто")
        return await context.bot.send_message(q.message.chat_id, _case_text(case), parse_mode=HTML,
                                              reply_markup=_vote_kb(case["id"]))
    case = case_by_id(num)
    if not case:
        return await q.answer("Дело не найдено", show_alert=True)
    ok, res = vote(case, u.id, "g" if act == "g" else "i")
    await q.answer(res, show_alert=not ok)
    if ok:
        try:
            await q.edit_message_text(_case_text(case), parse_mode=HTML, reply_markup=_vote_kb(case["id"]))
        except BadRequest:
            pass


async def court_tick(bot):
    now = time.time()
    for case in db.execute("SELECT * FROM court_cases WHERE status='vote' AND end<=?", (now,)).fetchall():
        await _announce(bot, case, *close_case(case))
