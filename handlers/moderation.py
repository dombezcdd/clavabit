# -*- coding: utf-8 -*-
"""Модерация и статистика: мут, бан, теги, итоги, вопрос и викторина."""

import time

from telegram import ChatPermissions

from content.texts import ADMIN_HELP
from core.durations import fmt_minutes, parse_duration
from core.helpers import reply, resolve_target, why_no_target
from core.ranks import can_act_on, need
from core.utils import disp, esc, link, today, urow
from database.db import db
from services.quiz import post_question, post_quiz
from services.stats import fmt_top, top_rows, week_start
from services.summary import send_summary


@need("админка")
async def cmd_admin(update, context):
    await reply(update, ADMIN_HELP)


MUTE_USAGE = ("Формат: «мут 30 @юзернейм причина» или ответом на сообщение: «мут 30 причина». "
              "Время: 30 (минуты), 2ч, 1д.")


@need("мут")
async def cmd_mute(update, context):
    msg = update.effective_message
    args = list(context.args or [])
    from_slash = (msg.text or "").startswith("/")
    minutes, used = parse_duration(args)
    if minutes is None:
        minutes = 60
        first = args[0] if args else ""
        if args and not from_slash and not (first.startswith("@") or
                                            (first.isdigit() and len(first) > 6)):
            return                      # это обычная фраза, а не команда
    else:
        args = args[used:]
    uid, name, rest, err = resolve_target(update, args)
    if err:
        return await reply(update, err)
    if not uid:
        return await reply(update, why_no_target(update, MUTE_USAGE))
    if minutes < 1:
        return await reply(update, "Время должно быть не меньше 1 минуты.")
    minutes = min(minutes, 366 * 1440)
    actor = update.effective_user
    if not can_act_on(actor, uid):
        return await reply(update, "Нельзя: у этого участника ранг не ниже твоего.")
    reason = " ".join(rest).strip()[:200]
    until = time.time() + minutes * 60
    try:
        await context.bot.restrict_chat_member(
            update.effective_chat.id, uid, ChatPermissions.no_permissions(),
            until_date=int(until))
    except Exception as e:
        return await reply(update, f"Не вышло: {esc(e)}\n"
                                   "Проверь, что у бота есть право блокировать участников "
                                   "и что это не админ чата.")
    db.execute("INSERT OR REPLACE INTO mutes(user_id,name,until,reason,by_name,created) "
               "VALUES(?,?,?,?,?,?)", (uid, name, until, reason, disp(actor), time.time()))
    db.commit()
    await reply(update, f"🔇 {link(uid, name)} в муте на {fmt_minutes(minutes)}."
                        + (f"\nПричина: {esc(reason)}" if reason else ""))


@need("размут")
async def cmd_unmute(update, context):
    uid, name, rest, err = resolve_target(update, list(context.args or []))
    if err:
        return await reply(update, err)
    if not uid:
        return await reply(update, why_no_target(
            update, "Ответь на сообщение участника или укажи @юзернейм: размут"))
    if uid != update.effective_user.id and not can_act_on(update.effective_user, uid):
        return await reply(update, "Нельзя снять ограничение с участника, чей ранг не ниже твоего.")
    try:
        await context.bot.restrict_chat_member(
            update.effective_chat.id, uid, ChatPermissions.all_permissions())
    except Exception as e:
        return await reply(update, f"Не вышло: {esc(e)}")
    db.execute("DELETE FROM mutes WHERE user_id=?", (uid,))
    db.commit()
    await reply(update, f"🔊 {link(uid, name)} размучен.")


@need("список мута")
async def cmd_mutelist(update, context):
    db.execute("DELETE FROM mutes WHERE until<?", (time.time(),))
    db.commit()
    rows = db.execute("SELECT * FROM mutes ORDER BY until").fetchall()
    if not rows:
        return await reply(update, "Сейчас в муте никого нет 🔊")
    lines = ["🔇 <b>Список мута</b>"]
    for i, r in enumerate(rows, 1):
        left = int((r["until"] - time.time()) // 60) + 1
        lines.append(f"{i}. {link(r['user_id'], r['name'])} — осталось {fmt_minutes(left)}\n"
                     f"    причина: {esc(r['reason'] or 'не указана')} · выдал: {esc(r['by_name'])}")
    await reply(update, "\n".join(lines))


@need("бан")
async def cmd_ban(update, context):
    uid, name, rest, err = resolve_target(update, list(context.args or []))
    if err:
        return await reply(update, err)
    if not uid:
        return await reply(update, why_no_target(
            update, "Ответь на сообщение участника или укажи @юзернейм: бан"))
    if not can_act_on(update.effective_user, uid):
        return await reply(update, "Нельзя: у этого участника ранг не ниже твоего.")
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, uid)
        db.execute("DELETE FROM mutes WHERE user_id=?", (uid,))
        db.commit()
        await reply(update, f"⛔ {link(uid, name)} забанен.")
    except Exception as e:
        await reply(update, f"Не вышло: {esc(e)}")


