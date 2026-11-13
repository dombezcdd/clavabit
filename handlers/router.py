# -*- coding: utf-8 -*-
"""Маршрутизация текстовых сообщений: слова-команды и алиасы."""

import re
import time

from telegram import Update
from telegram.ext import ContextTypes

from config import ALLOWED, CHAT_ID, SPAM_SEC
from content.data import RP
from core.antispam import is_meaningful, last_texts, last_ts
from core.helpers import reply, target_user
from core.ranks import has_rank
from core.utils import is_owner, norm, touch, urow
from database.db import db
from handlers.basic import cmd_help
from handlers.chat_admin import cmd_admin_log, cmd_rules, cmd_set_rules, cmd_set_welcome, cmd_weekstat
from handlers.duel import cmd_duel
from handlers.economy import cmd_balance, cmd_bonus, cmd_buy, cmd_coins_give, cmd_duels, cmd_item_add, cmd_item_del, cmd_order_done, cmd_orders, cmd_shop, cmd_topcoins
from handlers.jobs_admin import cmd_job_add, cmd_job_del, cmd_jobs_list
from handlers.life import handle_life
from handlers.media_admin import cmd_pic_add, cmd_pic_clear, cmd_pic_list
from handlers.menu import cmd_doc_update, private_menu
from handlers.minigames import cmd_coin, cmd_dice, cmd_slots
from handlers.moderation import cmd_admin, cmd_award, cmd_ban, cmd_mute, cmd_mutelist, cmd_question, cmd_quiz, cmd_stat, cmd_tag, cmd_topwords, cmd_unban, cmd_unmute, cmd_untag
from handlers.nft import NFT_RE, handle_nft
from handlers.profiles import cmd_month, cmd_quests, cmd_quiztop, cmd_top, cmd_week
from handlers.ranks_admin import cmd_access, cmd_admins, cmd_demote, cmd_promote
from handlers.relations import handle_relation
from handlers.reports import cmd_report
from handlers.rp import REP_RE, handle_rep, handle_rp
from services.profile import build_profile
from services.quiz import try_quiz
from services.relations import rel_add
from services.xp import add_counted, check_quests, count_words


# Команды обычными словами (сообщение целиком, без слеша)
USER_ALIASES = {
    "помощь": cmd_help, "команды": cmd_help, "хелп": cmd_help,
    "топ": cmd_top, "топ дня": cmd_top,
    "неделя": cmd_week, "топ недели": cmd_week,
    "месяц": cmd_month, "топ месяца": cmd_month,
    "квесты": cmd_quests, "задания": cmd_quests,
    "рейтинг викторины": cmd_quiztop, "топ викторины": cmd_quiztop,
    "дуэль": cmd_duel, "кости": cmd_dice, "слоты": cmd_slots,
    "монетка": cmd_coin, "монета": cmd_coin,
    "баланс": cmd_balance, "кошелек": cmd_balance, "кошелёк": cmd_balance,
    "магазин": cmd_shop, "шоп": cmd_shop, "топ монет": cmd_topcoins,
    "дуэли": cmd_duels, "бонус": cmd_bonus, "правила": cmd_rules, "репорт": cmd_report, "жалоба": cmd_report,
}


# слово -> (команда, ключ доступа, сколько слов можно дописать)
ADMIN_ALIASES = {
    "админка": (cmd_admin, "админка", 0), "админ панель": (cmd_admin, "админка", 0),
    "админы": (cmd_admins, "админы", 1),
    "мут": (cmd_mute, "мут", 15), "размут": (cmd_unmute, "размут", 1),
    "список мута": (cmd_mutelist, "список мута", 0), "муты": (cmd_mutelist, "список мута", 0),
    "бан": (cmd_ban, "бан", 8), "разбан": (cmd_unban, "разбан", 1),
    "тег": (cmd_tag, "тег", 5), "снять тег": (cmd_untag, "снять тег", 0),
    "статистика": (cmd_stat, "статистика", 0), "слова дня": (cmd_topwords, "слова дня", 0),
    "итоги": (cmd_award, "итоги", 0),
    "запустить вопрос": (cmd_question, "запустить вопрос", 0),
    "запустить викторину": (cmd_quiz, "запустить викторину", 0),
    "повысить": (cmd_promote, "повысить", 3), "разжаловать": (cmd_demote, "повысить", 2),
    "дк": (cmd_access, "дк", 6),
    "добавить картинку": (cmd_pic_add, "добавить картинку", 4),
    "список картинок": (cmd_pic_list, "список картинок", 0),
    "очистить картинки": (cmd_pic_clear, "очистить картинки", 4),
    "добавить товар": (cmd_item_add, "добавить товар", 12),
    "удалить товар": (cmd_item_del, "удалить товар", 1),
    "выдать монеты": (cmd_coins_give, "выдать монеты", 4),
    "заказы": (cmd_orders, "заказы", 0), "выдан": (cmd_order_done, "выдан", 1),
    "добавить работу": (cmd_job_add, "добавить работу", 8), "удалить работу": (cmd_job_del, "удалить работу", 1),
    "список работ": (cmd_jobs_list, "список работ", 0), "журнал": (cmd_admin_log, "журнал", 1),
    "установить приветствие": (cmd_set_welcome, "установить приветствие", 80),
    "установить правила": (cmd_set_rules, "установить правила", 200),
    "статистика недели": (cmd_weekstat, "статистика недели", 0),
    "обновить статью": (cmd_doc_update, "статья команд", 0),
}


