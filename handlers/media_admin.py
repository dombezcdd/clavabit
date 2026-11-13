# -*- coding: utf-8 -*-
"""Админ-команды для картинок rp."""

import time

from content.data import RP
from core.helpers import reply
from core.ranks import need
from core.utils import disp, esc
from database.db import db
from services.jobs import HOUSES, JOBS, PETS
from services.relations import REL_EVENTS


def pic_key(name):
    name = name.strip().lower()
    if name in RP:
        return name
    if name.startswith("отн "):
        e = name[4:].strip()
        if e in REL_EVENTS:
            return "отн:" + e
    for pref, table in (("раб ", JOBS), ("дом ", HOUSES), ("пет ", PETS)):
        if name.startswith(pref) and name[len(pref):].strip() in table:
            return pref.strip() + ":" + name[len(pref):].strip()
    if name in ("пет кормление", "питомец кормление"):
        return "пет:кормление"
    return None


def pic_names_text():
    return ("РП-действия: " + ", ".join(RP) + "\n\nОтношения (пиши с «отн »):\n" +
            "\n".join(f"отн {k} — {v}" for k, v in REL_EVENTS.items()) +
            "\n\nРаботы: " + ", ".join("раб " + k for k in JOBS) +
            "\nДома: " + ", ".join("дом " + k for k in HOUSES) +
            "\nПитомцы: " + ", ".join("пет " + k for k in PETS) + ", пет кормление")


@need("добавить картинку")
async def cmd_pic_add(update, context):
    msg = update.effective_message
    name = " ".join(context.args or [])
    key = pic_key(name)
    if not key:
        return await reply(update, "Ответь на гифку, картинку или видео и напиши "
                                   "«добавить картинку обнять».\n\n" + esc(pic_names_text()))
    r = msg.reply_to_message
    kind = file_id = unique = None
    if r:
        if r.animation:
            kind, file_id, unique = "animation", r.animation.file_id, r.animation.file_unique_id
        elif r.video:
            kind, file_id, unique = "video", r.video.file_id, r.video.file_unique_id
        elif r.photo:
            kind, file_id, unique = "photo", r.photo[-1].file_id, r.photo[-1].file_unique_id
        elif r.document and (r.document.mime_type or "").startswith(("image/", "video/")):
            kind, file_id, unique = "document", r.document.file_id, r.document.file_unique_id
    if not file_id:
        return await reply(update, "Ответь этой командой на сообщение с гифкой, картинкой или видео.")
    if db.execute("SELECT 1 FROM rp_media WHERE action=? AND file_unique=?", (key, unique)).fetchone():
        return await reply(update, "Эта картинка уже сохранена для этого действия.")
    db.execute("INSERT INTO rp_media(action,kind,file_id,file_unique,added_by,created) "
               "VALUES(?,?,?,?,?,?)", (key, kind, file_id, unique,
                                       disp(update.effective_user), time.time()))
    db.commit()
    n = db.execute("SELECT COUNT(*) FROM rp_media WHERE action=?", (key,)).fetchone()[0]
    await reply(update, f"✅ Сохранил для «{esc(name.lower())}». Картинок у этого действия: {n}.")


@need("список картинок")
async def cmd_pic_list(update, context):
    counts = {r["action"]: r["c"] for r in db.execute(
        "SELECT action, COUNT(*) c FROM rp_media GROUP BY action")}
    lines = ["🖼 <b>Картинки (сколько загружено)</b>", "<b>РП:</b>"]
    for k in RP:
        lines.append(f"• {k} — {counts.get(k, 0)}" + ("" if counts.get(k) else " (будет гифка из интернета)"))
    lines.append("<b>Отношения:</b>")
    for k in REL_EVENTS:
        lines.append(f"• отн {k} — {counts.get('отн:' + k, 0)}")
    lines.append("<b>Работы, дома, питомцы:</b>")
    for pref, table in (("раб", JOBS), ("дом", HOUSES), ("пет", PETS)):
        for k in table:
            if counts.get(pref + ":" + k):
                lines.append(f"• {pref} {k} — {counts[pref + ':' + k]}")
    lines.append("(остальные пустые: бот пришлёт подходящую гифку или просто текст)")
    await reply(update, "\n".join(lines))


@need("очистить картинки")
async def cmd_pic_clear(update, context):
    name = " ".join(context.args or [])
    key = pic_key(name)
    if not key:
        return await reply(update, "Напиши, у какого действия удалить картинки: «очистить картинки обнять».")
    n = db.execute("DELETE FROM rp_media WHERE action=?", (key,)).rowcount
    db.commit()
    await reply(update, f"🗑 Удалил картинок у «{esc(name.lower())}»: {n}.")
