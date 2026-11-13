# -*- coding: utf-8 -*-
"""Админ-команды рангов и доступа."""

from config import OWNER_USERNAME
from core.helpers import reply, resolve_target, why_no_target
from core.ranks import ADMIN_TITLES, DEFAULT_RANKS, MAX_RANK, need, rank_title, required_rank
from core.utils import esc, link, urow
from database.db import db
from database.state import state_get


async def _set_rank(update, context, rank, args):
    uid, name, rest, err = resolve_target(update, args)
    if err:
        return await reply(update, err)
    if not uid:
        return await reply(update, why_no_target(
            update, "Ответь на сообщение участника или укажи @юзернейм: повысить 2"))
    oid = state_get("owner_id")
    if oid and str(uid) == oid:
        return await reply(update, "Ранг владельца изменить нельзя.")
    if not urow(uid):
        return await reply(update, "Этот участник ещё не писал в чат.")
    db.execute("UPDATE users SET arank=? WHERE user_id=?", (rank, uid))
    db.commit()
    if rank:
        await reply(update, f"⭐ {link(uid, name)} получает должность "
                            f"<b>{esc(rank_title(rank))}</b> (ранг {rank}).")
    else:
        await reply(update, f"{link(uid, name)} лишён админ-ранга.")


@need("повысить")
async def cmd_promote(update, context):
    rank, rest = None, []
    for a in (context.args or []):
        if rank is None and a.isdigit() and len(a) == 1:
            rank = int(a)
        else:
            rest.append(a)
    if rank is None or rank > MAX_RANK:
        return await reply(update, "Формат: «повысить 2» ответом на сообщение или "
                                   "«повысить 2 @юзернейм». Ранг от 1 до 8, 0 — снять ранг.\n" +
                                   "\n".join(f"{k} — {v}" for k, v in ADMIN_TITLES.items()))
    await _set_rank(update, context, rank, rest)


@need("повысить")
async def cmd_demote(update, context):
    await _set_rank(update, context, 0, list(context.args or []))


@need("дк")
async def cmd_access(update, context):
    args = [a.lower() for a in (context.args or [])]
    if not args:
        lines = ["🔐 <b>Доступ к командам</b> (с какого ранга и выше)"]
        for k in DEFAULT_RANKS:
            lines.append(f"• {k} — {required_rank(k)} ({rank_title(required_rank(k))})")
        lines.append("\nИзменить: «дк мут 2». Выдать ранг человеку: «повысить 2» ответом на сообщение.")
        return await reply(update, "\n".join(lines))
    if len(args) < 2 or not args[-1].isdigit():
        return await reply(update, "Формат: «дк мут 2» (название команды и ранг от 1 до 8).")
    key, rank = " ".join(args[:-1]), int(args[-1])
    if key not in DEFAULT_RANKS:
        return await reply(update, f"Не знаю команду «{esc(key)}». Доступны: " +
                           ", ".join(DEFAULT_RANKS))
    if not 1 <= rank <= MAX_RANK:
        return await reply(update, "Ранг должен быть от 1 до 8.")
    db.execute("INSERT INTO cmd_access(cmd,rank) VALUES(?,?) "
               "ON CONFLICT(cmd) DO UPDATE SET rank=excluded.rank", (key, rank))
    db.commit()
    await reply(update, f"✅ Команда «{esc(key)}» теперь доступна с ранга {rank} "
                        f"({esc(rank_title(rank))}) и выше.")


@need("админы")
async def cmd_admins(update, context):
    only = None
    for a in (context.args or []):
        if a.isdigit():
            only = int(a)
    rows = db.execute("SELECT user_id, name, tag, arank FROM users WHERE arank>0 "
                      "ORDER BY arank DESC, name").fetchall()
    lines = ["👮 <b>Админы по рангам</b>"]
    if only is None or only == MAX_RANK:
        lines.append(f"{MAX_RANK} — {rank_title(MAX_RANK)}: @{OWNER_USERNAME} (владелец)")
    for r in rows:
        if only is not None and r["arank"] != only:
            continue
        lines.append(f"{r['arank']} — {rank_title(r['arank'])}: {link(r['user_id'], r['name'])}")
    if len(lines) == 1:
        lines.append("Пока никого. Выдать ранг: «повысить 2» ответом на сообщение.")
    await reply(update, "\n".join(lines))