@need("разбан")
async def cmd_unban(update, context):
    uid, name, rest, err = resolve_target(update, list(context.args or []))
    if err:
        return await reply(update, err)
    if not uid:
        return await reply(update, why_no_target(
            update, "Ответь на сообщение или укажи id / @юзернейм: разбан 123456789"))
    try:
        await context.bot.unban_chat_member(update.effective_chat.id, uid, only_if_banned=True)
        await reply(update, f"✅ {link(uid, name)} разбанен.")
    except Exception as e:
        await reply(update, f"Не вышло: {esc(e)}")


@need("тег")
async def cmd_tag(update, context):
    uid, name, rest, err = resolve_target(update, list(context.args or []))
    if err:
        return await reply(update, err)
    if not uid:
        return await reply(update, why_no_target(
            update, "Ответь на сообщение участника: тег Текст тега"))
    tag = " ".join(rest).strip()[:30]
    if not tag:
        return await reply(update, "Напиши текст тега: тег Текст")
    if not urow(uid):
        return await reply(update, "Этот участник ещё не писал в чат.")
    db.execute("UPDATE users SET tag=? WHERE user_id=?", (tag, uid))
    db.commit()
    await reply(update, f"🏷 Тег для {esc(name)}: <b>{esc(tag)}</b>")


@need("снять тег")
async def cmd_untag(update, context):
    uid, name, rest, err = resolve_target(update, list(context.args or []))
    if err:
        return await reply(update, err)
    if not uid:
        return await reply(update, why_no_target(
            update, "Ответь на сообщение участника: снять тег"))
    db.execute("UPDATE users SET tag='' WHERE user_id=?", (uid,))
    db.commit()
    await reply(update, f"Тег у {esc(name)} снят.")


@need("статистика")
async def cmd_stat(update, context):
    d, wk = today(), week_start()
    one = lambda q, *a: db.execute(q, a).fetchone()[0]
    msgs_d = one("SELECT COALESCE(SUM(cnt),0) FROM daily WHERE day=?", d)
    msgs_w = one("SELECT COALESCE(SUM(cnt),0) FROM daily WHERE day>=? AND day<=?", wk, d)
    act_d = one("SELECT COUNT(*) FROM daily WHERE day=? AND cnt>0", d)
    act_w = one("SELECT COUNT(DISTINCT user_id) FROM daily WHERE day>=? AND day<=? AND cnt>0", wk, d)
    known = one("SELECT COUNT(*) FROM users")
    reg = one("SELECT COUNT(*) FROM users WHERE registered=1 AND total>0")
    rows = top_rows(wk, d, 5)
    await reply(update,
                f"📈 <b>Активность чата</b>\n"
                f"Сегодня: {msgs_d} сообщ., активных: {act_d}\n"
                f"За 7 дней: {msgs_w} сообщ., активных: {act_w}\n"
                f"Всего участников в базе: {known}, в созыве: {reg}\n\n"
                f"<b>Топ-5 недели</b>\n" + (fmt_top(rows) if rows else "—"))


@need("слова дня")
async def cmd_topwords(update, context):
    rows = db.execute("SELECT word, cnt FROM words WHERE day=? ORDER BY cnt DESC LIMIT 15",
                      (today(),)).fetchall()
    if not rows:
        return await reply(update, "Пока мало данных.")
    await reply(update, "💬 <b>О чём говорят сегодня</b>\n" +
                ", ".join(f"{esc(r['word'])} ({r['cnt']})" for r in rows))


@need("итоги")
async def cmd_award(update, context):
    await send_summary(context.bot, today(), False)


@need("запустить вопрос")
async def cmd_question(update, context):
    await post_question(context.bot)


@need("запустить викторину")
async def cmd_quiz(update, context):
    await post_quiz(context.bot)
