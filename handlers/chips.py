# -*- coding: utf-8 -*-
"""Передача казино-фишек другому игроку: «передать фишки 100» ответом на сообщение (или с @ником)."""

import re

from config import ALLOWED, HTML
from core.antispam import cooldown
from core.helpers import reply, target_user
from core.utils import disp, link, today, touch
from database.db import db
from services.casino import chips_add, chips_of

RE = re.compile(r"^(?:передать|перевести|отдать|подарить)\s+фишки\s+(?:@\w+\s+)?(\d{1,6})(?:\s+@\w+)?$")
MIN_SEND, FEE_PCT, DAY_LIMIT = 10, 10, 3000      # минимум, комиссия %, сколько можно отправить за сутки


def _sent_today(uid):
    db.execute("CREATE TABLE IF NOT EXISTS chip_send(user_id INTEGER, day TEXT, sent INTEGER, PRIMARY KEY(user_id, day))")
    r = db.execute("SELECT sent FROM chip_send WHERE user_id=? AND day=?", (uid, today())).fetchone()
    return r["sent"] if r else 0


async def handle_chips_text(update, context, low, text):
    m = RE.match(low.strip())
    if not m or update.effective_chat.id not in ALLOWED:
        return False
    me = update.effective_user
    touch(me)
    foe = target_user(update)
    amt = int(m.group(1))
    if not foe or foe.is_bot or foe.id == me.id:
        await reply(update, "Ответь на сообщение того, кому передаёшь: «передать славБакс 100»")
        return True
    if amt < MIN_SEND:
        await reply(update, f"Минимум для передачи: {MIN_SEND} 💵")
        return True
    if chips_of(me.id) < amt:
        await reply(update, f"Не хватает славБакс: у тебя {chips_of(me.id)} 💵")
        return True
    if _sent_today(me.id) + amt > DAY_LIMIT:
        await reply(update, f"Лимит передач в сутки: {DAY_LIMIT} 💵 (сегодня отправлено {_sent_today(me.id)})")
        return True
    if not cooldown(("chipsend", me.id), 20):
        await reply(update, "Не так быстро, подожди пару секунд")
        return True
    touch(foe)
    got = amt - amt * FEE_PCT // 100
    chips_add(me.id, -amt, disp(me))
    chips_add(foe.id, got, disp(foe))
    db.execute("INSERT INTO chip_send(user_id,day,sent) VALUES(?,?,?) ON CONFLICT(user_id,day) DO UPDATE SET sent=sent+?",
               (me.id, today(), amt, amt))
    db.commit()
    await reply(update, f"💵 {link(me.id, disp(me))} передал(а) {link(foe.id, disp(foe))} <b>{got}</b> славБакс "
                        f"(комиссия {FEE_PCT}%: {amt - got})\nУ тебя осталось: {chips_of(me.id)} 💵")
    return True
