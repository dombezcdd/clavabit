# -*- coding: utf-8 -*-
"""Бои питомцев: «бой питомцев» ответом на сообщение (или @ник), можно со ставкой: «бой питомцев 50»."""

import asyncio
import copy
import logging
import re
import time

from telegram import InlineKeyboardButton as B, InlineKeyboardMarkup, InputMediaPhoto

from config import ALLOWED, HTML
from core.antispam import cooldown
from core.helpers import reply, target_user
from core.utils import disp, esc, link, today, touch
from services import petbattle as pb
from services.casino import chips_add, chips_of
from services.jobs import my_pets

log = logging.getLogger("petbattle")
RE = re.compile(r"^(?:бой|битва|драка|дуэль)\s+питомцев(?:\s+(\d{1,4}))?(?:\s+@\w+)?$")
MAX_BET = 500
CH = {}          # (чат, id вызвавшего, id вызванного) -> {t, bet, msg}


def _kb(a, b, bet):
    return InlineKeyboardMarkup([[B("⚔ Принять бой", callback_data=f"pb:{a}:{b}:{bet}:acc"), B("✖ Отказаться", callback_data=f"pb:{a}:{b}:{bet}:no")]])


async def handle_petbattle_text(update, context, low, text):
    m = RE.match(low.strip())
    if not m or update.effective_chat.id not in ALLOWED:
        if low.strip() in ("рекорд питомцев", "мои бои", "бои питомцев"):
            if update.effective_chat.id not in ALLOWED:
                return False
            me = update.effective_user
            w, l = pb.record_of(me.id)
            await reply(update, f"🐾 <b>Бои питомцев</b> · {link(me.id, disp(me))}\nПобед: <b>{w}</b> · поражений: <b>{l}</b>\n"
                                f"Вызвать: ответь на сообщение словами «бой питомцев» (можно со ставкой: «бой питомцев 50»).")
            return True
        return False
    me = update.effective_user
    touch(me)
    foe = target_user(update)
    if not foe or foe.is_bot or foe.id == me.id:
        await reply(update, "🐾 Ответь на сообщение того, кого вызываешь: «бой питомцев» или «бой питомцев 50» (со ставкой).")
        return True
    bet = int(m.group(1) or 0)
    if bet > MAX_BET:
        await reply(update, f"Ставка не больше {MAX_BET} 💵")
        return True
    day = today()
    fa, fb = pb.best_pet(my_pets(me.id), day), pb.best_pet(my_pets(foe.id), day)
    if not fa:
        await reply(update, "У тебя нет питомца для боя. Купить: «купить питомца»")
        return True
    if not fb:
        await reply(update, f"У {link(foe.id, disp(foe))} нет питомца, драться не с кем 🐾")
        return True
    if pb.fights_today(me.id, day) >= pb.DAILY_LIMIT:
        await reply(update, f"Сегодня уже {pb.DAILY_LIMIT} боёв, питомцу нужен отдых. Завтра снова")
        return True
    if bet and chips_of(me.id) < bet:
        await reply(update, f"Для ставки нужно {bet} 💵, у тебя {chips_of(me.id)}")
        return True
    if not cooldown(("pbc", me.id), 60):
        await reply(update, "Подожди минуту перед новым вызовом")
        return True
    chat = update.effective_chat.id
    txt = (f"⚔ {link(me.id, disp(me))} вызывает {link(foe.id, disp(foe))} на бой питомцев!\n"
           f"{esc(fa['name'])} ({fa['kind']}, ур. {fa['lvl']}) против {esc(fb['name'])} ({fb['kind']}, ур. {fb['lvl']})\n"
           + (f"💰 Ставка: <b>{bet}</b> 💵 с каждого (славБакс)\n" if bet else "🏆 Победитель получает приз от бота\n") + "У тебя 3 минуты, чтобы принять.")
    try:
        buf = await asyncio.to_thread(pb.battle_card, fa, fb, fa["hp"], fb["hp"], (disp(me), disp(foe)), [f"{fa['name']} против {fb['name']}"], None, None, "ВЫЗОВ НА БОЙ", bet)
        await update.effective_message.reply_photo(buf, caption=txt, parse_mode=HTML, reply_markup=_kb(me.id, foe.id, bet))
    except Exception as e:
        log.warning("pb challenge photo: %r", e)
        await reply(update, txt, reply_markup=_kb(me.id, foe.id, bet))
    CH[(chat, me.id, foe.id)] = {"t": time.time(), "bet": bet}
    return True


