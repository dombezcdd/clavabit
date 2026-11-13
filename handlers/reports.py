# -*- coding: utf-8 -*-
"""Жалобы на сообщения."""

import time

from telegram import ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup

from config import HTML, NOPREV
from core.antispam import cooldown
from core.helpers import group_only, reply
from core.ranks import can_act_on, has_rank, rank_of_id
from core.utils import disp, esc, is_owner, link
from database.db import db
from database.state import state_get


# ---------- жалобы ----------
def _msg_link(chat_id, msg_id):
    s = str(chat_id)
    return f"https://t.me/c/{s[4:]}/{msg_id}" if s.startswith("-100") else ""


@group_only
async def cmd_report(update, context):
    msg = update.effective_message
    me = update.effective_user
    tm = msg.reply_to_message
    if not tm or not tm.from_user:
        return await reply(update, "Ответь командой «репорт» на сообщение нарушителя. "
                                   "Причину можно дописать: «репорт спам»")
    t = tm.from_user
    if t.is_bot or t.id == me.id:
        return await reply(update, "На это сообщение жаловаться нельзя.")
    if rank_of_id(t.id) > 0 or is_owner(t):
        return await reply(update, "Это сообщение админа, пожаловаться нельзя.")
    if not cooldown(("report", me.id), 60):
        return await reply(update, "Подожди минуту перед следующей жалобой ⏳")
    reason = " ".join(context.args or []).strip()[:200]
    cur = db.execute("INSERT INTO reports(target_id,target_name,msg_id,reporter,reason,created,status) "
                     "VALUES(?,?,?,?,?,?, 'open')",
                     (t.id, disp(t), tm.message_id, disp(me), reason, time.time()))
    db.commit()
    rid = cur.lastrowid
    ids = {r["user_id"] for r in db.execute("SELECT user_id FROM users WHERE arank>=1")}
    oid = state_get("owner_id")
    if oid:
        ids.add(int(oid))
    hidden = "".join(f'<a href="tg://user?id={u}">​</a>' for u in list(ids)[:30])
    ln = _msg_link(update.effective_chat.id, tm.message_id)
    text = (f"🚨 <b>Жалоба #{rid}</b>\nНа: {link(t.id, disp(t))}\nОт: {esc(disp(me))}\n"
            f"Причина: {esc(reason or 'не указана')}"
            + (f"\n<a href=\"{ln}\">Перейти к сообщению</a>" if ln else "") + hidden)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔇 Мут 1ч", callback_data=f"rp:mute:{rid}"),
         InlineKeyboardButton("⛔ Бан", callback_data=f"rp:ban:{rid}")],
        [InlineKeyboardButton("🗑 Удалить сообщение", callback_data=f"rp:del:{rid}"),
         InlineKeyboardButton("✖ Закрыть", callback_data=f"rp:close:{rid}")]])
    await context.bot.send_message(update.effective_chat.id, text, parse_mode=HTML,
                                   reply_markup=kb, link_preview_options=NOPREV)
    try:
        await msg.delete()          # убираем команду, чтобы не светить жалобщика (нужно право удалять)
    except Exception:
        pass


async def on_report_btn(update, context):
    q = update.callback_query
    parts = (q.data or "").split(":")
    if len(parts) != 3 or parts[0] != "rp" or not parts[2].isdigit():
        return await q.answer()
    act, rid = parts[1], int(parts[2])
    r = db.execute("SELECT * FROM reports WHERE id=?", (rid,)).fetchone()
    if not r or r["status"] != "open":
        return await q.answer("Жалоба уже обработана", show_alert=True)
    key = "бан" if act == "ban" else "мут"
    if not has_rank(q.from_user, key):
        return await q.answer("Нужен ранг модератора", show_alert=True)
    chat_id = q.message.chat.id
    result = ""
    try:
        if act in ("mute", "ban") and not can_act_on(q.from_user, r["target_id"]):
            return await q.answer("У нарушителя ранг не ниже твоего", show_alert=True)
        if act == "mute":
            until = time.time() + 3600
            await context.bot.restrict_chat_member(chat_id, r["target_id"], ChatPermissions.no_permissions(),
                                                   until_date=int(until))
            db.execute("INSERT OR REPLACE INTO mutes(user_id,name,until,reason,by_name,created) "
                       "VALUES(?,?,?,?,?,?)", (r["target_id"], r["target_name"], until,
                                               f"жалоба #{rid}: {r['reason'] or '-'}", disp(q.from_user), time.time()))
            result = "🔇 Мут на 1 час"
        elif act == "ban":
            await context.bot.ban_chat_member(chat_id, r["target_id"])
            result = "⛔ Бан"
        elif act == "del":
            await context.bot.delete_message(chat_id, r["msg_id"])
            result = "🗑 Сообщение удалено"
        else:
            result = "✖ Закрыто без действий"
    except Exception as e:
        return await q.answer(f"Не вышло: {str(e)[:150]}", show_alert=True)
    db.execute("UPDATE reports SET status='done' WHERE id=?", (rid,))
    db.commit()
    await q.answer("Готово")
    try:
        await q.edit_message_text((q.message.text_html or "") + f"\n\n{result} · {esc(disp(q.from_user))}",
                                  parse_mode=HTML, link_preview_options=NOPREV)
    except Exception:
        pass