def set_args(context, args):
    try:
        context.args = args
    except AttributeError:
        context._args = args


async def run_alias(update, context, low, text):
    clean = re.sub(r"[!.?,]+$", "", low).strip()
    fn = USER_ALIASES.get(clean)
    if fn:
        set_args(context, [])
        await fn(update, context)
        return True
    words = clean.split()
    orig = re.sub(r"[!.?,]+$", "", text.strip()).split()
    for n in (2, 1):
        key = " ".join(words[:n])
        item = ADMIN_ALIASES.get(key)
        if item and len(words) - n <= item[2]:
            if has_rank(update.effective_user, item[1]):
                set_args(context, orig[n:])
                await item[0](update, context)
                return True
            return False
    return False


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, user, chat = update.effective_message, update.effective_user, update.effective_chat
    if not msg or not user or user.is_bot or not msg.text:
        return
    if chat.type == "private":
        return await private_menu(update)
    if chat.id not in ALLOWED:
        return
    touch(user)
    is_owner(user)
    text = msg.text.strip()
    low = text.lower()

    if low.startswith("/анрег") or low.startswith("/рег"):
        val = 0 if low.startswith("/анрег") else 1
        db.execute("UPDATE users SET registered=? WHERE user_id=?", (val, user.id))
        db.commit()
        return await reply(update, "Ты вышел из созыва 🔕" if val == 0 else "Ты снова в созыве 🔔")

    nm = NFT_RE.search(text)
    if nm and (text.startswith("!") or low.startswith(("гиф", "gif", "нфт", "nft"))):
        return await handle_nft(update, context, text)

    m = REP_RE.match(low)
    if m:
        return await handle_rep(update, context, m)

    mb = re.match(r"купить\s+(\d+)$", low)
    if mb:
        set_args(context, [mb.group(1)])
        return await cmd_buy(update, context)
    first = low.split()[0] if low.split() else ""
    if first in ("репорт", "жалоба", "report") and len(low.split()) <= 12:
        set_args(context, text.split()[1:])
        return await cmd_report(update, context)

    cmd_low = re.sub(r"\s+@\w{4,32}\s*$", "", low).strip()
    if cmd_low.startswith(".") and cmd_low[1:].strip() in RP:
        return await handle_rp(update, context, cmd_low[1:].strip(), dot=True)
    if cmd_low in RP:
        return await handle_rp(update, context, cmd_low)

    if await handle_life(update, context, cmd_low, text):
        return

    if await handle_relation(update, context, cmd_low):
        return

    if await run_alias(update, context, low, text):
        return

    if cmd_low in ("профиль", "мой профиль"):
        u = target_user(update) or user
        touch(u)
        return await reply(update, await build_profile(context.bot, urow(u.id)))

    await try_quiz(update, text)

    if chat.id != CHAT_ID:
        return          # в тестовом чате активность, опыт и монеты не начисляются

    if getattr(msg, "forward_origin", None) or getattr(msg, "forward_date", None):
        return
    if not is_meaningful(text):
        return
    t = time.time()
    if t - last_ts.get(user.id, 0) < SPAM_SEC:
        return
    recent = last_texts.setdefault(user.id, [])
    key = norm(text)
    if key in recent:
        return
    recent.append(key)
    del recent[:-5]
    last_ts[user.id] = t

    is_reply = bool(msg.reply_to_message and msg.reply_to_message.from_user
                    and msg.reply_to_message.from_user.id != user.id
                    and not msg.reply_to_message.from_user.is_bot)
    events = add_counted(user.id, msg.message_id, is_reply)
    if is_reply:
        rel_add(user.id, msg.reply_to_message.from_user.id, 1)
    count_words(text)
    if events:
        await reply(update, "\n".join(events))
    await check_quests(context.bot, user.id)
