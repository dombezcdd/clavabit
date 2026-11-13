# -*- coding: utf-8 -*-
"""Project configuration. Keep secrets in environment variables, not in Git."""
import os
from datetime import timedelta, timezone
from telegram import LinkPreviewOptions
from telegram.constants import ParseMode

# ============================ НАСТРОЙКИ ============================
BASE = os.path.dirname(os.path.abspath(__file__))

TOKEN = ""                    # вставь токен от @BotFather ИЛИ положи его в файл token.txt рядом с bot.py
CHAT_ID = -1004318004202          # основной чат
TEST_CHAT_ID = -1002299660550                # id тестовой группы (0 = нет). Там бот тоже отвечает на команды
OWNER_USERNAME = "bloya"        # владелец (без @)
OWNER_ID = (os.environ.get("OWNER_ID") or "").strip()   # числовой id владельца (надёжнее имени), можно задать в переменных хостинга
CHANNEL = "@clubClaveka"
CHAT_TAG = "@clavekchat"

TZ_HOURS = 7                    # часовой пояс чата (7 = Новосибирск, 3 = Москва/Стамбул)
MIN_MSGS = 50                   # норма сообщений за день для награды
MIN_LETTERS = 4                 # минимум букв в сообщении
SPAM_SEC = 3                    # пауза между засчитанными сообщениями
MIN_REACTIONS = 3               # минимум реакций для «лучшего сообщения дня»
QUESTION_TIME = (10, 0)         # вопрос дня
QUIZ_TIME = (18, 0)             # викторина
SUMMARY_TIME = (23, 55)         # итоги дня
QUIZ_MINUTES = 60
PROMO_MIN_MIN, PROMO_MAX_MIN = 60, 120   # реклама/приглашения: одно сообщение раз в 1-2 часа (случайно)
QUIET_HOURS = (1, 8)            # ночью (с 1 до 8) реклама и напоминания молчат
QUEST_XP = 40
QUEST_ALL_BONUS_XP = 100
QUIZ_XP = 10
BANNER = "banner.jpg"           # необязательная картинка для итогов
RP_DIR = "rp"                   # необязательные картинки/гифки: rp/обнять.jpg, rp/ударить.gif ...
DB_FILE = "activity.db"
# ===================================================================

ALLOWED = {CHAT_ID} | ({TEST_CHAT_ID} if TEST_CHAT_ID else set())
TZ = timezone(timedelta(hours=TZ_HOURS))
FMT = "%Y-%m-%d"
NOPREV = LinkPreviewOptions(is_disabled=True)
HTML = ParseMode.HTML

# ---- экономика (меняй числа здесь) ----
MSG_COINS_EVERY = 30       # 1 монета за каждые N сообщений
SHOP_PRICE_MULT = 3        # множитель цен в магазине подарков (цена из «добавить товар» умножается)
JOB_PAY_MULT = 0.4         # множитель зарплаты на работах (меньше = монет меньше)
