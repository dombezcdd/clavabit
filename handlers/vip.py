# -*- coding: utf-8 -*-
"""VIP: «звёздики», «вип», «купить вип», «купить вип @юз»."""

from config import ALLOWED, HTML
from core.helpers import reply, target_user
from core.utils import disp, link, touch, urow
from services.vip import (STAR, VIP_CASINO_BONUS, VIP_DAYS, VIP_PRICE, buy_vip, is_vip, stars_of, vip_left_text)


def vip_info(uid):
    st = (f"👑 <b>VIP активен</b>, осталось {vip_left_text(uid)}" if is_vip(uid) else "👑 VIP не активен")
    return (f"{STAR} <b>Звёздики:</b> {stars_of(uid)}\n{st}\n\n"
            f"<b>Что даёт VIP ({VIP_DAYS} дней, {VIP_PRICE} {STAR}):</b>\n"
            "• 👑 значок и золотая рамка профиля\n"
            "• +25% искр за действия в отношениях\n"
            "• 2 особых ежедневных VIP-квеста (по 60 опыта)\n"
            f"• пауза между сменами на 10% короче\n"
            f"• бонус фишек в казино {VIP_CASINO_BONUS} вместо 500\n\n"
            "Купить: «купить вип», подарить: «купить вип @юз» или ответом на сообщение.\n"
            "Пополнить звёздики: «пополнить» (оплата Telegram Stars).")


async def handle_vip_text(update, context, low, text):
    if update.effective_chat.id not in ALLOWED:
        return False
    w = low.split()
    if not w:
        return False
    if low in ("звёздики", "звездики", "мои звёздики", "мои звездики", "вип", "vip", "мой вип", "вип статус"):
        me = update.effective_user
        touch(me)
        await reply(update, vip_info(me.id))
        return True
    if w[0] == "купить" and len(w) >= 2 and w[1] in ("вип", "vip"):
        me = update.effective_user
        touch(me)
        t = target_user(update)
        tid = t.id if t else me.id
        ok, err = buy_vip(me.id, tid)
        if not ok:
            return await reply(update, err) or True
        who = "себе" if tid == me.id else f"для {link(tid, disp(t))}"
        await reply(update, f"👑 {link(me.id, disp(me))} купил(а) VIP {who} на {VIP_DAYS} дней за {VIP_PRICE} {STAR}!\n"
                            f"Осталось звёздиков: {stars_of(me.id)}")
        return True
    return False
