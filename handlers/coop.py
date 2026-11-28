# -*- coding: utf-8 -*-
"""Условия сотрудничества и подарков: «сотрудничество», кнопка «Подать заявку» шлёт заявку владельцу в личку."""

import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import ALLOWED, OWNER_ID, OWNER_USERNAME
from core.helpers import reply
from core.logger import log
from core.utils import disp, esc, link, touch
from database.state import state_get, state_set
from services.finance import GIFT_PAUSE_H, GIFT_VAT, SALARY_TAX

ARTICLE = "https://telegra.ph/sotrudnichestvo-07-20-4"
STARS_PER_INVITED = 0.7
WORDS = {"сотрудничество", "условия сотрудничества", "партнёрство", "партнерство", "условия подарков", "условия"}


def coop_text():
    return (
        "🤝 <b>Сотрудничество</b>\n"
        "Зарабатывай на видео и привлечении аудитории. Связь: @swagslave\n\n"
        "💵 <b>Выплата за просмотры</b>\n"
        "• 1000 просмотров = 1$\n"
        "• от 0.5$ до 5$ за видео (засчитываются 1000–10 000 просмотров)\n"
        "• вывод: ⭐ Telegram Stars, USDT или TON\n\n"
        "💬 <b>Бонус за комментарии</b>\n"
        "50 комментариев под видео в TikTok = 15 ⭐ (от 50 до 100). Следи, чтобы комментарии не удаляли.\n\n"
        "✅ <b>Правила видео</b>\n"
        "• хорошее качество, сильная идея и сценарий\n"
        "• правильный юзернейм в видео\n"
        "• аудитория должна хотеть перейти\n\n"
        "❌ <b>Откажем, если</b>\n"
        "накрутка, украденный контент, неверный юзернейм, видео не по условиям\n\n"
        "📝 <b>Как получить выплату</b>\n"
        "1. Заявку можно подать не раньше чем через 5 дней после публикации.\n"
        "2. Пришли юзернеймы приглашённых, скриншоты переходов и доказательство, что ссылку отправил именно ты.\n"
        "3. Сделай это в течение 1–3 дней после выполнения условий. Проверка может занять время.\n\n"
        "Пожалуйста, не пиши слишком часто: я отвечу, как только смогу.")


def gifts_text():
    return (
        "🎁 <b>Подарки из магазина</b>\n"
        "• приз выдаёт владелец вручную после покупки\n"
        f"• после покупки подарка следующий можно купить через {GIFT_PAUSE_H} ч, и все эти {GIFT_PAUSE_H} ч "
        f"налог на зарплату {int((SALARY_TAX + GIFT_VAT) * 100)}% (обычный {int(SALARY_TAX * 100)}% + НДС {int(GIFT_VAT * 100)}%)\n"
        "• купленный подарок можно продать другому игроку: «подарки», «продать 5 300», «рынок»")


def coop_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("💬 Написать @swagslave", url="https://t.me/swagslave")],
                                 [InlineKeyboardButton("✍️ Подать заявку", callback_data="coop:apply")]])


async def handle_coop_text(update, context, low, text):
    if update.effective_chat.id not in ALLOWED or low not in WORDS:
        return False
    sent = False
    try:
        from handlers.finance import _send_photo
        from services.coop_card import coop_card
        if len(coop_text()) <= 1024:
            await _send_photo(update.effective_message, coop_card, coop_text(), reply_markup=coop_kb(), key="coop_cover")
            sent = True
    except Exception:
        log.exception("coop cover")
    if not sent:
        await reply(update, coop_text(), reply_markup=coop_kb())
    await reply(update, gifts_text())
    return True


def _owner_id():
    if OWNER_ID:
        return int(OWNER_ID)
    oid = state_get("owner_id")
    return int(oid) if oid else None


async def on_coop_btn(update, context):
    q = update.callback_query
    if q.data != "coop:apply":
        return await q.answer()
    u = q.from_user
    touch(u)
    key = f"coop_{u.id}"
    last = float(state_get(key) or 0)
    if time.time() - last < 86400:
        return await q.answer("Заявка уже отправлена. Новую можно через сутки", show_alert=True)
    oid = _owner_id()
    if not oid:
        return await q.answer(f"Напиши владельцу @{OWNER_USERNAME} лично", show_alert=True)
    try:
        await context.bot.send_message(
            oid, f"📨 <b>Заявка на сотрудничество</b>\nОт: {link(u.id, disp(u))}"
                 + (f" (@{esc(u.username)})" if u.username else "") + f"\nID: <code>{u.id}</code>\n"
                 "Он(а) прочитал(а) условия. Свяжись с ним, чтобы получить ссылку на видео и доказательства.",
            parse_mode="HTML")
    except Exception as e:
        log.warning("coop apply: %r", e)
        return await q.answer(f"Не получилось отправить. Напиши владельцу @{OWNER_USERNAME}", show_alert=True)
    state_set(key, time.time())
    await q.answer("Заявка отправлена владельцу ✅", show_alert=True)
