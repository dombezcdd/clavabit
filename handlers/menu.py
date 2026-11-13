# -*- coding: utf-8 -*-
"""Меню в личке бота и ссылка на статью с командами."""

import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from config import HTML, NOPREV
from content.texts import ADMIN_HELP, HELP_TEXT, START_TEXT
from core.helpers import reply
from core.logger import log
from core.ranks import need
from core.utils import esc
from database.state import state_get
from services.telegraph import telegraph_sync


# ============================ МЕНЮ В ЛИЧКЕ БОТА (кнопки внизу) ============================
MENU_BTNS = ["📋 Команды", "🎮 Мини-игры", "💞 Отношения", "💼 Работа и монеты", "🛠 Для админов", "ℹ️ О боте"]


SECTION_GAMES = ("🎮 <b>Мини-игры</b> (для всех, прямо в чате)\n"
                 "• «мини игры»: меню с кнопками\n"
                 "• «угадай число»: бот загадывает 1–100, все пишут числа\n"
                 "• «анаграмма»: собери слово из перемешанных букв\n"
                 "• «кто быстрее»: кто первым напишет слово\n"
                 "• «виселица»: угадывайте слово по буквам\n"
                 "• «топ игр»: рейтинг побед, «стоп игра»: остановить\n"
                 "🕹 «игры в приложении» или /play: Монополия, 2048, Сапёр, Змейка (без наград)\n"
                 "Ещё: /dice, /slots, /coin, «дуэль», викторина и квесты (/quests)")


SECTION_LOVE = ("💞 <b>Отношения и семья</b>\n"
                "«предложить отношения @юз» → кнопка «Да». Общий баланс пары это искры 🔥\n"
                "Для партнёра с точкой: «.поцеловать», «.обнять», «.взять за руку»; обычное «поцеловать @юз» без искр\n"
                "«свидание» (выбор места), «подарок партнёру», «моя пара», «список пар», «топ пар», «обида», «расстаться»\n"
                "💍 «предложить брак» → «принять брак», «семья», «развод», «свидетельство»\n"
                "В браке: «завести ребёнка», «дети», «семейный счёт», «в семью 100», «из семьи 100»\n"
                "🏠 «дом», 🐾 «купить питомца», «питомцы», «покормить питомца», «мойпол м/ж»")


SECTION_WORK = ("💼 <b>Работа и монеты</b>\n"
                "«найти работу», «работать» (под заданием кнопка мини-игры: чем лучше результат, тем выше оплата), «моя работа», «уволиться»\n"
                "Должность растёт со сменами: Стажёр → Специалист → Старший → Эксперт → Мастер\n"
                "🪙 «баланс», «магазин», «купить 1», «топ монет», «дуэли»")


def menu_kb():
    return ReplyKeyboardMarkup([[MENU_BTNS[0]], [MENU_BTNS[1], MENU_BTNS[2]], [MENU_BTNS[3], MENU_BTNS[4]],
                                [MENU_BTNS[5]]], resize_keyboard=True)


async def private_menu(update):
    """Личка с ботом: нажатия кнопок меню показывают разделы."""
    msg = update.effective_message
    key = re.sub(r"[^\w\s]", "", msg.text or "").strip().lower()
    sections = {"команды": HELP_TEXT, "мини игры": SECTION_GAMES, "мини-игры": SECTION_GAMES,
                "отношения": SECTION_LOVE, "работа и монеты": SECTION_WORK, "для админов": ADMIN_HELP,
                "о боте": START_TEXT}
    key = key.replace("миниигры", "мини игры")
    text = next((v for k, v in sections.items() if key == k or key.endswith(" " + k)), None)
    if text is HELP_TEXT and state_get("tgph_url"):
        await send_commands_link(update)
        return
    if text:
        await msg.reply_text(text, parse_mode=HTML, link_preview_options=NOPREV, reply_markup=menu_kb())
    else:
        await msg.reply_text("Выбери раздел кнопками внизу 👇", reply_markup=menu_kb())


async def send_commands_link(update, markup=None):
    """Ссылка на статью с командами (если статья есть), иначе обычный текст справки."""
    url = state_get("tgph_url")
    m = update.effective_message
    if not url:
        return False
    kb = [[InlineKeyboardButton("📖 Посмотреть команды", url=url)]]
    await m.reply_text(f"⚙️ <b>Полный список команд в нашей <a href=\"{url}\">статье</a></b>",
                       parse_mode=HTML, reply_markup=InlineKeyboardMarkup(kb) if not markup else markup)
    return True


@need("статья команд")
async def cmd_doc_update(update, context):
    try:
        url = await telegraph_sync(force=True)
        await reply(update, f"✅ Статья обновлена: {url}")
    except Exception as e:
        log.exception("telegraph")
        await reply(update, f"Не вышло опубликовать статью: {esc(repr(e)[:200])}")
