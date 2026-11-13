# -*- coding: utf-8 -*-
"""rp-действия и репутация."""

import re
from types import SimpleNamespace

from content.data import RP, RP_API
from core.helpers import reply, target_user, why_no_target
from core.utils import disp, find_by_username, link, today, urow
from database.db import db
from services.media import send_with_pic
from services.relations import REL_GAIN, REL_PIC, ea, offended_block, pair_of, partner_of, rel_add
from services.xp import bump, check_quests


# ============================ ОБЫЧНЫЕ СООБЩЕНИЯ ============================
REP_RE = re.compile(r"^\+\s?(реп|rep)\b\s*(@\w+)?", re.I)


async def handle_rep(update, context, m):
    giver = update.effective_user
    target_id, target_name = None, None
    if m.group(2):
        r = find_by_username(m.group(2))
        if r:
            target_id, target_name = r["user_id"], r["name"]
    else:
        t = target_user(update)
        if t:
            target_id, target_name = t.id, disp(t)
    if not target_id:
        return await reply(update, why_no_target(update, "Ответь на сообщение участника: «+реп» или напиши «+реп @юз»"))
    if target_id == giver.id:
        return await reply(update, "Себе репутацию ставить нельзя 😉")
    d = today()
    if db.execute("SELECT 1 FROM rep_log WHERE day=? AND giver=? AND target=?",
                  (d, giver.id, target_id)).fetchone():
        return await reply(update, "Этому участнику ты уже ставил +реп сегодня.")
    given_today = db.execute("SELECT COUNT(*) FROM rep_log WHERE day=? AND giver=?",
                             (d, giver.id)).fetchone()[0]
    if given_today >= 5:
        return await reply(update, "Лимит: 5 репутаций в день.")
    db.execute("INSERT INTO rep_log VALUES(?,?,?)", (d, giver.id, target_id))
    db.execute("UPDATE users SET rep=rep+1 WHERE user_id=?", (target_id,))
    db.execute("UPDATE users SET rep_given=rep_given+1 WHERE user_id=?", (giver.id,))
    db.commit()
    bump(giver.id, "repgiven")
    rep = urow(target_id)["rep"]
    await reply(update, f"✨ {link(giver.id, disp(giver))} повысил репутацию "
                        f"{link(target_id, target_name)} (теперь {rep})")
    await check_quests(context.bot, giver.id)


async def handle_rp(update, context, key, dot=False):
    me = update.effective_user
    if dot:
        pr = pair_of(me.id)
        if not pr:
            return await reply(update, "У тебя пока нет пары 💔 Сначала: «предложить отношения @юз». "
                                       f"А обычное «{key} @юз» работает без пары.")
        pid = partner_of(pr, me.id)
        prow = urow(pid)
        other = SimpleNamespace(id=pid, username=(prow["username"] if prow else None), is_bot=False,
                                full_name=(prow["name"] if prow else str(pid)))
    else:
        other = target_user(update)
    if not other:
        return await reply(update, f"Напиши «{key} @юзернейм» или ответь словом «{key}» на сообщение человека")
    if other.id == me.id:
        return await reply(update, "Давай лучше кого-нибудь другого 🙂")
    if offended_block(me.id, other.id):
        return await reply(update, "🙁 Ваша половинка обижена на вас, все действия недоступны.")
    tpl, emoji = RP[key]
    text = (emoji + " " + tpl.format(a=link(me.id, disp(me)), b=link(other.id, disp(other)))).replace("(а)", ea(me.id))
    actions = [key]
    gain = REL_GAIN.get(key) if dot else None
    if gain:
        res = rel_add(me.id, other.id, gain, key)
        if res is not None:
            add, sparks = res
            text += (f"\n🔥 +{add} искр (всего {sparks})" if add
                     else "\n🔥 На сегодня лимит искр от действий набран")
            if key in REL_PIC:
                actions.insert(0, "отн:" + REL_PIC[key])
    await send_with_pic(context.bot, update.effective_chat.id, text, actions,
                        reply_to=update.effective_message.message_id, api_cat=RP_API.get(key))