async def on_pb_btn(update, context):
    q = update.callback_query
    p = (q.data or "").split(":")
    if len(p) != 5 or q.message.chat_id not in ALLOWED:
        return await q.answer()
    a, b, bet, act = int(p[1]), int(p[2]), int(p[3]), p[4]
    me = q.from_user
    chat = q.message.chat_id
    key = (chat, a, b)
    ch = CH.get(key)
    if me.id == a and act == "no":
        CH.pop(key, None)
        await q.answer("Вызов отменён")
        try:
            await q.message.edit_text("🐾 Вызов отменён.")
        except Exception:
            pass
        return
    if me.id != b:
        return await q.answer("Этот вызов не для тебя", show_alert=True)
    if not ch or time.time() - ch["t"] > 180:
        CH.pop(key, None)
        try:
            await q.message.edit_text("🐾 Время вызова вышло.")
        except Exception:
            pass
        return await q.answer("Вызов устарел")
    if act == "no":
        CH.pop(key, None)
        await q.answer()
        try:
            await q.message.edit_text(f"🐾 {link(b, disp(me))} отказался от боя.", parse_mode=HTML)
        except Exception:
            pass
        return
    touch(me)
    day = today()
    fa, fb = pb.best_pet(my_pets(a), day), pb.best_pet(my_pets(b), day)
    if not fa or not fb:
        CH.pop(key, None)
        return await q.answer("У одного из бойцов больше нет питомца", show_alert=True)
    if bet and (chips_of(a) < bet or chips_of(b) < bet):
        return await q.answer(f"На ставку нужно {bet} 💵 у обоих", show_alert=True)
    if pb.fights_today(b, day) >= pb.DAILY_LIMIT:
        return await q.answer("Твой питомец устал на сегодня", show_alert=True)
    CH.pop(key, None)
    await q.answer("Бой начинается! ⚔")
    from services.relations import uname
    na, nb = uname(a), disp(me)
    if bet:
        chips_add(a, -bet); chips_add(b, -bet)
    sa, sb = copy.deepcopy(fa), copy.deepcopy(fb)
    frames, win = pb.simulate(sa, sb)
    # кадры: старт + до 3 промежуточных + финал
    idx = sorted({0, len(frames) // 3, 2 * len(frames) // 3, len(frames) - 1})
    msg = q.message
    first = True
    for n, i in enumerate(idx):
        ha, hb, ev, hit = frames[i]
        last = n == len(idx) - 1
        evs = ev if not last else ev + [f"Победил {(fa if win == 'a' else fb)['name']}!"]
        buf = pb.battle_card(fa, fb, ha, hb, (na, nb), evs, hit=hit, winner=win if last else None, title="ПОБЕДА" if last else "БОЙ ПИТОМЦЕВ", bet=bet)
        cap = "⚔ <b>Бой питомцев</b>\n" + (f"{link(a, na)} против {link(b, nb)}" if not last else "")
        if last:
            wu, lu = (a, b) if win == "a" else (b, a)
            wn, ln = (na, nb) if win == "a" else (nb, na)
            wp = (fa if win == "a" else fb)
            prize = bet * 2 if bet else 25
            chips_add(wu, prize)
            pb.record(wu, True, day); pb.record(lu, False, day)
            cap = (f"🏆 {link(wu, wn)} побеждает! {esc(wp['name'])} молодец.\n"
                   f"Приз: <b>+{prize}</b> 💵" + (f"\n{link(lu, ln)} теряет ставку {bet}" if bet else ""))
        try:
            await msg.edit_media(InputMediaPhoto(buf, caption=cap, parse_mode=HTML))
        except Exception as e:
            log.info("pb edit: %r", e)
            try:
                if first:
                    await msg.delete()
                    msg = await context.bot.send_photo(chat, buf, caption=cap, parse_mode=HTML)
                else:
                    buf.seek(0)
                    await msg.edit_media(InputMediaPhoto(buf, caption=cap, parse_mode=HTML))
            except Exception as e2:
                log.warning("pb send: %r", e2)
        first = False
        if not last:
            await asyncio.sleep(2.2)
