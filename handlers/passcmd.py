# -*- coding: utf-8 -*-
"""«пасс»: картинка прогресса сезона и кнопка «Забрать награды»."""

from telegram import InlineKeyboardButton as B, InlineKeyboardMarkup

from config import ALLOWED, HTML
from core.helpers import reply
from core.utils import disp, esc, touch, urow
from handlers.finance import _send_photo
from services.battlepass import LEVELS, claim_all, pass_card, reward, state


def _kb(uid):
    pts, lvl, got = state(uid)
    n = sum(1 for i in range(1, lvl + 1) if i not in got)
    return InlineKeyboardMarkup([[B(f"🎁 Забрать награды ({n})" if n else "🎁 Наград пока нет", callback_data=f"ps:claim:{uid}")]])


def _cap(uid):
    pts, lvl, got = state(uid)
    nxt = f"Следующая награда (ур. {lvl + 1}): {reward(lvl + 1)[2]}" if lvl < LEVELS else "Все награды сезона открыты"
    return f"🎟 <b>Пасс сезона</b>\nУровень {lvl}/{LEVELS}, очков {pts}\n{nxt}"


async def handle_pass_text(update, context, low, text):
    if update.effective_chat.id not in ALLOWED or low not in ("пасс", "мой пасс", "pass", "батлпасс"):
        return False
    me = update.effective_user
    touch(me)
    await _send_photo(update.effective_message, pass_card(disp(me), me.id), _cap(me.id), reply_markup=_kb(me.id))
    return True


async def handle_ach_text(update, context, low, text):
    if update.effective_chat.id not in ALLOWED or low not in ("достижения", "ачивки", "мои достижения", "мои ачивки"):
        return False
    import asyncio
    from services.achievements import check, showcase, have, ACHS
    me = update.effective_user
    touch(me)
    check(me.id, True)
    buf = await asyncio.to_thread(showcase, disp(me), me.id)
    await _send_photo(update.effective_message, buf, f"🏅 Достижения: {len(have(me.id))} из {len(ACHS)}. Новые открываются сами")
    return True


async def announce_ach(bot, uid, chat_id):
    """Сообщение о новых достижениях (вызывается после игровых действий)."""
    from services.achievements import ACH_XP, check
    new = check(uid)
    if not new or not chat_id:
        return
    from services.xp import give_xp
    give_xp(uid, ACH_XP * len(new))
    r = urow(uid)
    lines = "\n".join(f"{ic} <b>{name}</b>" for _, ic, name in new)
    await bot.send_message(chat_id, f"🏅 {esc(r['name'] if r else '')}: новое достижение!\n{lines}\n+{ACH_XP * len(new)} опыта", parse_mode=HTML)


async def on_pass_btn(update, context):
    q = update.callback_query
    p = (q.data or "").split(":")
    if len(p) < 3 or not p[2].isdigit():
        return await q.answer()
    if q.from_user.id != int(p[2]):
        return await q.answer("Это пасс другого игрока. Свой: «пасс»", show_alert=True)
    got = claim_all(q.from_user.id)
    if not got:
        return await q.answer("Пока нет новых наград. Выполняй квесты дня!", show_alert=True)
    await q.answer("Награды получены!")
    await context.bot.send_message(q.message.chat_id, f"🎁 {esc(disp(q.from_user))} забрал(а) награды пасса:\n" + "\n".join(got),
                                   parse_mode=HTML)
    try:
        await q.edit_message_caption(caption=_cap(q.from_user.id), parse_mode=HTML, reply_markup=_kb(q.from_user.id))
    except Exception:
        pass
