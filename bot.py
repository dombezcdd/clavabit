# -*- coding: utf-8 -*-
"""
Бот активности для чата @clavekchat. Владелец: @bloya
Запуск: py -3.14 bot.py   (или start.bat)
Нужно: py -3.14 -m pip install "python-telegram-bot>=22"
"""
import asyncio
import html
import json
import logging
import os
import random
import re
import sqlite3
import sys
import time
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

from telegram import (ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup,
                      LinkPreviewOptions, ReplyParameters, Update)
from telegram.constants import ParseMode
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler, ContextTypes,
                          MessageHandler, filters)

try:
    from telegram.ext import MessageReactionHandler
except ImportError:  # старая версия библиотеки
    MessageReactionHandler = None

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ============================ НАСТРОЙКИ ============================
BASE = os.path.dirname(os.path.abspath(__file__))

TOKEN = ""                    # вставь токен от @BotFather ИЛИ положи его в файл token.txt рядом с bot.py
CHAT_ID = -1004318004202          # основной чат
TEST_CHAT_ID = 0                # id тестовой группы (0 = нет). Там бот тоже отвечает на команды
OWNER_USERNAME = "bloya"        # владелец (без @)
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

START_TEXT = (
    f"owner: @{OWNER_USERNAME}\n"
    "бот находится в БЕТА-тесте\n(возможны баги)\n"
    f"(БОТ работает ИСКЛЮЧИТЕЛЬНО в чате: {CHAT_TAG})\n\n"
    "Привет! активничай в чате и получай награды 🎁\n\n"
    f"поддержка/получить подарки: @{OWNER_USERNAME}"
)

HELP_TEXT = (
    "📋 <b>Команды</b>\n"
    "/me — профиль (ответом на сообщение — чужой профиль), также слово «профиль»\n"
    "/top, /week, /month — топы активности\n"
    "/quests — ежедневные квесты\n"
    "+реп — ответом на сообщение или «+реп @юз»\n"
    "/duel — дуэль профилей (ответом на сообщение или /duel @юз)\n"
    "!ссылка на NFT (t.me/nft/...) — карточка и анимация NFT; также «гиф ссылка»\n"
    "/dice — кости против другого (ответом), /slots, /coin\n"
    "/quiztop — рейтинг викторины\n"
    "РП (ответом на сообщение или «обнять @юз», с гифкой; без искр): обнять, обнять крепко, поцеловать, погладить, "
    "дать пять, пожать руку, взять за руку, пощекотать, ткнуть, покормить, помахать, "
    "похвалить, ударить, пнуть, укусить, отшлёпать, убить\n"
    "💞 Отношения (ответом или с @юз): «предложить отношения», потом кнопка «Да» "
    "или «принять» (2 минуты). Общий баланс пары это искры 🔥: пополняют точечные команды для партнёра «.поцеловать», «.обнять», «.взять за руку» и т.д., «свидание», "
    "работа и покупка в профиле «моя пара», тратятся раз в сутки, на нуле пара распадается. "
    "Ещё: «список пар», «топ пар», «обида» (повтор снимает), «расстаться», «мойпол м» или «мойпол ж»\n\n"
    "🪙 Монеты: «баланс», «бонус» (раз в день), «магазин», «купить 1», «топ монет», «дуэли»\n"
    "💼 Работа: «найти работу», «работать» (мини-игра на смене), «моя работа», «уволиться»\n"
    "📜 «свидетельство»: свидетельство пары или брака\n"
    "🎮 «мини игры» (кнопки): угадай число, анаграмма, кто быстрее, виселица; «топ игр»\n"
    "🎁 «свидание» (выбор места), «подарок партнёру» или «подарить цветы», «правила» чата; в браке: "
    "«семейный счёт», «в семью 100», «из семьи 100»\n"
    "💍 Брак: «предложить встречаться» → через пару дней «предложить брак» (ответом на сообщение), "
    "«принять брак», «семья», «развод»; в браке «завести ребёнка», «дети», «назвать ребёнка Имя»\n"
    "🏠 «дом» (купить жильё, бонус к зарплате), 🐾 «купить питомца», «питомцы», «покормить питомца», "
    "«назвать питомца Имя»\n"
    "🚨 «репорт» (+причина) ответом на сообщение нарушителя — жалоба админам\n\n"
    "/анрег — выйти из созыва, /рег — вернуться\n\n"
    "💡 Можно писать словами без слеша (сообщение целиком): "
    "профиль, топ, неделя, месяц, квесты, дуэль, кости, слоты, монетка, помощь"
)

ADMIN_HELP = (
    "🛠 <b>Админ-панель</b> (по рангам 1–8, владелец — 8)\n"
    "мут 30 @юзернейм причина — или ответом: мут 30 причина (время: 30, 2ч, 1д)\n"
    "размут, бан, разбан — ответом или @юзернейм\n"
    "список мута — кто в муте, на сколько и почему\n"
    "тег Текст / снять тег — ответом на сообщение\n"
    "повысить 2 — выдать ранг (ответом или @юзернейм, 0 — снять), только 8 ранг\n"
    "разжаловать — снять ранг\n"
    "админы [ранг] — список админов\n"
    "добавить картинку обнять — ответом на гифку/картинку/видео (можно несколько на одно действие); "
    "для отношений: добавить картинку отн поцелуй\n"
    "список картинок, очистить картинки обнять\n"
    "дк мут 2 — с какого ранга доступна команда («дк» без цифры покажет все), только 8 ранг\n"
    "добавить товар Мишка 500 [кол-во], удалить товар 1, выдать монеты @юз 100, заказы, выдан 5\n"
    "добавить работу Грузчик 45 3 ур=2 (оплата, пауза в часах), удалить работу, список работ, журнал [N], "
    "статистика недели, установить приветствие Привет, {name}!, установить правила Текст\n"
    "статистика, слова дня, итоги, запустить вопрос, запустить викторину\n\n"
    "Должности: 1 Мл. модератор, 2 Старший модератор, 3 Главный модератор, 4 Стажер админ, "
    "5 Младший админ, 6 Старший админ, 7 Зам.Администрации, 8 Доверенное лицо\n\n"
    "Со слешем: /mute, /unmute, /ban, /unban, /tag, /untag, /mutelist, /promote, /demote, "
    "/access, /admins, /stat, /topwords, /award, /question, /quiz"
)

RANK_TITLES = [  # (с какого уровня, название)
    (0, "Простой участник"), (5, "Активный"), (15, "Свой человек"),
    (30, "Постоянный"), (50, "Эксперт чата"), (70, "Легенда чата"),
    (90, "Мастер"), (100, "Бог чата"),
]
OLD_TITLES = [  # (с какого дня, название)
    (0, "🍼 Новорождённый"), (7, "🌿 Освоился"), (30, "🏠 Старожил"),
    (90, "🎖 Ветеран"), (180, "🏛 Олд"), (365, "🗿 Легенда-олд"),
]
STREAK_MILESTONES = (3, 7, 14, 30, 60, 100)

QUESTIONS = [
    "Что смотрите / во что играете на этой неделе?",
    "Какой трек сейчас на повторе? 🎧",
    "Чай или кофе — и почему?",
    "Какой самый полезный совет вы получали в жизни?",
    "Если бы завтра был выходной на неделю, чем бы занялись?",
    "Какое приложение на телефоне вы используете больше всего?",
    "Какую суперсилу выбрали бы себе?",
    "Лучшая еда, которую вы ели за последний месяц?",
    "Утро или ночь — когда вы продуктивнее?",
    "В какую страну поехали бы прямо сейчас?",
    "Какая игра или фильм вас сильно удивили?",
    "Чему вы научились за последний год?",
]

QUIZ = [  # (вопрос, [допустимые ответы])
    ("Столица Австралии?", ["канберра"]),
    ("Самая большая планета Солнечной системы?", ["юпитер"]),
    ("Кто написал «Войну и мир»?", ["толстой", "лев толстой"]),
    ("Химический символ золота?", ["au"]),
    ("Самое глубокое озеро мира?", ["байкал"]),
    ("Валюта Японии?", ["иена", "йена"]),
    ("Сколько нот в музыкальной гамме?", ["7", "семь"]),
    ("Кто написал «Мастера и Маргариту»?", ["булгаков", "михаил булгаков"]),
    ("Самое большое млекопитающее?", ["синий кит", "кит"]),
    ("Сколько дней в високосном году?", ["366"]),
    ("Самый большой океан?", ["тихий", "тихий океан"]),
    ("Как называется самая высокая гора мира?", ["эверест", "джомолунгма"]),
    ("Каким газом мы дышим для жизни?", ["кислород"]),
    ("Сколько игроков одной команды на поле в футболе?", ["11", "одиннадцать"]),
    ("Кто написал «Преступление и наказание»?", ["достоевский", "федор достоевский"]),
    ("Сколько секунд в минуте?", ["60", "шестьдесят"]),
]

# РП-команды: слово -> (шаблон, эмодзи)
RP = {
    "обнять": ("{a} обнял(а) {b}", "🤗"),
    "обнять крепко": ("{a} крепко обнял(а) {b}", "🫂"),
    "ударить": ("{a} ударил(а) {b}", "👊"),
    "пнуть": ("{a} пнул(а) {b}", "🦶"),
    "погладить": ("{a} погладил(а) {b} по голове", "🫳"),
    "дать пять": ("{a} дал(а) пять {b}", "🙌"),
    "пожать руку": ("{a} пожал(а) руку {b}", "🤝"),
    "укусить": ("{a} укусил(а) {b}", "😬"),
    "отшлёпать": ("{a} отшлёпал(а) {b}", "🍑"),
    "похвалить": ("{a} похвалил(а) {b}", "👏"),
    "поцеловать": ("{a} поцеловал(а) {b}", "😘"),
    "пощекотать": ("{a} пощекотал(а) {b}", "🤭"),
    "ткнуть": ("{a} ткнул(а) {b}", "👉"),
    "покормить": ("{a} покормил(а) {b}", "🍙"),
    "помахать": ("{a} помахал(а) {b}", "👋"),
    "взять за руку": ("{a} взял(а) за руку {b}", "🤝"),
    "убить": ("{a} убил(а) {b}", "💀"),
}
# слово -> категория гифок на nekos.best (если у тебя нет своей картинки в папке rp)
RP_API = {
    "обнять": "hug", "обнять крепко": "cuddle", "ударить": "punch", "пнуть": "kick",
    "погладить": "pat", "дать пять": "highfive", "пожать руку": "handshake",
    "укусить": "bite", "отшлёпать": "slap", "похвалить": "thumbsup",
    "поцеловать": "kiss", "пощекотать": "tickle", "ткнуть": "poke",
    "покормить": "feed", "помахать": "wave", "взять за руку": "handhold",
    "убить": "shoot",
}

KEYBOARD_ROWS = ["йцукенгшщзхъ", "фывапролджэ", "ячсмитьбю",
                 "qwertyuiop", "asdfghjkl", "zxcvbnm"]
STOPWORDS = set("это как так что чтобы когда если или тоже только очень есть "
                "было будет просто вообще потом тогда надо можно пока ещё уже "
                "который которые этого этот этой этих тебя меня тебе мне нас "
                "вас вам нам себя свой свои своё всё все всех".split())

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s",
                    level=logging.WARNING)
log = logging.getLogger("bot")

# ============================ БАЗА ДАННЫХ ============================
DATA_DIR = os.environ.get("DATA_DIR", BASE)   # на хостинге можно указать папку с постоянным диском
os.makedirs(DATA_DIR, exist_ok=True)
db = sqlite3.connect(os.path.join(DATA_DIR, DB_FILE), check_same_thread=False)
db.row_factory = sqlite3.Row
db.executescript("""
CREATE TABLE IF NOT EXISTS users(
  user_id INTEGER PRIMARY KEY, name TEXT, username TEXT DEFAULT '',
  total INTEGER DEFAULT 0, xp INTEGER DEFAULT 0,
  streak INTEGER DEFAULT 0, best_streak INTEGER DEFAULT 0, last_day TEXT,
  first_seen REAL, last_seen REAL,
  quiz_pts INTEGER DEFAULT 0, game_pts INTEGER DEFAULT 0, quest_pts INTEGER DEFAULT 0,
  rep INTEGER DEFAULT 0, rep_given INTEGER DEFAULT 0,
  tag TEXT DEFAULT '', registered INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS daily(
  day TEXT, user_id INTEGER, cnt INTEGER DEFAULT 0, replies INTEGER DEFAULT 0,
  plays INTEGER DEFAULT 0, repgiven INTEGER DEFAULT 0,
  PRIMARY KEY(day, user_id));
CREATE TABLE IF NOT EXISTS msgs(
  message_id INTEGER PRIMARY KEY, user_id INTEGER, day TEXT, reactions INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS quest_done(
  day TEXT, user_id INTEGER, qid TEXT, PRIMARY KEY(day, user_id, qid));
CREATE TABLE IF NOT EXISTS rep_log(
  day TEXT, giver INTEGER, target INTEGER, PRIMARY KEY(day, giver, target));
CREATE TABLE IF NOT EXISTS words(
  day TEXT, word TEXT, cnt INTEGER DEFAULT 0, PRIMARY KEY(day, word));
CREATE TABLE IF NOT EXISTS mutes(
  user_id INTEGER PRIMARY KEY, name TEXT, until REAL, reason TEXT,
  by_name TEXT, created REAL);
CREATE TABLE IF NOT EXISTS cmd_access(cmd TEXT PRIMARY KEY, rank INTEGER);
CREATE TABLE IF NOT EXISTS rp_media(
  id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT, kind TEXT, file_id TEXT,
  file_unique TEXT, added_by TEXT, created REAL);
CREATE TABLE IF NOT EXISTS pairs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, a INTEGER, b INTEGER, love INTEGER DEFAULT 30,
  since REAL, last_action REAL, gain_day TEXT, gain INTEGER DEFAULT 0, date_day TEXT);
CREATE TABLE IF NOT EXISTS proposals(
  to_id INTEGER PRIMARY KEY, from_id INTEGER, created REAL, msg_id INTEGER);
CREATE TABLE IF NOT EXISTS kids(
  id INTEGER PRIMARY KEY AUTOINCREMENT, pair_id INTEGER, name TEXT, gender TEXT, born REAL);
CREATE TABLE IF NOT EXISTS spark_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, pair_id INTEGER, delta INTEGER, reason TEXT, who TEXT,
  ts REAL, bal INTEGER);
CREATE TABLE IF NOT EXISTS job_tasks(
  user_id INTEGER PRIMARY KEY, job TEXT, kind TEXT, answer TEXT, target_id INTEGER,
  created REAL, expires REAL);
CREATE TABLE IF NOT EXISTS marry_proposals(
  to_id INTEGER PRIMARY KEY, from_id INTEGER, created REAL);
CREATE TABLE IF NOT EXISTS pets(
  id INTEGER PRIMARY KEY AUTOINCREMENT, owner INTEGER, kind TEXT, name TEXT, fed_day TEXT, bought REAL);
CREATE TABLE IF NOT EXISTS shop_items(
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, price INTEGER, stock INTEGER DEFAULT -1,
  active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS orders(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT, item TEXT, price INTEGER,
  created REAL, status TEXT);
CREATE TABLE IF NOT EXISTS reports(
  id INTEGER PRIMARY KEY AUTOINCREMENT, target_id INTEGER, target_name TEXT, msg_id INTEGER,
  reporter TEXT, reason TEXT, created REAL, status TEXT);
""")
for _col in ("arank INTEGER DEFAULT 0", "coins INTEGER DEFAULT 0", "duel_w INTEGER DEFAULT 0",
             "duel_l INTEGER DEFAULT 0", "bonus_day TEXT DEFAULT ''",
             "job TEXT DEFAULT ''", "job_shifts INTEGER DEFAULT 0", "last_work REAL DEFAULT 0",
             "house TEXT DEFAULT ''", "gender TEXT DEFAULT ''"):
    try:
        db.execute("ALTER TABLE users ADD COLUMN " + _col)
    except sqlite3.OperationalError:
        pass
for _col in ("married_at REAL DEFAULT 0", "anniv_day TEXT DEFAULT ''", "actions INTEGER DEFAULT 0",
             "offended INTEGER DEFAULT 0"):
    try:
        db.execute("ALTER TABLE pairs ADD COLUMN " + _col)
    except sqlite3.OperationalError:
        pass
db.commit()


def state_get(k, default=None):
    r = db.execute("SELECT value FROM state WHERE key=?", (k,)).fetchone()
    return r["value"] if r else default


def state_set(k, v):
    db.execute("INSERT INTO state(key,value) VALUES(?,?) "
               "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, str(v)))
    db.commit()


def state_del(k):
    db.execute("DELETE FROM state WHERE key=?", (k,))
    db.commit()


# ============================ УТИЛИТЫ ============================
def now():
    return datetime.now(TZ)


def today():
    return now().strftime(FMT)


def esc(s):
    return html.escape(str(s))


def link(uid, name):
    return f'<a href="tg://user?id={uid}">{esc(name)}</a>'


def disp(user):
    return (user.full_name or user.username or str(user.id)).strip()


def urow(uid):
    return db.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()


def touch(user):
    uid, name = user.id, disp(user)
    un = (user.username or "").lower()
    if urow(uid):
        db.execute("UPDATE users SET name=?, username=? WHERE user_id=?", (name, un, uid))
    else:
        db.execute("INSERT INTO users(user_id,name,username,first_seen) VALUES(?,?,?,?)",
                   (uid, name, un, time.time()))
    db.commit()


def find_by_username(un):
    r = db.execute("SELECT * FROM users WHERE username=?", (un.lstrip("@").lower(),)).fetchone()
    return r


def tagged(row):
    t = (row["tag"] or "").strip()
    name = esc(row["name"])
    return f"<b>{esc(t)}</b> {name}" if t else name


def is_owner(user):
    if not user:
        return False
    oid = state_get("owner_id")
    if oid and str(user.id) == oid:
        return True
    if (user.username or "").lower() == OWNER_USERNAME.lower():
        state_set("owner_id", user.id)
        return True
    return False


def owner_mention():
    oid = state_get("owner_id")
    return link(oid, "@" + OWNER_USERNAME) if oid else "@" + OWNER_USERNAME


def level_need(l):
    return int(15 * l ** 1.6)


def level_of(xp):
    lvl = 0
    for l in range(1, 101):
        if xp >= level_need(l):
            lvl = l
        else:
            break
    return lvl


def title_of(lvl):
    t = RANK_TITLES[0][1]
    for need, name in RANK_TITLES:
        if lvl >= need:
            t = name
    return t


def old_title(first_seen):
    days = int((time.time() - (first_seen or time.time())) // 86400)
    t = OLD_TITLES[0][1]
    for need, name in OLD_TITLES:
        if days >= need:
            t = name
    return t, days


def fmt_when(ts):
    if not ts:
        return "неизвестно"
    d = datetime.fromtimestamp(ts, TZ)
    n = now()
    if d.date() == n.date():
        return f"сегодня в {d:%H:%M}"
    if d.date() == (n - timedelta(days=1)).date():
        return f"вчера в {d:%H:%M}"
    return f"{d:%d.%m.%Y в %H:%M}"


def norm(s):
    s = s.lower().replace("ё", "е")
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# ============================ ЗАЩИТА ОТ НАКРУТКИ ============================
def is_meaningful(text):
    """Отсеивает набор букв вроде «ададад», «дадвдвд», «fafafa», «asdfgh»."""
    t = text.lower().replace("ё", "е")
    letters = re.sub(r"[^a-zа-я]", "", t)
    if len(letters) < MIN_LETTERS:
        return False
    if len(set(letters)) < 4:
        return False
    for p in (1, 2, 3):                       # повтор одного куска: адад, абвабв
        if letters == (letters[:p] * (len(letters) // p + 1))[:len(letters)]:
            return False
    for word in re.findall(r"[a-zа-я]+", t):
        if len(word) >= 7 and len(set(word)) / len(word) < 0.45:
            return False
    for row in KEYBOARD_ROWS:                 # «фывап», «asdfg», «ghjkl»
        for i in range(len(row) - 4):
            chunk = row[i:i + 5]
            if chunk in letters or chunk[::-1] in letters:
                return False
    if len(letters) >= 6:
        vowels = sum(letters.count(v) for v in "аеёиоуыэюяaeiouy")
        ratio = vowels / len(letters)
        if ratio < 0.15 or ratio > 0.75:
            return False
    return True


last_ts = {}
last_texts = {}
cooldowns = {}


def cooldown(key, sec):
    t = time.time()
    if t - cooldowns.get(key, 0) < sec:
        return False
    cooldowns[key] = t
    return True


# ============================ ОЧКИ, УРОВНИ, КВЕСТЫ ============================
def give_xp(uid, amount):
    u = urow(uid)
    if not u:
        return []
    old = level_of(u["xp"])
    xp = u["xp"] + amount
    new = level_of(xp)
    db.execute("UPDATE users SET xp=? WHERE user_id=?", (xp, uid))
    db.commit()
    ev = []
    if title_of(new) != title_of(old):
        ev.append(f"🎉 {link(uid, u['name'])} получает ранг <b>{esc(title_of(new))}</b> "
                  f"(уровень {new})!")
    elif new > old and new % 10 == 0:
        ev.append(f"⬆️ {link(uid, u['name'])} достиг {new} уровня!")
    return ev


def bump(uid, col, n=1):
    assert col in ("cnt", "replies", "plays", "repgiven")
    db.execute(f"INSERT INTO daily(day,user_id,{col}) VALUES(?,?,?) "
               f"ON CONFLICT(day,user_id) DO UPDATE SET {col}={col}+?",
               (today(), uid, n, n))
    db.commit()


def progress(uid, d=None):
    r = db.execute("SELECT * FROM daily WHERE day=? AND user_id=?", (d or today(), uid)).fetchone()
    if not r:
        return {"msgs": 0, "replies": 0, "plays": 0, "repgiven": 0}
    return {"msgs": r["cnt"], "replies": r["replies"], "plays": r["plays"],
            "repgiven": r["repgiven"]}


QUEST_TITLES = {
    "msgs": "Написать {n} сообщений",
    "replies": "Ответить на {n} сообщений",
    "plays": "Сыграть в мини-игры ({n} раз)",
    "repgiven": "Поставить +реп участнику",
}


def quests_for(d):
    rng = random.Random(d)
    types = rng.sample(list(QUEST_TITLES), 3)
    targets = {"msgs": [30, 50, 80], "replies": [5, 10, 15], "plays": [1, 2, 3], "repgiven": [1]}
    return [(t, rng.choice(targets[t])) for t in types]


async def check_quests(bot, uid):
    d = today()
    u = urow(uid)
    if not u:
        return
    prog = progress(uid, d)
    done = {r["qid"] for r in db.execute(
        "SELECT qid FROM quest_done WHERE day=? AND user_id=?", (d, uid))}
    qs = quests_for(d)
    out = []
    for qid, target in qs:
        if qid not in done and prog[qid] >= target:
            db.execute("INSERT OR IGNORE INTO quest_done VALUES(?,?,?)", (d, uid, qid))
            db.execute("UPDATE users SET quest_pts=quest_pts+1 WHERE user_id=?", (uid,))
            db.commit()
            done.add(qid)
            out.append(f"✅ {link(uid, u['name'])} выполнил квест: "
                       f"{QUEST_TITLES[qid].format(n=target)} (+{QUEST_XP} опыта)")
            out += give_xp(uid, QUEST_XP)
            give_coins(uid, 10)
    if len(done) >= 3 and "ALL" not in done:
        db.execute("INSERT OR IGNORE INTO quest_done VALUES(?,?,?)", (d, uid, "ALL"))
        db.commit()
        out.append(f"🏅 {link(uid, u['name'])} выполнил ВСЕ квесты дня! (+{QUEST_ALL_BONUS_XP} опыта)")
        out += give_xp(uid, QUEST_ALL_BONUS_XP)
        give_coins(uid, 30)
    if out:
        try:
            await bot.send_message(CHAT_ID, "\n".join(out), parse_mode=HTML,
                                   link_preview_options=NOPREV)
        except Exception:
            log.exception("quest msg")


def add_counted(uid, message_id, is_reply):
    d = today()
    yd = (now() - timedelta(days=1)).strftime(FMT)
    u = urow(uid)
    streak, best, last = u["streak"], u["best_streak"], u["last_day"]
    ev = []
    if last != d:
        streak = streak + 1 if last == yd else 1
        best = max(best, streak)
        if streak in STREAK_MILESTONES:
            ev.append(f"🔥 {link(uid, u['name'])} в серии уже {streak} дн. подряд!")
    db.execute("UPDATE users SET total=total+1, streak=?, best_streak=?, last_day=?, last_seen=? "
               "WHERE user_id=?", (streak, best, d, time.time(), uid))
    db.execute("INSERT OR IGNORE INTO msgs(message_id,user_id,day) VALUES(?,?,?)",
               (message_id, uid, d))
    db.commit()
    bump(uid, "cnt")
    if (u["total"] + 1) % 10 == 0:
        give_coins(uid, 1)
    if is_reply:
        bump(uid, "replies")
    ev += give_xp(uid, 1)
    return ev


def count_words(text):
    d = today()
    for w in set(re.findall(r"[a-zа-я]{5,}", norm(text))):
        if w in STOPWORDS:
            continue
        db.execute("INSERT INTO words(day,word,cnt) VALUES(?,?,1) "
                   "ON CONFLICT(day,word) DO UPDATE SET cnt=cnt+1", (d, w))
    db.commit()


# ============================ ТОПЫ ============================
def top_rows(start, end, limit=10):
    return db.execute(
        "SELECT d.user_id AS uid, u.name AS name, u.tag AS tag, SUM(d.cnt) AS c "
        "FROM daily d JOIN users u ON u.user_id=d.user_id "
        "WHERE d.day>=? AND d.day<=? GROUP BY d.user_id HAVING c>0 "
        "ORDER BY c DESC LIMIT ?", (start, end, limit)).fetchall()


def fmt_top(rows):
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, r in enumerate(rows):
        m = medals[i] if i < 3 else f"{i + 1}."
        t = f"<b>{esc(r['tag'])}</b> " if r["tag"] else ""
        lines.append(f"{m} {t}{esc(r['name'])} — {r['c']}")
    return "\n".join(lines)


def week_start():
    return (now() - timedelta(days=6)).strftime(FMT)


def month_start():
    return now().replace(day=1).strftime(FMT)


# ============================ ИТОГИ ДНЯ ============================
async def send_text(bot, text, **kw):
    return await bot.send_message(CHAT_ID, text, parse_mode=HTML,
                                  link_preview_options=NOPREV, **kw)


async def send_summary(bot, d, periodic):
    rows = [r for r in top_rows(d, d, 3) if r["c"] >= MIN_MSGS]
    if rows:
        medals = ["🥇", "🥈", "🥉"]
        lines = [f"{medals[i]} {link(r['uid'], r['name'])} — {r['c']} сообщ."
                 for i, r in enumerate(rows)]
        text = ("🏆 <b>Итоги дня</b>\n" + "\n".join(lines) +
                f"\n\n🎁 {owner_mention()}, вручи подарки победителям!")
    else:
        text = f"🏆 <b>Итоги дня</b>\nСегодня никто не набрал норму ({MIN_MSGS} сообщений). Завтра новый шанс!"
    path = os.path.join(BASE, BANNER)
    sent = False
    if os.path.exists(path) and len(text) <= 1000:
        try:
            with open(path, "rb") as f:
                await bot.send_photo(CHAT_ID, f, caption=text, parse_mode=HTML)
            sent = True
        except Exception:
            log.exception("banner")
    if not sent:
        await send_text(bot, text)

    best = db.execute("SELECT m.message_id, m.user_id, m.reactions, u.name FROM msgs m "
                      "JOIN users u ON u.user_id=m.user_id WHERE m.day=? AND m.reactions>=? "
                      "ORDER BY m.reactions DESC LIMIT 1", (d, MIN_REACTIONS)).fetchone()
    if best:
        try:
            await bot.send_message(
                CHAT_ID,
                f"⭐ <b>Лучшее сообщение дня</b> — {link(best['user_id'], best['name'])} "
                f"({best['reactions']} реакций)!\n🎁 {owner_mention()}, награда автору.",
                parse_mode=HTML, link_preview_options=NOPREV,
                reply_parameters=ReplyParameters(message_id=best["message_id"],
                                                 allow_sending_without_reply=True))
        except Exception:
            log.exception("best msg")

    if periodic:
        n = now()
        if n.weekday() == 6:
            rows = top_rows(week_start(), d, 10)
            if rows:
                await send_text(bot, "📅 <b>Топ недели</b>\n" + fmt_top(rows))
        if (n + timedelta(days=1)).day == 1:
            rows = top_rows(month_start(), d, 10)
            if rows:
                await send_text(bot, "🗓 <b>Топ месяца</b>\n" + fmt_top(rows))


# ============================ ВОПРОС И ВИКТОРИНА ============================
async def post_question(bot):
    await send_text(bot, "💬 <b>Вопрос дня</b>\n" + esc(random.choice(QUESTIONS)))


async def post_quiz(bot):
    prev = state_get("quiz_prev")
    pool = [q for i, q in enumerate(QUIZ) if str(i) != prev]
    q, answers = random.choice(pool)
    state_set("quiz_prev", QUIZ.index((q, answers)))
    state_set("quiz", json.dumps({"q": q, "a": answers,
                                  "until": time.time() + QUIZ_MINUTES * 60}, ensure_ascii=False))
    await send_text(bot, f"🧠 <b>Викторина!</b>\n{esc(q)}\n\nПервый, кто ответит правильно, получает очки. "
                         f"Время: {QUIZ_MINUTES} мин.")


def get_quiz():
    raw = state_get("quiz")
    return json.loads(raw) if raw else None


async def try_quiz(update, text):
    q = get_quiz()
    if not q:
        return
    if time.time() > q["until"]:
        return
    n = norm(text)
    for a in q["a"]:
        if re.search(rf"(?<!\w){re.escape(norm(a))}(?!\w)", n):
            state_del("quiz")
            uid = update.effective_user.id
            db.execute("UPDATE users SET quiz_pts=quiz_pts+1 WHERE user_id=?", (uid,))
            db.commit()
            ev = give_xp(uid, QUIZ_XP)
            give_coins(uid, 10)
            pts = urow(uid)["quiz_pts"]
            await update.effective_message.reply_text(
                f"✅ Верно! {link(uid, urow(uid)['name'])} отвечает первым. "
                f"Очков викторины: {pts} (+{QUIZ_XP} опыта)\n" + "\n".join(ev),
                parse_mode=HTML, link_preview_options=NOPREV)
            return


# ============================ ПЛАНИРОВЩИК ============================
async def tick(app):
    bot = app.bot
    n = now()
    d = n.strftime(FMT)
    db.execute("DELETE FROM mutes WHERE until<?", (time.time(),))
    db.commit()
    for name, (h, m), fn in (
        ("question", QUESTION_TIME, lambda: post_question(bot)),
        ("quiz", QUIZ_TIME, lambda: post_quiz(bot)),
        ("summary", SUMMARY_TIME, lambda: send_summary(bot, d, True)),
        ("relations", REL_TIME, lambda: life_daily(bot)),
    ):
        sched = n.replace(hour=h, minute=m, second=0, microsecond=0)
        if n >= sched and (n - sched) < timedelta(hours=2) and state_get("ran_" + name) != d:
            state_set("ran_" + name, d)
            await fn()

    q = get_quiz()
    if q and time.time() > q["until"]:
        state_del("quiz")
        await send_text(bot, f"⌛ Время вышло. Правильный ответ: <b>{esc(q['a'][0])}</b>")

    quiet = QUIET_HOURS[0] <= n.hour < QUIET_HOURS[1]
    last = state_get("last_promo")
    if last is None:
        state_set("last_promo", time.time())
        state_set("promo_gap", random.randint(PROMO_MIN_MIN, PROMO_MAX_MIN))
    elif not quiet and time.time() - float(last) >= float(state_get("promo_gap") or 90) * 60:
        state_set("last_promo", time.time())
        state_set("promo_gap", random.randint(PROMO_MIN_MIN, PROMO_MAX_MIN))
        turn = int(float(state_get("promo_turn") or 0))
        state_set("promo_turn", turn + 1)
        await (post_ad if turn % 2 == 0 else post_invite)(bot)


async def scheduler(app):
    await asyncio.sleep(5)
    while True:
        try:
            await tick(app)
        except Exception:
            log.exception("tick")
        await asyncio.sleep(30)


async def post_ad(bot):
    await send_text(bot, random.choice([
        f"📢 Загляните к нам в канал {esc(CHANNEL)}, там проходят все розыгрыши",
        f"📢 Подписывайтесь на {esc(CHANNEL)}, чтобы не пропустить розыгрыши и новости",
        f"📢 Самое интересное у нас в канале {esc(CHANNEL)}. Подпишитесь, чтобы быть в курсе",
    ]))


async def post_invite(bot):
    ids = [r["user_id"] for r in db.execute(
        "SELECT user_id FROM users WHERE registered=1 AND total>0")]
    text = random.choice([
        "🎁 Зовите друзей в чат, за приглашения можно получить подарки",
        "🎁 Пригласите друга в чат и получите подарок",
        "🎁 Хотите подарок? Приводите друзей в чат",
    ]) + f"\nПодробности у @{OWNER_USERNAME}\nЧтобы отключить напоминания, напишите /анрег"
    if not ids:
        await send_text(bot, text)
        return
    for i in range(0, len(ids), 90):
        hidden = "".join(f'<a href="tg://user?id={u}">\u200b</a>' for u in ids[i:i + 90])
        await send_text(bot, text + hidden if i == 0 else "🎁" + hidden)


# ============================ КОМАНДЫ ============================
def group_only(fn):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        if chat.type == "private":
            if fn.__name__ in ("cmd_start", "cmd_help", "cmd_id"):
                return await fn(update, context)
            return await update.effective_message.reply_text(
                f"Бот работает исключительно в чате {CHAT_TAG}")
        if chat.id not in ALLOWED:
            return
        if update.effective_user:
            touch(update.effective_user)
        return await fn(update, context)
    wrapper.__name__ = fn.__name__
    return wrapper


def owner_only(fn):
    async def wrapper(update, context):
        if not is_owner(update.effective_user):
            return
        return await fn(update, context)
    wrapper.__name__ = fn.__name__
    return group_only(wrapper)


async def reply(update, text, **kw):
    return await update.effective_message.reply_text(
        text, parse_mode=HTML, link_preview_options=NOPREV, **kw)


async def cmd_start(update, context):
    private = update.effective_chat.type == "private"
    await update.effective_message.reply_text(START_TEXT, reply_markup=menu_kb() if private else None)


async def cmd_help(update, context):
    private = update.effective_chat.type == "private"
    if await send_commands_link(update):
        return
    await reply(update, HELP_TEXT, **({"reply_markup": menu_kb()} if private else {}))


async def cmd_id(update, context):
    cid = update.effective_chat.id
    ok = "✅ бот тут работает" if cid in ALLOWED else "❌ бот здесь молчит: этот чат не совпадает с CHAT_ID в коде"
    await update.effective_message.reply_text(
        f"ID этого чата: {cid}\n{ok}\nCHAT_ID в коде: {CHAT_ID}\nверсия: 24")


def why_no_target(update, usage):
    """Если команду дали ответом, но цель не определилась — объяснить почему."""
    m = update.effective_message
    r = m.reply_to_message if m else None
    if m and getattr(m, "external_reply", None):
        return ("Ты ответил на сообщение из другого чата (личного). Найди сообщение этого "
                "человека прямо в группе и ответь командой на него.")
    if r:
        if getattr(r, "sender_chat", None):
            return ("Это сообщение отправлено от имени канала или чата, а не участника — "
                    "применить команду нельзя.")
        if r.from_user and r.from_user.is_bot:
            return (f"Это сообщение от бота или анонимного админа ({esc(r.from_user.full_name)}) — "
                    "применить команду нельзя.")
        if not r.from_user:
            return "Не удалось определить автора этого сообщения (скрытый отправитель)."
    return usage


def reply_user(update):
    """Пользователь из ответа на сообщение (не бот)."""
    m = update.effective_message
    if m.reply_to_message and m.reply_to_message.from_user:
        u = m.reply_to_message.from_user
        if not u.is_bot:
            touch(u)
            return u
    return None


def target_user(update):
    """Цель: ответ на сообщение, иначе @юзернейм (или упоминание без юза) прямо в тексте."""
    u = reply_user(update)
    if u:
        return u
    m = update.effective_message
    if not m or not getattr(m, "text", None):
        return None
    for e in (getattr(m, "entities", None) or []):
        if getattr(e, "type", "") == "text_mention" and getattr(e, "user", None) and not e.user.is_bot:
            touch(e.user)
            return e.user
    for tok in re.findall(r"@([A-Za-z0-9_]{4,32})", m.text):
        r = find_by_username(tok)
        if r:
            return SimpleNamespace(id=r["user_id"], username=r["username"], is_bot=False,
                                   full_name=r["name"] or tok)
    return None


async def build_profile(bot, row):
    uid = row["user_id"]
    try:
        cm = await bot.get_chat_member(CHAT_ID, uid)
        role = "Телеграм-админ этого чата" if cm.status in ("administrator", "creator") \
            else "участник"
    except Exception:
        role = "участник"
    lvl = level_of(row["xp"])
    nxt = ""
    if lvl < 100:
        nxt = f" (до {lvl + 1} ур.: {level_need(lvl + 1) - row['xp']} оп.)"
    ot, days = old_title(row["first_seen"])
    d = today()
    wk, mo = week_start(), month_start()

    def s(a, b):
        r = db.execute("SELECT COALESCE(SUM(cnt),0) c FROM daily WHERE user_id=? AND day>=? AND day<=?",
                       (uid, a, b)).fetchone()
        return r["c"]

    name = f"@{row['username']}" if row["username"] else esc(row["name"])
    tag = f"<b>{esc(row['tag'])}</b>\n" if (row["tag"] or "").strip() else ""
    st = row["streak"] if row["last_day"] in (d, (now() - timedelta(days=1)).strftime(FMT)) else 0
    ar = rank_of_id(uid)
    adm = f"🛡 {rank_title(ar)} (админ-ранг {ar})\n" if ar else ""
    return (
        f"👤 Это пользователь {name}\n{tag}"
        f"👨🏻‍🔧 {role}\n{adm}\n"
        f"▫️ [{lvl}] Ранг: {esc(title_of(lvl))}{nxt}\n"
        f"🕰 Олдство: {ot} ({days} дн. в чате)\n\n"
        f"Репутация: ✨ {row['rep']} | ➕ {row['rep_given']}\n\n"
        f"1. Первое появление: ❗️ {fmt_when(row['first_seen'])}\n"
        f"2. Последний актив: {fmt_when(row['last_seen'])}\n"
        f"3. Актив (д|н|м|весь): {s(d, d)} | {s(wk, d)} | {s(mo, d)} | {row['total']}\n"
        f"4. Серия дней: 🔥 {st} (рекорд {row['best_streak']})\n"
        f"5. Очки: 🧠 {row['quiz_pts']} | 🎮 {row['game_pts']} | 📜 {row['quest_pts']}"
    )


@group_only
async def cmd_me(update, context):
    u = target_user(update) or update.effective_user
    touch(u)
    text = await build_profile(context.bot, urow(u.id))
    await reply(update, text)


@group_only
async def cmd_top(update, context):
    rows = top_rows(today(), today())
    await reply(update, "📊 <b>Топ дня</b>\n" + fmt_top(rows) if rows else "Пока тишина 🤫")


@group_only
async def cmd_week(update, context):
    rows = top_rows(week_start(), today())
    await reply(update, "📅 <b>Топ недели</b>\n" + fmt_top(rows) if rows else "Пока тишина 🤫")


@group_only
async def cmd_month(update, context):
    rows = top_rows(month_start(), today())
    await reply(update, "🗓 <b>Топ месяца</b>\n" + fmt_top(rows) if rows else "Пока тишина 🤫")


@group_only
async def cmd_quiztop(update, context):
    rows = db.execute("SELECT name, quiz_pts FROM users WHERE quiz_pts>0 "
                      "ORDER BY quiz_pts DESC LIMIT 10").fetchall()
    if not rows:
        return await reply(update, "Пока никто не отвечал правильно 🧠")
    await reply(update, "🧠 <b>Рейтинг викторины</b>\n" + "\n".join(
        f"{i + 1}. {esc(r['name'])} — {r['quiz_pts']}" for i, r in enumerate(rows)))


@group_only
async def cmd_quests(update, context):
    uid = update.effective_user.id
    d = today()
    prog = progress(uid, d)
    done = {r["qid"] for r in db.execute(
        "SELECT qid FROM quest_done WHERE day=? AND user_id=?", (d, uid))}
    lines = ["📜 <b>Квесты на сегодня</b>"]
    for qid, target in quests_for(d):
        mark = "✅" if qid in done else "▫️"
        lines.append(f"{mark} {QUEST_TITLES[qid].format(n=target)} "
                     f"({min(prog[qid], target)}/{target})")
    lines.append(f"\nНаграда: +{QUEST_XP} опыта за квест, +{QUEST_ALL_BONUS_XP} за все три.")
    await reply(update, "\n".join(lines))


# ---------- мини-игры ----------
async def played(bot, uid):
    bump(uid, "plays")
    await check_quests(bot, uid)


@group_only
async def cmd_coin(update, context):
    uid = update.effective_user.id
    if not cooldown(("coin", uid), 5):
        return
    await reply(update, "🪙 Выпал: <b>" + random.choice(["Орёл", "Решка"]) + "</b>")
    await played(context.bot, uid)


@group_only
async def cmd_slots(update, context):
    uid = update.effective_user.id
    if not cooldown(("slots", uid), 20):
        return await reply(update, "Подожди немного перед следующей попыткой ⏳")
    msg = await context.bot.send_dice(update.effective_chat.id, emoji="🎰")
    await asyncio.sleep(3)
    v = msg.dice.value
    if v == 64:
        pts, text = 10, "🎉 ДЖЕКПОТ! +10 игровых очков"
    elif v in (1, 22, 43):
        pts, text = 3, "👏 Три в ряд! +3 игровых очка"
    else:
        pts, text = 0, "Не повезло, попробуй ещё 🍀"
    if pts:
        db.execute("UPDATE users SET game_pts=game_pts+?, coins=coins+? WHERE user_id=?", (pts, pts * 2, uid))
        db.commit()
    await reply(update, text)
    await played(context.bot, uid)


@group_only
async def cmd_dice(update, context):
    me = update.effective_user
    other = target_user(update)
    if not other or other.id == me.id:
        return await reply(update, why_no_target(update, "Ответь командой /dice на сообщение соперника 🎲"))
    if not cooldown(("dice", me.id), 20):
        return await reply(update, "Подожди немного ⏳")
    chat = update.effective_chat.id
    a = await context.bot.send_dice(chat, emoji="🎲")
    b = await context.bot.send_dice(chat, emoji="🎲")
    await asyncio.sleep(4)
    va, vb = a.dice.value, b.dice.value
    ra, rb = urow(me.id), urow(other.id)
    if va == vb:
        res = "🤝 Ничья!"
    else:
        win = ra if va > vb else rb
        db.execute("UPDATE users SET game_pts=game_pts+1, coins=coins+2 WHERE user_id=?", (win["user_id"],))
        db.commit()
        res = f"🏆 Победил {link(win['user_id'], win['name'])}! (+1 игровое очко)"
    await reply(update, f"🎲 {esc(ra['name'])}: {va} — {esc(rb['name'])}: {vb}\n{res}")
    await played(context.bot, me.id)
    await played(context.bot, other.id)


async def profile_score(bot, row):
    uid = row["user_id"]
    parts = {}
    try:
        ph = await bot.get_user_profile_photos(uid, limit=1)
        parts["аватарка"] = 20 if ph.total_count > 0 else 0
    except Exception:
        parts["аватарка"] = 0
    bio = ""
    try:
        ch = await bot.get_chat(uid)
        bio = (getattr(ch, "bio", "") or "").strip()
    except Exception:
        pass
    parts["описание"] = 15 if len(bio) >= 10 else (5 if bio else 0)
    parts["юзернейм"] = 10 if row["username"] else 0
    parts["уровень"] = round(level_of(row["xp"]) * 0.5)
    parts["репутация"] = min(row["rep"] * 2, 30)
    parts["олдство"] = min(old_title(row["first_seen"])[1] // 15, 24)
    parts["тег"] = 10 if (row["tag"] or "").strip() else 0
    nft, regular = await count_gifts(bot, uid)
    parts["NFT-подарки"] = min(nft * 4, 40)
    parts["подарки"] = min(regular, 10)
    return parts


async def count_gifts(bot, uid):
    """(уникальные NFT, обычные) среди подарков, которые человек показывает в профиле.
    Если у человека подарки скрыты или метод недоступен — (0, 0)."""
    fn = getattr(bot, "get_user_gifts", None)
    if fn is None:
        return 0, 0
    try:
        res = await fn(user_id=uid, limit=100)
    except Exception as e:
        log.warning("get_user_gifts: %s", e)
        return 0, 0
    nft = regular = 0
    for g in getattr(res, "gifts", None) or []:
        if getattr(g, "type", "") == "unique" or hasattr(g, "gift") and hasattr(g.gift, "model"):
            nft += 1
        else:
            regular += 1
    total = getattr(res, "total_count", 0) or 0
    if total > nft + regular:      # список обрезан лимитом, остальное считаем обычными
        regular += total - nft - regular
    return nft, regular


NFT_RE = re.compile(r"(?:https?://)?t\.me/nft/([A-Za-z0-9]+)-(\d+)", re.I)


def _pattern_tile(card_bytes, S):
    """Берёт готовую карточку подарка (фон + узор + статичная модель), вырезает центр
    с моделью и заливает его цветом фона. Остаётся фон с узором."""
    from io import BytesIO
    from PIL import Image, ImageDraw, ImageFilter, ImageStat
    im = Image.open(BytesIO(card_bytes)).convert("RGB")
    w, h = im.size
    m = int(min(w, h) * 0.03)                      # срезаем рамку
    im = im.crop((m, m, w - m, h - m)).resize((S, S), Image.LANCZOS)
    cx = cy = S / 2
    rx, ry = S * 0.37, S * 0.35                    # зона модели
    band = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(band)
    d.ellipse((cx - rx * 1.22, cy - ry * 1.22, cx + rx * 1.22, cy + ry * 1.22), fill=255)
    d.ellipse((cx - rx * 1.02, cy - ry * 1.02, cx + rx * 1.02, cy + ry * 1.02), fill=0)
    med = tuple(int(v) for v in ImageStat.Stat(im, band).median)
    light = tuple(min(255, int(v * 1.06 + 4)) for v in med)
    fill = Image.new("RGB", (S, S), med)
    glow = Image.radial_gradient("L").resize((S, S)).point(lambda v: 255 - min(255, v * 2))
    fill = Image.composite(Image.new("RGB", (S, S), light), fill, glow.point(lambda v: v // 3))
    hole = Image.new("L", (S, S), 0)
    ImageDraw.Draw(hole).ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
    hole = hole.filter(ImageFilter.GaussianBlur(S * 0.03))
    return Image.composite(fill, im, hole)


NFT_LOCK = asyncio.Lock()


def _cards_to_gif(items, out):
    """items — список (lottie_json_str, bg). Рисует карточки как в подборках NFT:
    скруглённые плитки с мягким свечением на тёмном фоне. Одна — по центру, несколько — сеткой."""
    from PIL import Image, ImageDraw
    from rlottie_python import LottieAnimation
    k = len(items)
    anims = [LottieAnimation.from_data(it[0]) for it in items]
    totals = [max(1, a.lottie_animation_get_totalframe()) for a in anims]
    fps = anims[0].lottie_animation_get_framerate() or 30
    FOOT = 56
    if k == 1:
        S, W, H, cols, gap = 380, 800, 450, 1, 0
        H += FOOT
    else:
        S, gap, cols = 250, 16, min(3, k)
        rows = (k + cols - 1) // cols
        W, H = cols * S + (cols + 1) * gap, rows * S + (rows + 1) * gap + FOOT
    base = Image.new("RGB", (W, H), (22, 19, 21))
    try:
        bd = ImageDraw.Draw(base)
        ft = _cert_font("bold", 30)
        tw = bd.textlength(CHAT_TAG, font=ft)
        bd.text(((W - tw) / 2, H - FOOT + 10), CHAT_TAG, font=ft, fill=(235, 232, 236))
    except Exception as e:
        print("NFT: подпись не нарисована:", repr(e)[:100])
    # фон каждой плитки: радиальное свечение + скругление
    tiles = []
    rad = Image.radial_gradient("L").resize((S, S))              # 0 центр -> 255 край
    rmask = Image.new("L", (S * 3, S * 3), 0)
    ImageDraw.Draw(rmask).rounded_rectangle((0, 0, S * 3 - 1, S * 3 - 1), radius=int(S * 3 * 0.24), fill=255)
    rmask = rmask.resize((S, S), Image.LANCZOS)
    for _, bg, card in items:
        light = tuple(min(255, int(v * 1.18 + 12)) for v in bg)
        edge = tuple(int(v * 0.82) for v in bg)
        tile = Image.composite(Image.new("RGB", (S, S), edge), Image.new("RGB", (S, S), light),
                               rad.point(lambda v: int(max(0, v - 40) * 255 / 215)))
        if card:
            try:
                tile = _pattern_tile(card, S) or tile
            except Exception as e:
                print("NFT: узор не получился:", repr(e)[:150])
        tiles.append(tile)
    pos = []
    for i in range(k):
        r, c = divmod(i, cols)
        if k == 1:
            pos.append(((W - S) // 2, (H - FOOT - S) // 2))
        else:
            pos.append((gap + c * (S + gap), gap + r * (S + gap)))
    n = max(totals)
    step = max(1, n // 55)
    gs = int(S * 0.8)
    frames = []
    for i in range(0, n, step):
        canvas = base.copy()
        for j, a in enumerate(anims):
            fr = a.render_pillow_frame(frame_num=i % totals[j], width=gs, height=gs).convert("RGBA")
            t = tiles[j].convert("RGBA")
            t.alpha_composite(fr, ((S - gs) // 2, (S - gs) // 2))
            canvas.paste(t.convert("RGB"), pos[j], rmask)
        frames.append(canvas.convert("P", palette=Image.ADAPTIVE, colors=256, dither=Image.NONE))
    frames[0].save(out, save_all=True, append_images=frames[1:], loop=0,
                   duration=int(1000 / max(fps, 1) * step), disposal=2, optimize=False)


async def fetch_nft_source(name, num):
    """Возвращает ('lottie', json_str, bg) | ('file', path, None) | None."""
    import gzip
    import httpx
    slug = f"{name}-{num}".lower()
    page = f"https://t.me/nft/{name}-{num}"
    cands, bg, card = [], (45, 45, 55), None
    async with httpx.AsyncClient(timeout=25, follow_redirects=True,
                                 headers={"User-Agent": "Mozilla/5.0"}) as c:
        for suffix in (".large.jpg", ".medium.jpg", ".webp"):
            try:
                rr = await c.get(f"https://nft.fragment.com/gift/{slug}{suffix}")
                if rr.status_code == 200 and len(rr.content) > 2000:
                    card = rr.content
                    break
            except Exception:
                pass
        try:
            r = await c.get(page)
            txt = html.unescape(r.text)
            cands += re.findall(r'https?://[^\s"\'<>\\)]+\.(?:tgs|json|webm|mp4|gif)(?:\?[^\s"\'<>\\)]*)?', txt)
            mm = re.search(r'og:image"\s+content="([^"]+)"', txt)
            if mm:
                try:
                    from io import BytesIO
                    from PIL import Image
                    raw_img = (await c.get(mm.group(1))).content
                    im = Image.open(BytesIO(raw_img)).convert("RGB")
                    bg = im.getpixel((6, 6))
                    if card is None:
                        card = raw_img
                except Exception:
                    pass
        except Exception as e:
            print("NFT: страница не открылась:", e)
        cands += [f"https://nft.fragment.com/gift/{slug}.lottie.json",
                  f"https://nft.fragment.com/gift/{slug}.tgs"]
        seen = set()
        for u in cands:
            if u in seen:
                continue
            seen.add(u)
            try:
                r = await c.get(u)
                if r.status_code != 200 or not r.content:
                    continue
                path = u.split("?")[0].lower()
                if path.endswith((".mp4", ".gif")):
                    out = os.path.join(BASE, f"nft_{slug}" + path[-4:])
                    open(out, "wb").write(r.content)
                    return ("file", out, None)
                if path.endswith(".webm"):
                    continue
                raw = r.content
                if raw[:2] == b"\x1f\x8b":
                    raw = gzip.decompress(raw)
                return ("lottie", raw.decode("utf-8"), tuple(bg), card)
            except Exception as e:
                print("NFT: источник не подошёл:", u, "->", repr(e)[:200])
    return None


async def handle_nft(update, context, text):
    found = []
    for mm in NFT_RE.finditer(text):
        key = (mm.group(1), mm.group(2))
        if key not in found:
            found.append(key)
    found = found[:6]
    caps = []
    for name, num in found:
        caps.append(f"🎁 <b>{esc(re.sub(r'(?<!^)(?=[A-Z])', ' ', name))}</b> #{esc(num)}")
    caption = ("\n".join(caps) + "\n" +
               f"Запросил: {link(update.effective_user.id, disp(update.effective_user))}")
    gif, tmp = None, []
    try:
        await context.bot.send_chat_action(update.effective_chat.id, "upload_video")
        srcs = [await fetch_nft_source(n, u) for n, u in found]
        srcs = [s for s in srcs if s]
        lot = [(s[1], s[2], s[3]) for s in srcs if s[0] == "lottie"]
        files = [s[1] for s in srcs if s[0] == "file"]
        tmp += files
        if lot:
            gif = os.path.join(BASE, f"nft_{update.effective_message.message_id}.gif")
            tmp.append(gif)
            async with NFT_LOCK:
                await asyncio.to_thread(_cards_to_gif, lot, gif)
        elif files:
            gif = files[0]
    except ImportError:
        print("NFT: не установлены rlottie-python/Pillow. Выполни: py -m pip install rlottie-python Pillow")
    except Exception as e:
        print("NFT: ошибка:", repr(e)[:200])
        gif = None
    if gif:
        try:
            with open(gif, "rb") as f:
                await update.effective_message.reply_animation(f, caption=caption, parse_mode=HTML)
            return
        except Exception as e:
            print("NFT: не удалось отправить gif:", repr(e)[:200])
        finally:
            for p in tmp:
                try:
                    os.remove(p)
                except OSError:
                    pass
    links = "\n".join(f"<a href=\"https://t.me/nft/{n}-{u}\">Открыть NFT {esc(n)} #{esc(u)}</a>" for n, u in found)
    await update.effective_message.reply_text(
        f"{caption}\n{links}", parse_mode=HTML,
        link_preview_options=LinkPreviewOptions(
            url=f"https://t.me/nft/{found[0][0]}-{found[0][1]}", prefer_large_media=True, show_above_text=True))


@group_only
async def cmd_duel(update, context):
    me = update.effective_user
    other = target_user(update)
    if not other or other.id == me.id:
        return await reply(update, "Ответь командой /duel на сообщение соперника — "
                                   "сравним профили ⚔️")
    if not cooldown(("duel", me.id), 30):
        return await reply(update, "Подожди немного ⏳")
    ra, rb = urow(me.id), urow(other.id)
    pa, pb = await profile_score(context.bot, ra), await profile_score(context.bot, rb)
    sa, sb = sum(pa.values()) + random.randint(0, 15), sum(pb.values()) + random.randint(0, 15)

    def fmt(p):
        return ", ".join(f"{k} {v}" for k, v in p.items() if v)

    win = ra if sa >= sb else rb
    lose = rb if win is ra else ra
    db.execute("UPDATE users SET game_pts=game_pts+2, duel_w=duel_w+1, coins=coins+5 WHERE user_id=?",
               (win["user_id"],))
    db.execute("UPDATE users SET duel_l=duel_l+1 WHERE user_id=?", (lose["user_id"],))
    db.commit()
    await reply(update,
                f"⚔️ <b>Дуэль профилей</b>\n"
                f"{esc(ra['name'])}: <b>{sa}</b> ({fmt(pa)})\n"
                f"{esc(rb['name'])}: <b>{sb}</b> ({fmt(pb)})\n\n"
                f"🏆 Побеждает {link(win['user_id'], win['name'])} (+2 игровых очка, +5 🪙)\n"
                f"<i>В счёт идут: аватарка, описание, юзернейм, уровень, репутация, олдство, тег, "
                f"NFT-подарки и обычные подарки из профиля + немного удачи. "
                f"Скрытые подарки бот не видит. NFT-юзернейм отличить нельзя.</i>")
    await played(context.bot, me.id)
    await played(context.bot, other.id)


# ---------- ранги админов и права на команды ----------
# с какого ранга доступна команда (меняется: «дк мут 2»). Владелец всегда 8.
DEFAULT_RANKS = {
    "админка": 1, "админы": 1, "мут": 1, "размут": 1, "список мута": 1,
    "бан": 2, "разбан": 2, "статистика": 2, "слова дня": 2,
    "тег": 3, "снять тег": 3,
    "итоги": 4, "запустить вопрос": 4, "запустить викторину": 4,
    "добавить картинку": 2, "список картинок": 1, "очистить картинки": 3,
    "добавить товар": 4, "удалить товар": 4, "выдать монеты": 5, "заказы": 2, "выдан": 2,
    "добавить работу": 5, "удалить работу": 5, "список работ": 2, "журнал": 3,
    "установить приветствие": 3, "установить правила": 3, "статистика недели": 2,
    "статья команд": 6,
}
ADMIN_TITLES = {
    1: "Мл. модератор", 2: "Старший модератор", 3: "Главный модератор",
    4: "Стажер админ", 5: "Младший админ", 6: "Старший админ",
    7: "Зам.Администрации", 8: "Доверенное лицо",
}


def rank_title(n):
    return ADMIN_TITLES.get(n, "")


FIXED_8 = {"повысить", "дк"}          # только админ 8 ранга
MAX_RANK = 8


def rank_of_id(uid):
    oid = state_get("owner_id")
    if oid and str(uid) == oid:
        return MAX_RANK
    r = db.execute("SELECT arank FROM users WHERE user_id=?", (uid,)).fetchone()
    return (r["arank"] or 0) if r else 0


def rank_of(user):
    if not user:
        return 0
    if is_owner(user):
        return MAX_RANK
    return rank_of_id(user.id)


def required_rank(key):
    if key in FIXED_8:
        return MAX_RANK
    r = db.execute("SELECT rank FROM cmd_access WHERE cmd=?", (key,)).fetchone()
    return r["rank"] if r else DEFAULT_RANKS.get(key, MAX_RANK)


def has_rank(user, key):
    return rank_of(user) >= required_rank(key)


def can_act_on(actor, target_id):
    """Нельзя трогать тех, чей ранг не ниже твоего (владелец может всех)."""
    if is_owner(actor):
        return True
    return rank_of(actor) > rank_of_id(target_id)


def need(key):
    def deco(fn):
        async def wrapper(update, context):
            if not has_rank(update.effective_user, key):
                return
            if key not in LOG_SKIP:
                log_admin(update, key)
            return await fn(update, context)
        wrapper.__name__ = fn.__name__
        return group_only(wrapper)
    return deco


UNITS = {"м": 1, "мин": 1, "минут": 1, "минуту": 1, "минуты": 1, "m": 1, "min": 1, "mins": 1,
         "ч": 60, "час": 60, "часа": 60, "часов": 60, "h": 60, "hour": 60, "hours": 60,
         "д": 1440, "дн": 1440, "день": 1440, "дня": 1440, "дней": 1440,
         "d": 1440, "day": 1440, "days": 1440}


def parse_duration(args):
    """('30','мин') / ('2ч') / ('10','min') -> (минуты, сколько слов съели) или (None, 0)."""
    if not args:
        return None, 0
    m = re.fullmatch(r"(\d{1,6})([a-zа-я]*)", args[0].lower())
    if not m:
        return None, 0
    n, unit, used = int(m.group(1)), m.group(2), 1
    if not unit and len(args) > 1 and args[1].lower() in UNITS:
        unit, used = args[1].lower(), 2
    if unit and unit not in UNITS:
        return None, 0
    return n * (UNITS[unit] if unit else 1), used


def fmt_minutes(m):
    m = max(int(m), 0)
    d, rem = divmod(m, 1440)
    h, mi = divmod(rem, 60)
    parts = []
    if d:
        parts.append(f"{d} д.")
    if h:
        parts.append(f"{h} ч.")
    if mi or not parts:
        parts.append(f"{mi} мин.")
    return " ".join(parts)


def resolve_target(update, args):
    """Цель: ответ на сообщение, иначе @юзернейм / id из аргументов.
    -> (uid, имя, оставшиеся аргументы, текст ошибки)"""
    u = reply_user(update)
    if u:
        return u.id, disp(u), args, None
    uid = name = None
    rest = []
    for a in args:
        if uid is None and a.startswith("@"):
            r = find_by_username(a)
            if not r:
                return None, None, args, (
                    f"Не нашёл {esc(a)}: человек должен хотя бы раз написать в чат при "
                    f"запущенном боте. Можно ответить командой на его сообщение.")
            uid, name = r["user_id"], r["name"]
            continue
        if uid is None and a.isdigit() and len(a) > 6:
            r = urow(int(a))
            uid, name = int(a), (r["name"] if r else a)
            continue
        rest.append(a)
    if uid is None:
        return None, None, args, None
    return uid, name, rest, None


@need("админка")
async def cmd_admin(update, context):
    await reply(update, ADMIN_HELP)


MUTE_USAGE = ("Формат: «мут 30 @юзернейм причина» или ответом на сообщение: «мут 30 причина». "
              "Время: 30 (минуты), 2ч, 1д.")


@need("мут")
async def cmd_mute(update, context):
    msg = update.effective_message
    args = list(context.args or [])
    from_slash = (msg.text or "").startswith("/")
    minutes, used = parse_duration(args)
    if minutes is None:
        minutes = 60
        first = args[0] if args else ""
        if args and not from_slash and not (first.startswith("@") or
                                            (first.isdigit() and len(first) > 6)):
            return                      # это обычная фраза, а не команда
    else:
        args = args[used:]
    uid, name, rest, err = resolve_target(update, args)
    if err:
        return await reply(update, err)
    if not uid:
        return await reply(update, why_no_target(update, MUTE_USAGE))
    if minutes < 1:
        return await reply(update, "Время должно быть не меньше 1 минуты.")
    minutes = min(minutes, 366 * 1440)
    actor = update.effective_user
    if not can_act_on(actor, uid):
        return await reply(update, "Нельзя: у этого участника ранг не ниже твоего.")
    reason = " ".join(rest).strip()[:200]
    until = time.time() + minutes * 60
    try:
        await context.bot.restrict_chat_member(
            update.effective_chat.id, uid, ChatPermissions.no_permissions(),
            until_date=int(until))
    except Exception as e:
        return await reply(update, f"Не вышло: {esc(e)}\n"
                                   "Проверь, что у бота есть право блокировать участников "
                                   "и что это не админ чата.")
    db.execute("INSERT OR REPLACE INTO mutes(user_id,name,until,reason,by_name,created) "
               "VALUES(?,?,?,?,?,?)", (uid, name, until, reason, disp(actor), time.time()))
    db.commit()
    await reply(update, f"🔇 {link(uid, name)} в муте на {fmt_minutes(minutes)}."
                        + (f"\nПричина: {esc(reason)}" if reason else ""))


@need("размут")
async def cmd_unmute(update, context):
    uid, name, rest, err = resolve_target(update, list(context.args or []))
    if err:
        return await reply(update, err)
    if not uid:
        return await reply(update, why_no_target(
            update, "Ответь на сообщение участника или укажи @юзернейм: размут"))
    try:
        await context.bot.restrict_chat_member(
            update.effective_chat.id, uid, ChatPermissions.all_permissions())
    except Exception as e:
        return await reply(update, f"Не вышло: {esc(e)}")
    db.execute("DELETE FROM mutes WHERE user_id=?", (uid,))
    db.commit()
    await reply(update, f"🔊 {link(uid, name)} размучен.")


@need("список мута")
async def cmd_mutelist(update, context):
    db.execute("DELETE FROM mutes WHERE until<?", (time.time(),))
    db.commit()
    rows = db.execute("SELECT * FROM mutes ORDER BY until").fetchall()
    if not rows:
        return await reply(update, "Сейчас в муте никого нет 🔊")
    lines = ["🔇 <b>Список мута</b>"]
    for i, r in enumerate(rows, 1):
        left = int((r["until"] - time.time()) // 60) + 1
        lines.append(f"{i}. {link(r['user_id'], r['name'])} — осталось {fmt_minutes(left)}\n"
                     f"    причина: {esc(r['reason'] or 'не указана')} · выдал: {esc(r['by_name'])}")
    await reply(update, "\n".join(lines))


@need("бан")
async def cmd_ban(update, context):
    uid, name, rest, err = resolve_target(update, list(context.args or []))
    if err:
        return await reply(update, err)
    if not uid:
        return await reply(update, why_no_target(
            update, "Ответь на сообщение участника или укажи @юзернейм: бан"))
    if not can_act_on(update.effective_user, uid):
        return await reply(update, "Нельзя: у этого участника ранг не ниже твоего.")
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, uid)
        db.execute("DELETE FROM mutes WHERE user_id=?", (uid,))
        db.commit()
        await reply(update, f"⛔ {link(uid, name)} забанен.")
    except Exception as e:
        await reply(update, f"Не вышло: {esc(e)}")


@need("разбан")
async def cmd_unban(update, context):
    uid, name, rest, err = resolve_target(update, list(context.args or []))
    if err:
        return await reply(update, err)
    if not uid:
        return await reply(update, why_no_target(
            update, "Ответь на сообщение или укажи id / @юзернейм: разбан 123456789"))
    try:
        await context.bot.unban_chat_member(update.effective_chat.id, uid, only_if_banned=True)
        await reply(update, f"✅ {link(uid, name)} разбанен.")
    except Exception as e:
        await reply(update, f"Не вышло: {esc(e)}")


@need("тег")
async def cmd_tag(update, context):
    uid, name, rest, err = resolve_target(update, list(context.args or []))
    if err:
        return await reply(update, err)
    if not uid:
        return await reply(update, why_no_target(
            update, "Ответь на сообщение участника: тег Текст тега"))
    tag = " ".join(rest).strip()[:30]
    if not tag:
        return await reply(update, "Напиши текст тега: тег Текст")
    if not urow(uid):
        return await reply(update, "Этот участник ещё не писал в чат.")
    db.execute("UPDATE users SET tag=? WHERE user_id=?", (tag, uid))
    db.commit()
    await reply(update, f"🏷 Тег для {esc(name)}: <b>{esc(tag)}</b>")


@need("снять тег")
async def cmd_untag(update, context):
    uid, name, rest, err = resolve_target(update, list(context.args or []))
    if err:
        return await reply(update, err)
    if not uid:
        return await reply(update, why_no_target(
            update, "Ответь на сообщение участника: снять тег"))
    db.execute("UPDATE users SET tag='' WHERE user_id=?", (uid,))
    db.commit()
    await reply(update, f"Тег у {esc(name)} снят.")


@need("статистика")
async def cmd_stat(update, context):
    d, wk = today(), week_start()
    one = lambda q, *a: db.execute(q, a).fetchone()[0]
    msgs_d = one("SELECT COALESCE(SUM(cnt),0) FROM daily WHERE day=?", d)
    msgs_w = one("SELECT COALESCE(SUM(cnt),0) FROM daily WHERE day>=? AND day<=?", wk, d)
    act_d = one("SELECT COUNT(*) FROM daily WHERE day=? AND cnt>0", d)
    act_w = one("SELECT COUNT(DISTINCT user_id) FROM daily WHERE day>=? AND day<=? AND cnt>0", wk, d)
    known = one("SELECT COUNT(*) FROM users")
    reg = one("SELECT COUNT(*) FROM users WHERE registered=1 AND total>0")
    rows = top_rows(wk, d, 5)
    await reply(update,
                f"📈 <b>Активность чата</b>\n"
                f"Сегодня: {msgs_d} сообщ., активных: {act_d}\n"
                f"За 7 дней: {msgs_w} сообщ., активных: {act_w}\n"
                f"Всего участников в базе: {known}, в созыве: {reg}\n\n"
                f"<b>Топ-5 недели</b>\n" + (fmt_top(rows) if rows else "—"))


@need("слова дня")
async def cmd_topwords(update, context):
    rows = db.execute("SELECT word, cnt FROM words WHERE day=? ORDER BY cnt DESC LIMIT 15",
                      (today(),)).fetchall()
    if not rows:
        return await reply(update, "Пока мало данных.")
    await reply(update, "💬 <b>О чём говорят сегодня</b>\n" +
                ", ".join(f"{esc(r['word'])} ({r['cnt']})" for r in rows))


@need("итоги")
async def cmd_award(update, context):
    await send_summary(context.bot, today(), False)


@need("запустить вопрос")
async def cmd_question(update, context):
    await post_question(context.bot)


@need("запустить викторину")
async def cmd_quiz(update, context):
    await post_quiz(context.bot)


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


_rp_cats = None
RP_UA = {"User-Agent": "clavekbot/1.0 (telegram chat bot)"}


async def rp_gif_url(category):
    """Случайная гифка категории с nekos.best или None."""
    import httpx
    global _rp_cats
    try:
        async with httpx.AsyncClient(timeout=10, headers=RP_UA) as c:
            if _rp_cats is None:
                r = await c.get("https://nekos.best/api/v2/endpoints")
                data = r.json()
                _rp_cats = data if isinstance(data, dict) else {}
            if _rp_cats:
                info = _rp_cats.get(category)
                if info is None:
                    return None
                if isinstance(info, dict) and info.get("format") not in (None, "gif"):
                    return None
            r = await c.get(f"https://nekos.best/api/v2/{category}")
            return r.json()["results"][0]["url"]
    except Exception as e:
        print("RP: не удалось получить гифку:", repr(e)[:150])
        return None


def local_rp_files(action):
    """Свои файлы из папки rp: «обнять.gif», «обнять_2.jpg», «отн_поцелуй_1.mp4»."""
    stem = action.replace(":", "_")
    out = []
    for folder in (os.path.join(BASE, RP_DIR), BASE):     # папка rp или рядом с bot.py
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        for fn in names:
            base, ext = os.path.splitext(fn)
            if ext.lower() not in (".gif", ".mp4", ".jpg", ".jpeg", ".png", ".webp"):
                continue
            if base == stem or base.startswith(stem + "_"):
                out.append(os.path.join(folder, fn))
    random.shuffle(out)
    return out


async def send_with_pic(bot, chat_id, text, actions, reply_to=None, api_cat=None,
                        markup=None, gif_query=None):
    """Картинка к сообщению. Порядок: свои картинки из базы -> файлы из папки rp ->
    гифка с nekos.best -> просто текст."""
    rp = ReplyParameters(message_id=reply_to, allow_sending_without_reply=True) if reply_to else None

    async def send(kind, media):
        kw = dict(caption=text, parse_mode=HTML, reply_parameters=rp, reply_markup=markup)
        if kind == "animation":
            return await bot.send_animation(chat_id, media, **kw)
        if kind == "video":
            return await bot.send_video(chat_id, media, **kw)
        if kind == "photo":
            return await bot.send_photo(chat_id, media, **kw)
        return await bot.send_document(chat_id, media, **kw)

    for action in actions:
        rows = db.execute("SELECT kind, file_id FROM rp_media WHERE action=?", (action,)).fetchall()
        if rows:
            r = random.choice(rows)
            try:
                return await send(r["kind"], r["file_id"])
            except Exception as e:
                print("Картинка из базы не отправилась:", repr(e)[:150])
    for action in actions:
        for p in local_rp_files(action):
            ext = os.path.splitext(p)[1].lower()
            try:
                with open(p, "rb") as f:
                    return await send("animation" if ext in (".gif", ".mp4") else "photo", f)
            except Exception as e:
                print("Файл из rp не отправился:", p, repr(e)[:150])
    if gif_query:
        url = await giphy_url(gif_query)
        if url:
            try:
                return await send("animation", url)
            except Exception as e:
                print("Giphy: гифка не ушла:", repr(e)[:150])
    if api_cat:
        url = await rp_gif_url(api_cat)
        if url:
            try:
                return await send("animation", url)
            except Exception as e:
                print("RP: гифка по ссылке не ушла:", repr(e)[:150])
                try:
                    import httpx
                    from io import BytesIO
                    async with httpx.AsyncClient(timeout=20, headers=RP_UA) as c:
                        data = (await c.get(url)).content
                    return await send("animation", BytesIO(data))
                except Exception as e2:
                    print("RP: и файлом не ушла:", repr(e2)[:150])
    return await bot.send_message(chat_id, text, parse_mode=HTML, reply_markup=markup,
                                  link_preview_options=NOPREV, reply_parameters=rp)


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


# ============================ ОТНОШЕНИЯ (искры) ============================
REL_START, REL_DAILY_CAP, REL_DATE_GAIN = 100, 300, 80     # искры: старт, лимит в сутки с действий, свидание
REL_ASK_SEC = 120                                           # сколько живёт предложение (2 минуты)
SPARK_RATE = 2                                              # 1 монета = 2 искры
KID_COST, KIDS_MAX = 300, 4
REL_TIME = (10, 15)            # когда раз в день списывать содержание
LEVELS = [(0, "Первые искры"), (300, "Тёплые чувства"), (800, "Крепкая связь"), (1500, "Горячая любовь"),
          (2500, "Родные души"), (4000, "Вместе навсегда"), (6000, "Пара мечты"), (9000, "Легенда чата")]
REL_GAIN = {"поцеловать": 50, "обнять": 30, "обнять крепко": 40, "взять за руку": 25,
            "погладить": 20, "покормить": 15, "пощекотать": 15, "похвалить": 15, "помахать": 5}
REL_PIC = {"поцеловать": "поцелуй", "обнять": "объятие", "обнять крепко": "объятие"}
REL_EVENTS = {
    "предложение": "кто-то предложил отношения",
    "пара": "предложение принято, пара создана",
    "поцелуй": "партнёры целуются (команда «поцеловать»)",
    "объятие": "партнёры обнимаются (команды «обнять»)",
    "свидание": "команда «свидание»",
    "скучаю": "напоминание: искры на исходе",
    "расставание": "расставание",
    "предложение брака": "кто-то предложил брак",
    "свадьба": "свадьба",
    "развод": "развод",
    "годовщина": "годовщина свадьбы",
    "ребёнок": "рождение ребёнка",
    "обида": "кто-то обиделся",
}
REL_TXT_PROPOSE = [
    "💌 {a} признаётся {b} в чувствах и предлагает быть вместе.\nСердце бьётся чаще: нажмите «Да» или «Нет». Запрос действителен 2 минуты.",
    "💘 {a} протягивает руку и сердце: {b}, станем парой?\nОтвет ждут 2 минуты: кнопка «Да», «Нет» или слова «принять» и «отказать».",
    "🌹 Для {b} есть особое послание: {a} мечтает встречаться!\nУ вас 2 минуты, чтобы ответить: «Да» или «Нет».",
]
REL_TXT_ACCEPT = [
    "💞 Два сердца нашли друг друга: {a} и {b} теперь пара!",
    "💖 Свершилось! {a} и {b} вместе. Пусть это будет красивая история.",
    "🌷 {a} и {b} теперь вместе. Берегите друг друга и не забывайте про свидания.",
]
REL_TXT_DECLINE = [
    "💔 {b} мягко отказал{ea} {a}. Бывает, зато теперь всё ясно.",
    "🥀 Сердце {a} дрогнуло: {b} ответил{ea} «нет». Но всё ещё впереди.",
    "🌧 {b} пока не готов{ea} к отношениям с {a}. Дружба тоже красиво.",
]
PROPOSE = {"предложить отношения", "предложить встречаться", "встречаться"}
ACCEPT = {"принять", "принимаю", "согласна", "согласен"}
DECLINE = {"отказать", "отказываюсь", "отказаться"}
LEAVE = {"расстаться", "расстаёмся", "расстаемся", "порвать отношения", "расторгнуть"}
STATUS_SELF = {"моя пара", "мои отношения", "отн я", "профиль пары"}
STATUS_OTHER = {"пара", "отношения"}   # только ответом на сообщение человека
DATE_WORDS = {"свидание", "пойти на свидание"}
TOPPAIRS = {"топ пар"}
LIST_WORDS = {"список пар", "все пары"}
OFFEND_WORDS = {"обида", "обидеться", "я обиделся", "я обиделась"}
KID_WORDS = {"завести ребёнка", "завести ребенка", "родить ребёнка"}
KIDS_LIST_WORDS = {"дети", "мои дети", "наши дети"}
SONS = ["Артём", "Матвей", "Лев", "Тимур", "Ян", "Макс", "Платон", "Мирон"]
DAUGHTERS = ["Аня", "Соня", "Мия", "Ева", "Алиса", "Вера", "Лея", "Майя"]

# перевод старых значений «любви» (0 до 100) в искры, один раз
if not state_get("sparks_v1"):
    db.execute("UPDATE pairs SET love=love*5")
    db.commit()
    state_set("sparks_v1", "1")


def ea(uid):
    """окончание по полу: '' (м), 'а' (ж) или '(а)', если пол не указан"""
    r = urow(uid)
    g = (r["gender"] if r and "gender" in r.keys() else "") or ""
    return "" if g == "м" else "а" if g == "ж" else "(а)"


def pair_of(uid):
    return db.execute("SELECT * FROM pairs WHERE a=? OR b=?", (uid, uid)).fetchone()


def pair_by_id(pid):
    return db.execute("SELECT * FROM pairs WHERE id=?", (pid,)).fetchone()


def partner_of(row, uid):
    return row["b"] if row["a"] == uid else row["a"]


def uname(uid):
    r = urow(uid)
    return r["name"] if r else str(uid)


def spark_level(n):
    lvl = 1
    for i, (thr, _) in enumerate(LEVELS, 1):
        if n >= thr:
            lvl = i
    return lvl


def kids_of(pid):
    return db.execute("SELECT * FROM kids WHERE pair_id=? ORDER BY id", (pid,)).fetchall()


def upkeep(row):
    base = 10 * spark_level(row["love"])
    base *= 1 + 0.1 * len(kids_of(row["id"]))
    if row["married_at"]:
        base *= 0.7
    return max(5, int(base))


def spark_line(row):
    lvl = spark_level(row["love"])
    return (f"🔥 Искры: <b>{row['love']}</b> · {LEVELS[lvl - 1][1]} (ур. {lvl})\n"
            f"📈 Расход в сутки: {upkeep(row)}")


def spark_add(pid, delta, reason, who=""):
    row = pair_by_id(pid)
    if not row:
        return 0
    new = max(0, row["love"] + delta)
    db.execute("UPDATE pairs SET love=? WHERE id=?", (new, pid))
    db.execute("INSERT INTO spark_log(pair_id,delta,reason,who,ts,bal) VALUES(?,?,?,?,?,?)",
               (pid, new - row["love"], reason, who, time.time(), new))
    db.commit()
    return new


def rel_add(uid, other, amount, reason="действие"):
    """Начислить искры за действие, если uid и other пара -> (начислено, всего) или None."""
    row = pair_of(uid)
    if not row or partner_of(row, uid) != other:
        return None
    d = today()
    gain = row["gain"] if row["gain_day"] == d else 0
    add = max(0, min(amount, REL_DAILY_CAP - gain))
    db.execute("UPDATE pairs SET gain=?, gain_day=?, last_action=?, actions=actions+1 WHERE id=?",
               (gain + add, d, time.time(), row["id"]))
    db.commit()
    new = spark_add(row["id"], add, reason, uname(uid)) if add else row["love"]
    return add, new


def fmt_dur(sec):
    days = int(sec // 86400)
    if days >= 30:
        return f"{days // 30} мес. {days % 30} д."
    if days >= 1:
        return f"{days} д. {int(sec % 86400 // 3600)} ч."
    return f"{int(sec // 3600)} ч. {int(sec % 3600 // 60)} мин."


def offended_block(me_id, other_id):
    row = pair_of(me_id)
    return bool(row and partner_of(row, me_id) == other_id and row["offended"]
                and row["offended"] != me_id)


def delete_pair(pid):
    db.execute("DELETE FROM pairs WHERE id=?", (pid,))
    db.execute("DELETE FROM kids WHERE pair_id=?", (pid,))
    db.commit()


def pair_profile_text(row, uid):
    p = partner_of(row, uid)
    kids = kids_of(row["id"])
    sons = sum(1 for k in kids if k["gender"] == "м")
    me_r, p_r = urow(uid), urow(p)
    hs = [HOUSES[r["house"]][0] for r in (me_r, p_r) if r and r["house"] in HOUSES]
    pets = db.execute("SELECT * FROM pets WHERE owner IN (?,?)", (uid, p)).fetchall()
    lines = [f"❤️ Твоя половинка: {link(p, uname(p))}", f"🆔 ID отношений: {row['id']}"]
    if row["married_at"]:
        lines.append(f"💍 В браке с {fmt_when(row['married_at'])}")
    lines.append(spark_line(row))
    lines.append(f"🕙 Длительность: {fmt_dur(time.time() - row['since'])}")
    if hs:
        lines.append("🏠 Дом: " + ", ".join(hs[:1]))
    if pets:
        lines.append("🐾 Питомцы: " + ", ".join(esc(x["name"]) for x in pets))
    lines.append(f"👶 Сыновья: {sons}\n👩 Дочери: {len(kids) - sons}")
    lines.append(f"🎯 Действий: {row['actions'] or 0}")
    if row["offended"]:
        lines.append(f"🙁 {esc(uname(row['offended']))} обиделся(ась)")
    return "\n".join(lines)


def pair_kb(uid):
    B = InlineKeyboardButton
    return InlineKeyboardMarkup([
        [B("💰 Купить искры", callback_data=f"rel:menu:buy:{uid}"), B("🏠 Дом", callback_data=f"rel:menu:house:{uid}")],
        [B("🐾 Питомцы", callback_data=f"rel:menu:pets:{uid}"), B("👶 Дети", callback_data=f"rel:menu:kids:{uid}")],
        [B("📊 История", callback_data=f"rel:menu:hist:{uid}")]])


async def rel_answer(bot, chat_id, me_id, accept, reply_to=None):
    """Ответ на предложение отношений (слова или кнопки). True, если предложение было."""
    pr = db.execute("SELECT * FROM proposals WHERE to_id=?", (me_id,)).fetchone()
    if not pr:
        return False
    db.execute("DELETE FROM proposals WHERE to_id=?", (me_id,))
    db.commit()
    a = pr["from_id"]

    async def out(text, pic=None):
        await send_with_pic(bot, chat_id, text, ["отн:" + pic] if pic else [], reply_to=reply_to)

    if time.time() - pr["created"] > REL_ASK_SEC:
        await out("⌛ Время на ответ вышло (2 минуты), предложение отменено.")
        return True
    if not accept:
        await out(random.choice(REL_TXT_DECLINE).format(a=link(a, uname(a)), b=link(me_id, uname(me_id)),
                                                         ea=ea(me_id)))
    elif pair_of(a) or pair_of(me_id):
        await out("Кто-то из вас уже в отношениях.")
    else:
        cur = db.execute("INSERT INTO pairs(a,b,love,since,last_action) VALUES(?,?,?,?,?)",
                         (a, me_id, REL_START, time.time(), time.time()))
        db.execute("INSERT INTO spark_log(pair_id,delta,reason,who,ts,bal) VALUES(?,?,?,?,?,?)",
                   (cur.lastrowid, REL_START, "начало отношений", "", time.time(), REL_START))
        db.commit()
        txt = (random.choice(REL_TXT_ACCEPT).format(a=link(a, uname(a)), b=link(me_id, uname(me_id))) +
               f"\n🔥 Искры: {REL_START} (общий баланс пары, они тратятся раз в сутки)\n"
               f"Пополняйте искры: «поцеловать», «обнять», «свидание», задания на работе. "
               f"Профиль: «моя пара»")
        if not await send_certificate(bot, chat_id, pair_of(me_id), False, reply_to, caption=txt):
            await out(txt, "пара")
    return True


async def rel_leave_ask(update, context):
    me = update.effective_user
    row = pair_of(me.id)
    if not row:
        return False
    p = partner_of(row, me.id)
    cost = f"\nРазвод в браке стоит {DIVORCE_COST} 🪙." if row["married_at"] else ""
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("💔 Расторгнуть", callback_data=f"rel:leave:{me.id}"),
                                InlineKeyboardButton("Отмена", callback_data=f"rel:cancel:{me.id}")]])
    await send_with_pic(context.bot, update.effective_chat.id,
                        f"💔 {link(me.id, disp(me))}, вы действительно хотите расторгнуть отношения с "
                        f"{link(p, uname(p))}? Это действие навсегда, вместе с парой пропадут искры и дети."
                        + cost, [], reply_to=update.effective_message.message_id, markup=kb)
    return True


async def rel_leave_do(bot, chat_id, uid, reply_to=None):
    row = pair_of(uid)
    if not row:
        return False
    p = partner_of(row, uid)
    married = bool(row["married_at"])
    if married:
        if coins_of(uid) < DIVORCE_COST:
            await send_with_pic(bot, chat_id, f"Развод стоит {DIVORCE_COST} 🪙, а у тебя {coins_of(uid)}.", [],
                                reply_to=reply_to)
            return True
        give_coins(uid, -DIVORCE_COST)
    delete_pair(row["id"])
    await send_with_pic(bot, chat_id,
                        f"💔 {link(p, uname(p))}, к сожалению, {link(uid, uname(uid))} решил{ea(uid)} "
                        f"расторгнуть ваши отношения" + (f" (−{DIVORCE_COST} 🪙)." if married else "."),
                        ["отн:развод" if married else "отн:расставание"], reply_to=reply_to,
                        api_cat="cry")
    return True


async def rel_offend(update, context):
    me = update.effective_user
    row = pair_of(me.id)
    if not row:
        return False
    p = partner_of(row, me.id)
    if row["offended"] == me.id:
        db.execute("UPDATE pairs SET offended=0 WHERE id=?", (row["id"],))
        db.commit()
        txt = f"😊 {link(p, uname(p))}, твоя половинка больше не обижается. Все действия снова доступны!"
    elif row["offended"]:
        txt = "🙁 Ваша половинка уже обижена на вас, сначала помиритесь."
    else:
        db.execute("UPDATE pairs SET offended=? WHERE id=?", (me.id, row["id"]))
        db.commit()
        txt = (f"🙁 {link(p, uname(p))}, твоя половинка обиделась. Все действия будут временно заблокированы, "
               f"пока она не передумает.\n💭 {link(me.id, disp(me))}, чтобы перестать обижаться, "
               f"введите эту команду ещё раз.")
    await send_with_pic(context.bot, update.effective_chat.id, txt, ["отн:обида"],
                        reply_to=update.effective_message.message_id)
    return True


async def rel_kid_ask(update, context):
    me = update.effective_user
    row = pair_of(me.id)
    if not row or not row["married_at"]:
        return await reply(update, "Дети бывают только в браке 💍. Сначала «предложить брак».")
    if len(kids_of(row["id"])) >= KIDS_MAX:
        return await reply(update, f"В семье уже {KIDS_MAX} детей, это максимум 👨‍👩‍👧‍👦")
    if row["love"] < KID_COST + 100:
        return await reply(update, f"Ребёнок стоит {KID_COST} искр, а в запасе должно остаться ещё 100. "
                                   f"Сейчас у пары {row['love']}. Пополните искры.")
    p = partner_of(row, me.id)
    state_set(f"kidreq:{p}", f"{me.id}:{time.time()}")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("👶 Да", callback_data=f"rel:kidyes:{p}"),
                                InlineKeyboardButton("Нет", callback_data=f"rel:kidno:{p}")]])
    await send_with_pic(context.bot, update.effective_chat.id,
                        f"👶 {link(me.id, disp(me))} мечтает о ребёнке! {link(p, uname(p))}, вы согласны? "
                        f"(2 минуты, стоит {KID_COST} искр)", [], reply_to=update.effective_message.message_id,
                        markup=kb)


async def rel_kid_born(bot, chat_id, uid, reply_to=None):
    row = pair_of(uid)
    req = state_get(f"kidreq:{uid}")
    state_del(f"kidreq:{uid}")
    if not row or not req or time.time() - float(req.split(":")[1]) > REL_ASK_SEC:
        return "Время вышло или запрос уже не актуален."
    if not row["married_at"] or len(kids_of(row["id"])) >= KIDS_MAX or row["love"] < KID_COST + 100:
        return "Сейчас это невозможно."
    g = random.choice(["м", "ж"])
    name = random.choice(SONS if g == "м" else DAUGHTERS)
    db.execute("INSERT INTO kids(pair_id,name,gender,born) VALUES(?,?,?,?)", (row["id"], name, g, time.time()))
    db.commit()
    spark_add(row["id"], -KID_COST, "рождение ребёнка", uname(uid))
    a, b = row["a"], row["b"]
    await send_with_pic(bot, chat_id,
                        f"👶🎉 В семье пополнение! У {link(a, uname(a))} и {link(b, uname(b))} "
                        f"родил{'ся сын' if g == 'м' else 'ась дочь'}: <b>{esc(name)}</b>\n"
                        f"Переименовать: «назвать ребёнка Имя». Расход искр вырос на 10%.",
                        ["отн:ребёнок"], reply_to=reply_to, api_cat="happy")
    return None


async def rel_kids_list(update, context):
    row = pair_of(update.effective_user.id)
    kids = kids_of(row["id"]) if row else []
    if not kids:
        return await reply(update, "Детей пока нет. В браке: «завести ребёнка» 👶")
    lines = ["👨‍👩‍👧‍👦 <b>Дети</b>"]
    for k in kids:
        lines.append(f"{'👦' if k['gender'] == 'м' else '👧'} {esc(k['name'])}, {fmt_dur(time.time() - k['born'])}")
    await reply(update, "\n".join(lines))


async def rel_kid_rename(update, context, new):
    row = pair_of(update.effective_user.id)
    kids = kids_of(row["id"]) if row else []
    new = new.strip()[:20]
    if not kids:
        return await reply(update, "У вас нет детей.")
    if not new:
        return await reply(update, "Напиши имя: «назвать ребёнка Артём»")
    db.execute("UPDATE kids SET name=? WHERE id=?", (new, kids[-1]["id"]))
    db.commit()
    await reply(update, f"✏️ Теперь младшего зовут <b>{esc(new)}</b>")


def hist_text(pid):
    rows = db.execute("SELECT * FROM spark_log WHERE pair_id=? ORDER BY id DESC LIMIT 10", (pid,)).fetchall()
    row = pair_by_id(pid)
    if not rows:
        return "История пока пуста."
    lines = [f"📊 <b>История искр</b>\n🔥 Текущий баланс: {row['love']}\n"]
    for r in rows:
        mark = "📈" if r["delta"] >= 0 else "📉"
        who = f" • {esc(r['who'])}" if r["who"] else ""
        lines.append(f"{mark} {r['delta']:+d} | {esc(r['reason'])}{who}\n   {fmt_when(r['ts'])} | баланс {r['bal']}")
    return "\n".join(lines)


def top_text(cat):
    if cat == "act":
        rows = db.execute("SELECT * FROM pairs ORDER BY actions DESC LIMIT 10").fetchall()
        val = lambda r: f"{r['actions'] or 0} действий"
        title = "🔄 Общая активность"
    elif cat == "sp":
        rows = db.execute("SELECT * FROM pairs ORDER BY love DESC LIMIT 10").fetchall()
        val = lambda r: f"{r['love']} 🔥"
        title = "🔥 Искры"
    else:
        rows = db.execute("SELECT * FROM pairs ORDER BY since ASC LIMIT 10").fetchall()
        val = lambda r: fmt_dur(time.time() - r["since"])
        title = "⏳ Длительность"
    if not rows:
        return "Пока нет ни одной пары 💔"
    return f"🏆 <b>Топ по «{title}»</b>\n\n" + "\n".join(
        f"{i}. {esc(uname(r['a']))} + {esc(uname(r['b']))} — {val(r)}" for i, r in enumerate(rows, 1))


def top_kb(uid):
    B = InlineKeyboardButton
    return InlineKeyboardMarkup([[B("🔄 Общая активность", callback_data=f"rel:top:act:{uid}")],
                                 [B("🔥 Искры", callback_data=f"rel:top:sp:{uid}")],
                                 [B("⏳ Длительность", callback_data=f"rel:top:dur:{uid}")]])


async def handle_relation(update, context, low):
    clean = re.sub(r"[!.?,]+$", "", low).strip()
    if not (clean in PROPOSE or clean in ACCEPT or clean in DECLINE or clean in LEAVE
            or clean in STATUS_SELF or clean in STATUS_OTHER or clean in DATE_WORDS
            or clean in TOPPAIRS or clean in LIST_WORDS):
        return False
    msg, me, chat = update.effective_message, update.effective_user, update.effective_chat
    bot = context.bot

    async def say(text, pic=None, markup=None):
        await send_with_pic(bot, chat.id, text, ["отн:" + pic] if pic else [], reply_to=msg.message_id,
                            markup=markup)

    if clean in PROPOSE:
        other = target_user(update)
        if not other or other.id == me.id:
            await say("Ответь этими словами на сообщение человека: «предложить отношения» 💌")
        elif pair_of(me.id):
            await say("Ты уже в отношениях. Сначала «расстаться».")
        elif pair_of(other.id):
            await say(f"У {esc(disp(other))} уже есть пара.")
        else:
            touch(other)
            db.execute("INSERT OR REPLACE INTO proposals(to_id,from_id,created,msg_id) VALUES(?,?,?,?)",
                       (other.id, me.id, time.time(), msg.message_id))
            db.commit()
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("💖 Да", callback_data=f"rel:yes:{other.id}"),
                                        InlineKeyboardButton("💔 Нет", callback_data=f"rel:no:{other.id}")]])
            await say(random.choice(REL_TXT_PROPOSE).format(a=link(me.id, disp(me)),
                                                            b=link(other.id, disp(other))),
                      "предложение", kb)
        return True

    if clean in ACCEPT or clean in DECLINE:
        return await rel_answer(bot, chat.id, me.id, clean in ACCEPT, msg.message_id)

    if clean in LEAVE:
        return await rel_leave_ask(update, context)

    if clean in STATUS_SELF or clean in STATUS_OTHER:
        u = target_user(update) if clean in STATUS_OTHER else None
        if clean in STATUS_OTHER and not u:
            return False
        u = u or me
        row = pair_of(u.id)
        if not row:
            await say("У тебя нет пары. Ответь на сообщение человека: «предложить отношения»."
                      if u.id == me.id else f"У {esc(disp(u))} нет пары.")
        else:
            await say(pair_profile_text(row, u.id), None, pair_kb(u.id) if u.id == me.id else None)
        return True

    if clean in DATE_WORDS:
        row = pair_of(me.id)
        if not row:
            return False
        p = partner_of(row, me.id)
        if offended_block(me.id, p):
            await say("🙁 Ваша половинка обижена на вас, все действия недоступны.")
        elif row["date_day"] == today():
            await say("Сегодня вы уже ходили на свидание 🌹")
        else:
            await say("🌹 Куда пойдёте на свидание? Платит тот, кто выбирает место.", None, date_kb(me.id))
        return True

    if clean in LIST_WORDS:
        rows = db.execute("SELECT * FROM pairs ORDER BY since LIMIT 30").fetchall()
        if not rows:
            await say("Пока нет ни одной пары 💔")
        else:
            await say("💞 <b>Пары чата</b>\n" + "\n".join(
                f"{i}. {'💍' if r['married_at'] else '❤️'} {esc(uname(r['a']))} + {esc(uname(r['b']))} "
                f"({fmt_dur(time.time() - r['since'])})" for i, r in enumerate(rows, 1)))
        return True

    await say("📊 Выберите категорию для топа отношений:", None, top_kb(me.id))
    return True


async def on_rel_btn(update, context):
    q = update.callback_query
    p = (q.data or "").split(":")
    if len(p) < 3 or p[0] != "rel":
        return await q.answer()
    kind = p[1]
    uid = int(p[-1]) if p[-1].isdigit() else 0
    if q.from_user.id != uid:
        return await q.answer("Это кнопка для другого человека 🙂", show_alert=True)
    chat = q.message.chat.id
    mid = q.message.message_id
    bot = context.bot
    shim = SimpleNamespace(effective_user=q.from_user, effective_chat=q.message.chat,
                                 effective_message=q.message)

    async def drop_markup():
        try:
            await q.edit_message_reply_markup(None)
        except Exception:
            pass

    if kind in ("yes", "no"):
        touch(q.from_user)
        ok = await rel_answer(bot, chat, uid, kind == "yes", mid)
        await q.answer("Готово" if ok else "Предложение уже неактуально")
        return await drop_markup()
    if kind == "leave":
        await q.answer()
        await drop_markup()
        return await rel_leave_do(bot, chat, uid, mid)
    if kind == "cancel":
        await q.answer("Отменено")
        return await drop_markup()
    if kind in ("kidyes", "kidno"):
        await drop_markup()
        if kind == "kidno":
            state_del(f"kidreq:{uid}")
            return await q.answer("Отказано")
        err = await rel_kid_born(bot, chat, uid, mid)
        return await q.answer(err or "Поздравляем!", show_alert=bool(err))
    if kind == "top":
        await q.answer()
        try:
            await q.edit_message_text(top_text(p[2]), parse_mode=HTML,
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
                                          "< Назад", callback_data=f"rel:topback:{uid}")]]))
        except Exception:
            pass
        return
    if kind == "topback":
        await q.answer()
        try:
            await q.edit_message_text("📊 Выберите категорию для топа отношений:", reply_markup=top_kb(uid))
        except Exception:
            pass
        return
    row = pair_of(uid)
    if not row:
        return await q.answer("У тебя нет пары", show_alert=True)
    if kind == "menu":
        what = p[2]
        await q.answer()
        if what == "buy":
            B = InlineKeyboardButton
            kb = InlineKeyboardMarkup([[B(f"{c} 🪙 → {c * SPARK_RATE} искр", callback_data=f"rel:buy2:{c}:{uid}")]
                                       for c in (50, 200, 500)])
            return await send_with_pic(bot, chat, f"💰 Купить искры. Курс: 1 🪙 = {SPARK_RATE} искр. "
                                                  f"У тебя {coins_of(uid)} 🪙", [], reply_to=mid, markup=kb)
        if what == "house":
            return await life_houses(shim, context)
        if what == "pets":
            return await life_pet_shop(shim, context)
        if what == "kids":
            return await rel_kids_list(shim, context)
        if what == "hist":
            return await send_with_pic(bot, chat, hist_text(row["id"]), [], reply_to=mid)
        return
    if kind == "buy2":
        c = int(p[2])
        if c not in (50, 200, 500):
            return await q.answer()
        if coins_of(uid) < c:
            return await q.answer(f"Не хватает монет: нужно {c}, у тебя {coins_of(uid)}", show_alert=True)
        give_coins(uid, -c)
        new = spark_add(row["id"], c * SPARK_RATE, "покупка искр", uname(uid))
        await q.answer("Готово")
        await drop_markup()
        return await send_with_pic(bot, chat, f"💰 {link(uid, uname(uid))} купил(а) {c * SPARK_RATE} искр "
                                              f"за {c} 🪙. Всего искр: {new}", [], reply_to=mid)
    await q.answer()


async def rel_daily(bot):
    """Раз в сутки: списываем содержание пар, предупреждаем и расторгаем, когда искры кончились."""
    for row in db.execute("SELECT * FROM pairs").fetchall():
        try:
            up = upkeep(row)
            new = row["love"] - up
            a, b = row["a"], row["b"]
            names = f"{link(a, uname(a))} и {link(b, uname(b))}"
            if new <= 0:
                if row["married_at"]:
                    new = 10
                else:
                    dur = fmt_dur(time.time() - row["since"])
                    delete_pair(row["id"])
                    await send_with_pic(bot, CHAT_ID,
                                        f"💔 Отношения между {names}, длившиеся {dur}, были завершены: "
                                        f"искры закончились.", ["отн:расставание"])
                    continue
            db.execute("UPDATE pairs SET love=? WHERE id=?", (new, row["id"]))
            db.execute("INSERT INTO spark_log(pair_id,delta,reason,who,ts,bal) VALUES(?,?,?,?,?,?)",
                       (row["id"], -up, "ежедневное содержание", "", time.time(), new))
            db.commit()
            nxt = upkeep(pair_by_id(row["id"]))
            if new < nxt and not row["married_at"]:
                await send_with_pic(
                    bot, CHAT_ID,
                    f"🚨 Отношения между {names} на грани распада! Осталось {new} искр, а для содержания "
                    f"нужно {nxt}. Срочно пополните искры («моя пара», кнопка «Купить искры» или "
                    f"«поцеловать», «свидание»), иначе отношения будут разрушены!", ["отн:скучаю"])
        except Exception:
            log.exception("rel_daily")


# ============================ МОНЕТЫ, МАГАЗИН, ЖАЛОБЫ ============================
COIN = "🪙"
BONUS_BASE = 20


def give_coins(uid, n):
    db.execute("UPDATE users SET coins=coins+? WHERE user_id=?", (n, uid))
    db.commit()


def coins_of(uid):
    r = urow(uid)
    return (r["coins"] or 0) if r else 0


@group_only
async def cmd_balance(update, context):
    u = target_user(update) or update.effective_user
    touch(u)
    r = urow(u.id)
    await reply(update, f"{COIN} Баланс {link(u.id, r['name'])}: <b>{r['coins'] or 0}</b>\n"
                        f"Монеты дают за сообщения (1 за каждые 10), квесты, викторину, дуэли, игры и «бонус».\n"
                        f"Потратить: «магазин»")


@group_only
async def cmd_bonus(update, context):
    uid = update.effective_user.id
    r = urow(uid)
    d = today()
    if r["bonus_day"] == d:
        return await reply(update, "Сегодняшний бонус уже получен. Приходи завтра 🎁")
    amount = BONUS_BASE + min(r["streak"] or 0, 30)
    db.execute("UPDATE users SET bonus_day=? WHERE user_id=?", (d, uid))
    db.commit()
    give_coins(uid, amount)
    await reply(update, f"🎁 Ежедневный бонус: <b>+{amount}</b> {COIN} "
                        f"(база {BONUS_BASE} + серия дней). Баланс: {coins_of(uid)}")


@group_only
async def cmd_topcoins(update, context):
    rows = db.execute("SELECT user_id,name,coins FROM users WHERE coins>0 "
                      "ORDER BY coins DESC LIMIT 10").fetchall()
    if not rows:
        return await reply(update, "Пока ни у кого нет монет. Пиши в чат и забирай «бонус» 🪙")
    medals = ["🥇", "🥈", "🥉"]
    lines = [f"{COIN} <b>Топ по монетам</b>"]
    for i, r in enumerate(rows):
        lines.append(f"{medals[i] if i < 3 else str(i + 1) + '.'} {link(r['user_id'], r['name'])} — {r['coins']}")
    await reply(update, "\n".join(lines))


@group_only
async def cmd_duels(update, context):
    u = target_user(update) or update.effective_user
    touch(u)
    r = urow(u.id)
    w, l = r["duel_w"] or 0, r["duel_l"] or 0
    lines = [f"⚔️ <b>Дуэли {esc(r['name'])}</b>: побед {w}, поражений {l}"
             + (f" ({round(100 * w / (w + l))}%)" if w + l else "")]
    top = db.execute("SELECT user_id,name,duel_w,duel_l FROM users WHERE duel_w>0 "
                     "ORDER BY duel_w DESC LIMIT 5").fetchall()
    if top:
        lines.append("\n🏆 <b>Лучшие дуэлянты</b>")
        for i, t in enumerate(top, 1):
            lines.append(f"{i}. {link(t['user_id'], t['name'])} — {t['duel_w']} поб. / {t['duel_l']} пор.")
    else:
        lines.append("Дуэлей ещё не было. Ответь «дуэль» на сообщение соперника")
    await reply(update, "\n".join(lines))


@group_only
async def cmd_shop(update, context):
    items = db.execute("SELECT * FROM shop_items WHERE active=1 ORDER BY id").fetchall()
    if not items:
        return await reply(update, "🛍 Магазин пока пуст. Админы добавят товары командой "
                                   "«добавить товар Название цена»")
    lines = [f"🛍 <b>Магазин подарков</b>\nТвой баланс: <b>{coins_of(update.effective_user.id)}</b> {COIN}\n"]
    for it in items:
        stock = "" if it["stock"] < 0 else f" · осталось {it['stock']}"
        lines.append(f"<b>{it['id']}.</b> {esc(it['name'])} — {it['price']} {COIN}{stock}")
    lines.append("\nКупить: «купить 1» (номер товара). Приз выдаёт владелец вручную")
    await reply(update, "\n".join(lines))


@group_only
async def cmd_buy(update, context):
    args = list(context.args or [])
    if not args or not args[0].isdigit():
        return await reply(update, "Напиши: «купить 1» (номер товара из «магазин»)")
    me = update.effective_user
    touch(me)
    it = db.execute("SELECT * FROM shop_items WHERE id=? AND active=1", (int(args[0]),)).fetchone()
    if not it:
        return await reply(update, "Нет такого товара. Список: «магазин»")
    if it["stock"] == 0:
        return await reply(update, "Товар закончился 😔")
    bal = coins_of(me.id)
    if bal < it["price"]:
        return await reply(update, f"Не хватает монет: нужно {it['price']}, у тебя {bal} {COIN}")
    db.execute("UPDATE users SET coins=coins-? WHERE user_id=?", (it["price"], me.id))
    if it["stock"] > 0:
        db.execute("UPDATE shop_items SET stock=stock-1 WHERE id=?", (it["id"],))
    cur = db.execute("INSERT INTO orders(user_id,name,item,price,created,status) VALUES(?,?,?,?,?, 'new')",
                     (me.id, disp(me), it["name"], it["price"], time.time()))
    db.commit()
    await reply(update, f"✅ {link(me.id, disp(me))} купил «{esc(it['name'])}» за {it['price']} {COIN}\n"
                        f"Заказ <b>#{cur.lastrowid}</b>. {owner_mention()}, нужно выдать приз 🎁\n"
                        f"Остаток: {coins_of(me.id)} {COIN}")


def _parse_item(args):
    """название... цена [остаток] -> (name, price, stock) или None"""
    a = list(args)
    stock = -1
    if len(a) >= 3 and a[-1].isdigit() and a[-2].isdigit():
        stock = int(a.pop())
    if len(a) >= 2 and a[-1].isdigit():
        price = int(a.pop())
        return " ".join(a)[:60], price, stock
    return None


@need("добавить товар")
async def cmd_item_add(update, context):
    p = _parse_item(context.args or [])
    if not p or p[1] < 1:
        return await reply(update, "Формат: добавить товар Мишка 500 (название, цена) "
                                   "или добавить товар Мишка 500 3 (ещё и количество)")
    name, price, stock = p
    cur = db.execute("INSERT INTO shop_items(name,price,stock,active) VALUES(?,?,?,1)", (name, price, stock))
    db.commit()
    await reply(update, f"✅ Товар <b>#{cur.lastrowid}</b> «{esc(name)}» — {price} {COIN}"
                        + ("" if stock < 0 else f", количество {stock}"))


@need("удалить товар")
async def cmd_item_del(update, context):
    a = list(context.args or [])
    if not a or not a[0].isdigit():
        return await reply(update, "Формат: удалить товар 1")
    db.execute("UPDATE shop_items SET active=0 WHERE id=?", (int(a[0]),))
    db.commit()
    await reply(update, f"🗑 Товар #{a[0]} убран из магазина")


@need("выдать монеты")
async def cmd_coins_give(update, context):
    uid, name, rest, err = resolve_target(update, list(context.args or []))
    if err:
        return await reply(update, err)
    nums = [x for x in rest if re.fullmatch(r"-?\d+", x)]
    if not uid or not nums:
        return await reply(update, "Формат: выдать монеты @юзернейм 100 (или ответом: выдать монеты 100; "
                                   "отрицательное число забирает)")
    if not urow(uid):
        return await reply(update, "Этого участника нет в базе бота.")
    n = int(nums[0])
    give_coins(uid, n)
    await reply(update, f"{COIN} {link(uid, name)}: {'+' if n >= 0 else ''}{n}. Баланс: {coins_of(uid)}")


@need("заказы")
async def cmd_orders(update, context):
    rows = db.execute("SELECT * FROM orders WHERE status='new' ORDER BY id LIMIT 30").fetchall()
    if not rows:
        return await reply(update, "Невыданных заказов нет ✅")
    lines = ["📦 <b>Невыданные заказы</b>"]
    for r in rows:
        lines.append(f"#{r['id']} · {link(r['user_id'], r['name'])} · {esc(r['item'])} ({r['price']} {COIN})")
    lines.append("\nПосле выдачи: «выдан 5»")
    await reply(update, "\n".join(lines))


@need("выдан")
async def cmd_order_done(update, context):
    a = list(context.args or [])
    if not a or not a[0].isdigit():
        return await reply(update, "Формат: выдан 5 (номер заказа из «заказы»)")
    r = db.execute("SELECT * FROM orders WHERE id=?", (int(a[0]),)).fetchone()
    if not r:
        return await reply(update, "Нет такого заказа.")
    db.execute("UPDATE orders SET status='done' WHERE id=?", (r["id"],))
    db.commit()
    await reply(update, f"✅ Заказ #{r['id']} выдан: {link(r['user_id'], r['name'])} получил «{esc(r['item'])}»")


# ---------- жалобы ----------
def _msg_link(chat_id, msg_id):
    s = str(chat_id)
    return f"https://t.me/c/{s[4:]}/{msg_id}" if s.startswith("-100") else ""


@group_only
async def cmd_report(update, context):
    msg = update.effective_message
    me = update.effective_user
    tm = msg.reply_to_message
    if not tm or not tm.from_user:
        return await reply(update, "Ответь командой «репорт» на сообщение нарушителя. "
                                   "Причину можно дописать: «репорт спам»")
    t = tm.from_user
    if t.is_bot or t.id == me.id:
        return await reply(update, "На это сообщение жаловаться нельзя.")
    if rank_of_id(t.id) > 0 or is_owner(t):
        return await reply(update, "Это сообщение админа, пожаловаться нельзя.")
    if not cooldown(("report", me.id), 60):
        return await reply(update, "Подожди минуту перед следующей жалобой ⏳")
    reason = " ".join(context.args or []).strip()[:200]
    cur = db.execute("INSERT INTO reports(target_id,target_name,msg_id,reporter,reason,created,status) "
                     "VALUES(?,?,?,?,?,?, 'open')",
                     (t.id, disp(t), tm.message_id, disp(me), reason, time.time()))
    db.commit()
    rid = cur.lastrowid
    ids = {r["user_id"] for r in db.execute("SELECT user_id FROM users WHERE arank>=1")}
    oid = state_get("owner_id")
    if oid:
        ids.add(int(oid))
    hidden = "".join(f'<a href="tg://user?id={u}">​</a>' for u in list(ids)[:30])
    ln = _msg_link(update.effective_chat.id, tm.message_id)
    text = (f"🚨 <b>Жалоба #{rid}</b>\nНа: {link(t.id, disp(t))}\nОт: {esc(disp(me))}\n"
            f"Причина: {esc(reason or 'не указана')}"
            + (f"\n<a href=\"{ln}\">Перейти к сообщению</a>" if ln else "") + hidden)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔇 Мут 1ч", callback_data=f"rp:mute:{rid}"),
         InlineKeyboardButton("⛔ Бан", callback_data=f"rp:ban:{rid}")],
        [InlineKeyboardButton("🗑 Удалить сообщение", callback_data=f"rp:del:{rid}"),
         InlineKeyboardButton("✖ Закрыть", callback_data=f"rp:close:{rid}")]])
    await context.bot.send_message(update.effective_chat.id, text, parse_mode=HTML,
                                   reply_markup=kb, link_preview_options=NOPREV)
    try:
        await msg.delete()          # убираем команду, чтобы не светить жалобщика (нужно право удалять)
    except Exception:
        pass


async def on_report_btn(update, context):
    q = update.callback_query
    parts = (q.data or "").split(":")
    if len(parts) != 3 or parts[0] != "rp" or not parts[2].isdigit():
        return await q.answer()
    act, rid = parts[1], int(parts[2])
    r = db.execute("SELECT * FROM reports WHERE id=?", (rid,)).fetchone()
    if not r or r["status"] != "open":
        return await q.answer("Жалоба уже обработана", show_alert=True)
    key = "бан" if act == "ban" else "мут"
    if not has_rank(q.from_user, key):
        return await q.answer("Нужен ранг модератора", show_alert=True)
    chat_id = q.message.chat.id
    result = ""
    try:
        if act in ("mute", "ban") and not can_act_on(q.from_user, r["target_id"]):
            return await q.answer("У нарушителя ранг не ниже твоего", show_alert=True)
        if act == "mute":
            until = time.time() + 3600
            await context.bot.restrict_chat_member(chat_id, r["target_id"], ChatPermissions.no_permissions(),
                                                   until_date=int(until))
            db.execute("INSERT OR REPLACE INTO mutes(user_id,name,until,reason,by_name,created) "
                       "VALUES(?,?,?,?,?,?)", (r["target_id"], r["target_name"], until,
                                               f"жалоба #{rid}: {r['reason'] or '-'}", disp(q.from_user), time.time()))
            result = "🔇 Мут на 1 час"
        elif act == "ban":
            await context.bot.ban_chat_member(chat_id, r["target_id"])
            result = "⛔ Бан"
        elif act == "del":
            await context.bot.delete_message(chat_id, r["msg_id"])
            result = "🗑 Сообщение удалено"
        else:
            result = "✖ Закрыто без действий"
    except Exception as e:
        return await q.answer(f"Не вышло: {str(e)[:150]}", show_alert=True)
    db.execute("UPDATE reports SET status='done' WHERE id=?", (rid,))
    db.commit()
    await q.answer("Готово")
    try:
        await q.edit_message_text((q.message.text_html or "") + f"\n\n{result} · {esc(disp(q.from_user))}",
                                  parse_mode=HTML, link_preview_options=NOPREV)
    except Exception:
        pass


# ============================ СВИДЕТЕЛЬСТВО (картинка) ============================
CERT_W, CERT_H = 1600, 1130
CERT_TEXT_REL = ("Этот документ подтверждает искренность чувств прекрасной пары. "
                 "Пусть любовь крепнет с каждым днём.")
CERT_TEXT_MARRY = ("Этот документ подтверждает, что эти двое стали семьёй. "
                   "Пусть в доме всегда будет тепло.")


def _cert_font(kind, size):
    from PIL import ImageFont
    names = ["cert_bold.otf", "cert_bold.ttf"] if kind == "bold" else ["cert_text.otf", "cert_text.ttf"]
    cands = [os.path.join(BASE, n) for n in names]
    cands += ["C:/Windows/Fonts/segoeuib.ttf" if kind == "bold" else "C:/Windows/Fonts/segoeui.ttf",
              "C:/Windows/Fonts/arialbd.ttf" if kind == "bold" else "C:/Windows/Fonts/arial.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if kind == "bold"
              else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    for p in cands:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default(size)


def _heart_points(cx, cy, size):
    import math
    pts = []
    for i in range(0, 360, 4):
        t = math.radians(i)
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * size / 17, cy - y * size / 17))
    return pts


def _circle_avatar(raw, d, name):
    from PIL import Image, ImageDraw
    from io import BytesIO
    if raw:
        try:
            im = Image.open(BytesIO(bytes(raw))).convert("RGB")
            s = min(im.size)
            im = im.crop(((im.width - s) // 2, (im.height - s) // 2,
                          (im.width + s) // 2, (im.height + s) // 2)).resize((d, d), Image.LANCZOS)
        except Exception:
            im = None
    else:
        im = None
    if im is None:
        colors = [(232, 102, 52), (44, 110, 150), (110, 170, 110), (170, 100, 190), (230, 160, 40)]
        im = Image.new("RGB", (d, d), colors[sum(map(ord, name)) % len(colors)])
        dr = ImageDraw.Draw(im)
        f = _cert_font("bold", int(d * 0.5))
        ch = (name.strip()[:1] or "?").upper()
        dr.text((d / 2, d / 2), ch, fill="white", font=f, anchor="mm")
    big = Image.new("L", (d * 3, d * 3), 0)
    ImageDraw.Draw(big).ellipse((0, 0, d * 3 - 1, d * 3 - 1), fill=255)
    mask = big.resize((d, d), Image.LANCZOS)
    out = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out


def _fit(draw, text, kind, max_w, start):
    size = start
    while size > 20:
        f = _cert_font(kind, size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 2
    return _cert_font(kind, 20)


def _wrap(draw, text, font, max_w):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def make_certificate(name_a, name_b, av_a, av_b, date_str, married):
    """Рисует свидетельство. Возвращает BytesIO с JPEG."""
    import math
    from io import BytesIO
    from PIL import Image, ImageDraw, ImageChops
    W, H = CERT_W, CERT_H
    navy, orange, yellow = (44, 72, 98), (232, 102, 52), (245, 176, 40)
    pink, red = (250, 130, 160), (225, 60, 85)
    img = Image.new("RGB", (W, H), (252, 248, 241))
    d = ImageDraw.Draw(img)
    # геометрия по углам (верх справа и низ слева)
    d.rectangle((W - 300, 0, W, 150), fill=navy)
    d.pieslice((W - 420, -150, W - 120, 150), 90, 180, fill=orange)
    d.rectangle((W - 150, 150, W, 300), fill=yellow)
    d.pieslice((W - 300, 150, W, 450), 270, 360, fill=orange)
    d.ellipse((W - 560, 40, W - 500, 100), fill=navy)
    d.rectangle((0, H - 110, 210, H), fill=navy)
    d.pieslice((100, H - 110, 320, H + 110), 270, 360, fill=orange)
    d.rectangle((0, H - 220, 110, H - 110), fill=yellow)
    d.pieslice((-110, H - 330, 110, H - 110), 0, 90, fill=orange)
    for i in range(3):
        for j in range(3):
            d.ellipse((60 + i * 34, 90 + j * 34, 72 + i * 34, 102 + j * 34), fill=navy)
            d.ellipse((W - 150 + i * 34, 540 + j * 34, W - 138 + i * 34, 552 + j * 34), fill=navy)
    # заголовок
    t1 = "СВИДЕТЕЛЬСТВО О БРАКЕ" if married else "СВИДЕТЕЛЬСТВО ОБ ОТНОШЕНИЯХ"
    ft = _fit(d, t1, "bold", W - 640, 92)
    for dx, dy, col in ((5, 6, (170, 185, 200)), (0, 0, navy)):
        d.text((W / 2 + dx, 165 + dy), t1, font=ft, fill=col, anchor="mm")
    sub = "чат " + CHAT_TAG
    d.text((W / 2, 255), sub, font=_cert_font("text", 38), fill=(110, 120, 135), anchor="mm")
    # аватарки с венком
    for cx, av, nm in ((380, av_a, name_a), (1220, av_b, name_b)):
        cy, r = 470, 120
        for k in range(30):
            a = 2 * math.pi * k / 30
            col = [(240, 190, 205), (200, 190, 235), (250, 215, 170)][k % 3]
            x, y = cx + math.cos(a) * (r + 28), cy + math.sin(a) * (r + 28)
            d.ellipse((x - 17, y - 17, x + 17, y + 17), fill=col)
        d.ellipse((cx - r - 8, cy - r - 8, cx + r + 8, cy + r + 8), fill=(255, 255, 255))
        img.paste(_circle_avatar(av, r * 2, nm), (cx - r, cy - r), _circle_avatar(av, r * 2, nm))
        fn = _fit(d, nm[:28], "bold", 520, 52)
        d.text((cx, 665), nm[:28], font=fn, fill=navy, anchor="mm")
    # сердца посередине
    d.polygon(_heart_points(752, 475, 105), fill=pink)
    d.polygon(_heart_points(852, 467, 105), fill=red)
    for a, (x0, y0, x1, y1) in enumerate(((665, 385, 640, 360), (940, 385, 965, 360), (800, 360, 800, 325))):
        d.line((x0, y0, x1, y1), fill=navy, width=6)
    # линия сердцебиения
    y0 = 760
    d.line((100, y0, 700, y0), fill=(235, 120, 120), width=5)
    d.line((900, y0, 1500, y0), fill=(235, 120, 120), width=5)
    d.line((700, y0, 740, y0 - 25, 770, y0 + 20, 800, y0 - 60, 830, y0 + 35, 860, y0 - 15, 900, y0),
           fill=(235, 120, 120), width=5, joint="curve")
    # текст
    fb = _cert_font("text", 36)
    body = CERT_TEXT_MARRY if married else CERT_TEXT_REL
    y = 835
    for ln in _wrap(d, body, fb, W - 380):
        d.text((W / 2, y), ln, font=fb, fill=navy, anchor="mm")
        y += 52
    # дата, кольца, подпись
    d.text((560, 1005), date_str, font=_cert_font("bold", 44), fill=navy, anchor="mm")
    d.line((360, 1040, 760, 1040), fill=(235, 120, 120), width=4)
    d.text((560, 1080), "ДАТА", font=_cert_font("bold", 36), fill=navy, anchor="mm")
    if married:
        d.ellipse((930, 970, 1000, 1040), outline=(222, 170, 40), width=10)
        d.ellipse((970, 970, 1040, 1040), outline=(235, 195, 80), width=10)
    else:
        d.polygon(_heart_points(985, 1005, 70), fill=red)
    sig = Image.new("RGBA", (440, 120), (0, 0, 0, 0))
    ImageDraw.Draw(sig).text((20, 30), "Clavek", font=_cert_font("bold", 70), fill=navy)
    sig = sig.transform(sig.size, Image.AFFINE, (1, 0.45, -20, 0, 1, 0), Image.BICUBIC)
    img.paste(sig, (1180, 935), sig)
    d.line((1140, 1040, 1500, 1040), fill=(235, 120, 120), width=4)
    d.text((1320, 1080), "ПОДПИСЬ", font=_cert_font("bold", 36), fill=navy, anchor="mm")
    out = BytesIO()
    img.save(out, "JPEG", quality=90)
    out.seek(0)
    return out


async def _avatar_bytes(bot, uid):
    try:
        ph = await bot.get_user_profile_photos(uid, limit=1)
        if ph.total_count:
            f = await bot.get_file(ph.photos[0][-1].file_id)
            return bytes(await f.download_as_bytearray())
    except Exception as e:
        print("Аватарка недоступна:", repr(e)[:100])
    return None


async def send_certificate(bot, chat_id, row, married, reply_to=None, caption=None):
    """Свидетельство одним сообщением вместе с текстом (caption). True, если отправилось."""
    try:
        a, b = row["a"], row["b"]
        ts = row["married_at"] if married and row["married_at"] else row["since"]
        date_str = datetime.fromtimestamp(ts, timezone(timedelta(hours=TZ_HOURS))).strftime("%d.%m.%Y %H:%M")
        av_a, av_b = await _avatar_bytes(bot, a), await _avatar_bytes(bot, b)
        buf = await asyncio.to_thread(make_certificate, uname(a), uname(b), av_a, av_b, date_str, married)
        rp = ReplyParameters(message_id=reply_to, allow_sending_without_reply=True) if reply_to else None
        await bot.send_photo(chat_id, buf, reply_parameters=rp, parse_mode=HTML,
                             caption=caption or f"📜 {link(a, uname(a))} и {link(b, uname(b))}")
        return True
    except Exception as e:
        print("Свидетельство не отправилось:", repr(e)[:200])
        return False


# ============================ ЖИЗНЬ: РАБОТЫ, БРАК, ДОМА, ПИТОМЦЫ ============================
# Все цифры тут: меняй под свой чат.
JOBS = {   # ключ: (название, 🪙 за смену, пауза между сменами в часах, требования)
    "курьер":      ("Курьер", 20, 2, {}),
    "уборщик":     ("Уборщик", 25, 2, {}),
    "продавец":    ("Продавец", 35, 3, {"days": 2}),
    "официант":    ("Официант", 50, 3, {"level": 3}),
    "таксист":     ("Таксист", 70, 4, {"msgs": 300}),
    "программист": ("Программист", 120, 4, {"level": 8, "days": 7}),
    "врач":        ("Врач", 160, 6, {"level": 15, "days": 14}),
    "пилот":       ("Пилот", 220, 6, {"level": 25, "msgs": 2000}),
    "директор":    ("Директор", 400, 8, {"level": 40, "days": 30}),
}
HOUSES = {  # ключ: (название, цена, бонус к зарплате %, ссылка для кнопки «Посмотреть» или "")
    "комната":  ("Комната", 300, 5, ""),
    "квартира": ("Квартира", 1000, 10, ""),
    "дом":      ("Дом", 3000, 20, ""),
    "особняк":  ("Особняк", 10000, 35, ""),
}
PETS = {  # ключ: (название, цена, эмодзи)
    "кот": ("Кот", 150, "🐱"), "собака": ("Собака", 200, "🐶"), "хомяк": ("Хомяк", 80, "🐹"),
    "попугай": ("Попугай", 250, "🦜"), "кролик": ("Кролик", 180, "🐰"), "лиса": ("Лиса", 600, "🦊"),
}
MARRY_MIN_DAYS, MARRY_MIN_LOVE, MARRY_COST, DIVORCE_COST = 2, 300, 100, 50   # MARRY_MIN_LOVE: искры
PET_FEED_COST, PET_MAX, PET_RUNAWAY_DAYS = 3, 3, 5
ANNIV_DAYS, ANNIV_COINS = 30, 50
JOB_WORDS_FIND = {"найти работу", "вакансии", "поиск работы"}
JOB_WORDS_WORK = {"работать", "выйти на смену", "пойти на работу"}
JOB_WORDS_QUIT = {"уволиться", "уволиться с работы"}
JOB_WORDS_MY = {"моя работа", "моя профессия"}
MARRY_PROPOSE = {"предложить брак", "предложить пожениться", "пожениться", "выйти за меня замуж",
                 "выходи за меня"}
MARRY_ACCEPT = {"принять брак", "согласна на брак", "согласен на брак", "да я согласна", "да я согласен"}
MARRY_DECLINE = {"отказать в браке", "отказаться от брака"}
DIVORCE = {"развод", "развестись"}
FAMILY = {"семья", "мой брак", "моя семья"}
HOUSE_WORDS = {"купить дом", "недвижимость", "купить жильё", "купить жилье", "магазин домов"}
PET_SHOP_WORDS = {"купить питомца", "питомцы магазин", "зоомагазин"}
PET_MY_WORDS = {"питомцы", "мои питомцы"}
PET_FEED_WORDS = {"покормить питомца", "покормить питомцев", "кормить питомца"}
MARRY_PIC_API = "kiss"


def days_in_chat(row):
    return int((time.time() - (row["first_seen"] or time.time())) // 86400)


def job_missing(row, req):
    """-> список невыполненных условий (пусто, если работа доступна)"""
    out = []
    if row_level(row) < req.get("level", 0):
        out.append(f"уровень {req['level']}")
    if days_in_chat(row) < req.get("days", 0):
        out.append(f"{req['days']} дн. в чате")
    if (row["total"] or 0) < req.get("msgs", 0):
        out.append(f"{req['msgs']} сообщений")
    return out


def row_level(row):
    return level_of(row["xp"] or 0)


def house_bonus_pct(uid):
    """бонус дома: свой или дом супруга (берём лучший)"""
    best = 0
    ids = [uid]
    p = pair_of(uid)
    if p and (p["married_at"] or 0):
        ids.append(partner_of(p, uid))
    for i in ids:
        r = urow(i)
        if r and r["house"] in HOUSES:
            best = max(best, HOUSES[r["house"]][2])
    return best


def job_pay(row):
    name, base, cd, req = JOBS[row["job"]]
    mult = 1 + min(row["job_shifts"] or 0, 100) / 200 + house_bonus_pct(row["user_id"]) / 100
    return int(base * mult)


def own_kb(rows):
    return InlineKeyboardMarkup(rows)


async def life_send(update, context, text, key=None, api=None, kb=None, gif=None):
    """Сообщение с картинкой (свои «раб:курьер» и т.п.), гифкой из Giphy или аниме-гифкой и кнопками."""
    return await send_with_pic(context.bot, update.effective_chat.id, text, [key] if key else [],
                               reply_to=update.effective_message.message_id, api_cat=api,
                               markup=kb, gif_query=gif)


async def life_jobs_find(update, context):
    me = update.effective_user
    row = urow(me.id)
    lines = ["💼 <b>Биржа труда</b>"]
    if row["job"] in JOBS:
        lines.append(f"Сейчас ты работаешь: <b>{JOBS[row['job']][0]}</b>. «Работать» чтобы выйти на смену, "
                     f"«уволиться» чтобы сменить работу.\n")
    avail, locked = [], []
    for k, (name, pay, cd, req) in JOBS.items():
        miss = job_missing(row, req)
        (locked if miss else avail).append((k, name, pay, cd, miss))
    offers = random.sample(avail, min(3, len(avail)))
    lines.append("<b>Тебе предлагают:</b>")
    for k, name, pay, cd, _ in offers:
        lines.append(f"• {name}: {pay} 🪙 за смену, раз в {cd} ч.")
    if locked:
        lines.append("\n<b>Пока недоступно:</b>")
        for k, name, pay, cd, miss in locked[:4]:
            lines.append(f"🔒 {name} ({pay} 🪙): нужно {', '.join(miss)}")
    kb = own_kb([[InlineKeyboardButton(f"💼 {name} · {pay}🪙", callback_data=f"life:job:{me.id}:{k}")]
                 for k, name, pay, cd, _ in offers])
    await life_send(update, context, "\n".join(lines), kb=kb)


# ---------- мини-игры на работах ----------
GIPHY_KEY = os.environ.get("GIPHY_KEY", "")      # бесплатный ключ: developers.giphy.com
JOB_GIF = {"курьер": "delivery courier", "уборщик": "cleaning mop", "продавец": "cashier store",
           "официант": "waiter serving food", "таксист": "taxi driving", "программист": "programming computer",
           "врач": "doctor hospital", "пилот": "airplane pilot cockpit", "директор": "boss office"}
TASK_MIN = 10          # минут на выполнение
DELIVER = {            # работа -> (текст задания, слово-ответ, куда/кому)
    "курьер": ("📦 <b>Заказ #{n}</b>\nОтдайте заказ {t}", "отдать заказ"),
    "официант": ("🍽 <b>Столик #{n}</b>\nОтнесите блюда клиенту {t}", "принести заказ"),
    "таксист": ("🚕 <b>Вызов #{n}</b>\nПассажир {t} ждёт такси. Адрес: {place}", "довезти"),
    "врач": ("🩺 <b>Приём #{n}</b>\nНа осмотр пришёл {t}. Жалобы: {place}", "осмотреть"),
}
PLACES_TAXI = ["вокзал", "аэропорт", "торговый центр", "университет", "парк", "набережная"]
PLACES_DOC = ["болит голова", "кашель", "температура", "болит горло", "слабость", "насморк"]
WORDS = ["пылесос", "швабра", "ведро", "тряпка", "веник", "мусор", "метла", "порошок", "губка"]
MATH_FLAVOR = {"продавец": "🛒 <b>Касса.</b> Пробейте чек: {q}", "программист": "💻 <b>Баг #{n}.</b> Найдите ответ: {q}",
               "пилот": "✈️ <b>Расчёт топлива.</b> {q}", "директор": "📊 <b>Смета.</b> Подпишите, посчитав: {q}"}


def _math_task(job):
    r = random
    if job == "продавец":
        a, b, c = r.randint(20, 200), r.randint(10, 90), r.randint(5, 60)
        return f"{a} + {b} + {c} = ?", a + b + c
    if job == "программист":
        x, y, z = r.randint(6, 19), r.randint(3, 9), r.randint(1, 30)
        return f"{x} × {y} − {z} = ?", x * y - z
    if job == "пилот":
        c, k, d = r.randint(3, 9), r.randint(10, 40), r.randint(5, 50)
        return f"{c * k} ÷ {c} + {d} = ?", k + d
    x, y, z = r.randint(12, 40), r.randint(11, 30), r.randint(100, 900)
    return f"{x} × {y} + {z} = ?", x * y + z


def tag_user(row):
    return "@" + row["username"] if row["username"] else link(row["user_id"], row["name"])


async def giphy_url(q):
    if not GIPHY_KEY:
        return None
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get("https://api.giphy.com/v1/gifs/search",
                            params={"api_key": GIPHY_KEY, "q": q, "limit": 25, "rating": "g"})
        data = r.json().get("data") or []
        if data:
            im = random.choice(data)["images"]
            return (im.get("downsized_medium") or im.get("original") or {}).get("url")
    except Exception as e:
        print("Giphy:", repr(e)[:120])
    return None


def open_task(uid):
    return db.execute("SELECT * FROM job_tasks WHERE user_id=?", (uid,)).fetchone()


async def life_work(update, context):
    me = update.effective_user
    row = urow(me.id)
    if row["job"] not in JOBS:
        return await reply(update, "У тебя нет работы. Напиши «найти работу» 💼")
    t = open_task(me.id)
    if t and t["expires"] > time.time():
        return await reply(update, "Ты уже на смене, сначала закончи задание выше ☝️ "
                                   f"(осталось {fmt_minutes((t['expires'] - time.time()) // 60 + 1)})")
    name, base, cd, req = JOBS[row["job"]]
    left = (row["last_work"] or 0) + cd * 3600 - time.time()
    if left > 0:
        return await reply(update, f"Смена ещё не началась. Отдыхай: через {fmt_minutes(left // 60 + 1)} ⏳")
    job = row["job"]
    n = random.randint(100, 999)
    kind, answer, target, extra = "word", "", 0, ""
    if job in DELIVER:
        others = db.execute("SELECT * FROM users WHERE user_id!=? AND last_seen>? ORDER BY RANDOM() LIMIT 1",
                            (me.id, time.time() - 3 * 86400)).fetchone()
        if others:
            kind, target = "deliver", others["user_id"]
            tpl, phrase = DELIVER[job]
            place = random.choice(PLACES_TAXI if job == "таксист" else PLACES_DOC)
            text = tpl.format(n=n, t=tag_user(others), place=place)
            answer = phrase
            hint = (f"\n\nНапиши: «{phrase}» (можно ответом на его сообщение) или нажми кнопку. "
                    f"Время: {TASK_MIN} мин.")
    if kind != "deliver":
        if job in MATH_FLAVOR:
            kind = "math"
            q, ans = _math_task(job)
            answer = str(ans)
            text = MATH_FLAVOR[job].format(q=q, n=n)
            hint = f"\n\nНапиши ответ числом. Время: {TASK_MIN} мин."
        else:
            kind, answer = "word", random.choice(WORDS)
            text = (f"🧹 <b>Уборка.</b> Наведите порядок: напишите слово «{answer}»" if job == "уборщик"
                    else f"🛠 <b>Рабочее задание.</b> Напишите слово «{answer}»")
            hint = f"\n\nВремя: {TASK_MIN} мин."
    db.execute("INSERT OR REPLACE INTO job_tasks(user_id,job,kind,answer,target_id,created,expires) "
               "VALUES(?,?,?,?,?,?,?)", (me.id, job, kind, answer, target, time.time(),
                                        time.time() + TASK_MIN * 60))
    db.execute("UPDATE users SET last_work=? WHERE user_id=?", (time.time(), me.id))
    db.commit()
    kb = None
    if kind == "deliver":
        kb = own_kb([[InlineKeyboardButton("✅ Выполнить", callback_data=f"life:done:{me.id}:x")]])
    await life_send(update, context, f"{link(me.id, disp(me))}, новое задание!\n{text}{hint}", key="раб:" + job,
                    api="thumbsup", gif=JOB_GIF.get(job), kb=kb)


async def finish_task(bot, chat_id, uid, reply_to=None):
    t = open_task(uid)
    row = urow(uid)
    if not t or not row:
        return
    db.execute("DELETE FROM job_tasks WHERE user_id=?", (uid,))
    db.commit()
    if row["job"] not in JOBS:
        return
    pay = job_pay(row)
    note = ""
    r = random.random()
    if r < 0.10:
        pay = int(pay * 1.5)
        note = "\n🎉 Премия! Начальство довольно, зарплата +50%"
    elif r > 0.95:
        pay = int(pay * 0.5)
        note = "\n😬 Клиент недоволен, зарплата вдвое меньше"
    shifts = (row["job_shifts"] or 0) + 1
    db.execute("UPDATE users SET job_shifts=? WHERE user_id=?", (shifts, uid))
    db.commit()
    give_coins(uid, pay)
    for _i, (_n, _nm) in enumerate(CAREER):
        if _i and _n == shifts:
            give_coins(uid, 50 * _i)
            note += f"\n🎖 Повышение! Теперь ты: <b>{_nm}</b> · бонус +{50 * _i} 🪙"
    spark_note = ""
    pr_ = pair_of(uid)
    if pr_:
        bonus = max(1, pay // 5)
        spark_add(pr_["id"], bonus, "работа", row["name"])
        spark_note = f" · паре +{bonus} 🔥"
    extra = ""
    if t["kind"] == "deliver" and t["target_id"]:
        tr = urow(t["target_id"])
        if tr:
            extra = f"\n📬 {link(tr['user_id'], tr['name'])} обслужен(а)"
    await send_with_pic(bot, chat_id,
                        f"💼 {link(uid, row['name'])} выполнил(а) задание: <b>{JOBS[row['job']][0]}</b>{extra}\n"
                        f"+{pay} 🪙 · баланс {coins_of(uid)} · смен всего {shifts}{spark_note}" + note,
                        ["раб:" + row["job"]], reply_to=reply_to, api_cat="thumbsup",
                        gif_query=JOB_GIF.get(row["job"]))


async def task_check(update, context, clean):
    """Вызывается на каждое сообщение. True, если сообщение было ответом на задание."""
    me = update.effective_user
    t = open_task(me.id)
    if not t:
        return False
    if t["expires"] < time.time():
        db.execute("DELETE FROM job_tasks WHERE user_id=?", (me.id,))
        db.commit()
        await reply(update, "⌛ Время вышло: задание провалено, оплата за смену не начислена.")
        return False
    ok = False
    if t["kind"] == "deliver":
        ok = clean.startswith(t["answer"]) or clean in ("готово", "доставил", "доставила")
    elif t["kind"] == "math":
        ok = clean.replace(" ", "") == t["answer"]
    else:
        ok = clean == t["answer"]
    if not ok:
        return False
    await finish_task(context.bot, update.effective_chat.id, me.id, update.effective_message.message_id)
    return True


async def life_job_quit(update, context):
    me = update.effective_user
    row = urow(me.id)
    if row["job"] not in JOBS:
        return await reply(update, "Ты и так без работы 🙂")
    db.execute("UPDATE users SET job='' WHERE user_id=?", (me.id,))
    db.commit()
    await reply(update, f"📤 Ты уволился с должности «{JOBS[row['job']][0]}». Новая работа: «найти работу»")


# ---------- брак ----------
def is_married(row):
    return bool(row and (row["married_at"] or 0))


async def life_marry_propose(update, context):
    msg, me = update.effective_message, update.effective_user
    other = target_user(update)
    row = pair_of(me.id)
    if not other or other.id == me.id:
        return await reply(update, "Ответь на сообщение любимого человека: «предложить брак» 💍")
    if not row or partner_of(row, me.id) != other.id:
        return await reply(update, "Сначала нужно встречаться: «предложить встречаться».")
    if is_married(row):
        return await reply(update, "Вы уже в браке 💞")
    days = int((time.time() - row["since"]) // 86400)
    if days < MARRY_MIN_DAYS:
        return await reply(update, f"Рановато. Вы вместе {days} дн., нужно хотя бы {MARRY_MIN_DAYS}. "
                                   f"Узнайте друг друга получше 🌹")
    if row["love"] < MARRY_MIN_LOVE:
        return await reply(update, f"Искр пока маловато: {row['love']}/{MARRY_MIN_LOVE}. "
                                   f"Больше внимания: «свидание», «поцеловать», «обнять»")
    if coins_of(me.id) < MARRY_COST:
        return await reply(update, f"Свадьба стоит {MARRY_COST} 🪙, у тебя {coins_of(me.id)}. "
                                   f"Заработай: «работать», «бонус»")
    db.execute("INSERT OR REPLACE INTO marry_proposals(to_id,from_id,created) VALUES(?,?,?)",
               (other.id, me.id, time.time()))
    db.commit()
    await life_send(update, context,
                    f"💍 {link(me.id, disp(me))} делает предложение {link(other.id, disp(other))}!\n"
                    f"Ответ в течение суток: «принять брак» или «отказать в браке».\n"
                    f"Свадьба оплачивается из кошелька жениха/невесты: {MARRY_COST} 🪙",
                    key="отн:предложение брака", api="handhold")


async def life_marry_answer(update, context, accept):
    me = update.effective_user
    pr = db.execute("SELECT * FROM marry_proposals WHERE to_id=?", (me.id,)).fetchone()
    if not pr:
        return await reply(update, "Тебе никто не делал предложение брака.")
    db.execute("DELETE FROM marry_proposals WHERE to_id=?", (me.id,))
    db.commit()
    a = pr["from_id"]
    if time.time() - pr["created"] > 86400:
        return await reply(update, "Предложение устарело (прошли сутки).")
    if not accept:
        return await reply(update, f"💔 {link(me.id, disp(me))} отказал{ea(me.id)} {link(a, uname(a))} в браке.")
    row = pair_of(me.id)
    if not row or partner_of(row, me.id) != a or is_married(row):
        return await reply(update, "Что-то изменилось, свадьба не получится.")
    if coins_of(a) < MARRY_COST:
        return await reply(update, f"У {esc(uname(a))} не хватило монет на свадьбу ({MARRY_COST} 🪙).")
    give_coins(a, -MARRY_COST)
    db.execute("UPDATE pairs SET married_at=?, last_action=? WHERE id=?", (time.time(), time.time(), row["id"]))
    db.commit()
    spark_add(row["id"], 200, "свадьба", uname(a))
    txt = (f"🎉💍 <b>Свадьба!</b>\n{link(a, uname(a))} и {link(me.id, disp(me))} теперь муж и жена!\n"
           f"Дальше можно купить дом («купить дом»), завести питомцев («купить питомца») "
           f"и копить на семейное счастье. Профиль семьи: «семья»")
    if not await send_certificate(context.bot, update.effective_chat.id, pair_of(me.id), True,
                                  update.effective_message.message_id, caption=txt):
        await life_send(update, context, txt, key="отн:свадьба", api=MARRY_PIC_API)


async def life_divorce(update, context):
    me = update.effective_user
    row = pair_of(me.id)
    if not is_married(row):
        return await reply(update, "Ты не в браке.")
    if coins_of(me.id) < DIVORCE_COST:
        return await reply(update, f"Развод стоит {DIVORCE_COST} 🪙, а у тебя {coins_of(me.id)}.")
    p = partner_of(row, me.id)
    give_coins(me.id, -DIVORCE_COST)
    db.execute("DELETE FROM pairs WHERE id=?", (row["id"],))
    db.commit()
    await life_send(update, context,
                    f"💔 {link(me.id, disp(me))} подал(а) на развод с {link(p, uname(p))} (−{DIVORCE_COST} 🪙).",
                    key="отн:развод", api="cry")


async def life_family(update, context):
    u = target_user(update) or update.effective_user
    row = pair_of(u.id)
    if not row:
        return await reply(update, "У этого человека нет пары." if u.id != update.effective_user.id
                                   else "У тебя нет пары. Ответь «предложить встречаться» 💌")
    a, b = row["a"], row["b"]
    lines = [f"👨‍👩‍👧 <b>Семья</b>: {link(a, uname(a))} ❤ {link(b, uname(b))}",
             spark_line(row)]
    if is_married(row):
        lines.append(f"💍 В браке с {fmt_when(row['married_at'])}, "
                     f"{int((time.time() - row['married_at']) // 86400) + 1} дн.")
    else:
        lines.append(f"💞 Встречаются {int((time.time() - row['since']) // 86400) + 1} дн. "
                     f"(брак доступен с {MARRY_MIN_DAYS} дн. и {MARRY_MIN_LOVE} искр)")
    for i in (a, b):
        r = urow(i)
        if not r:
            continue
        job = JOBS[r["job"]][0] if r["job"] in JOBS else "без работы"
        lines.append(f"• {esc(r['name'])}: {job}, {r['coins'] or 0} 🪙")
    hs = {urow(i)["house"] for i in (a, b) if urow(i) and urow(i)["house"] in HOUSES}
    if hs:
        lines.append("🏠 Жильё: " + ", ".join(HOUSES[h][0] for h in hs))
    pets = db.execute("SELECT * FROM pets WHERE owner IN (?,?)", (a, b)).fetchall()
    if pets:
        lines.append("🐾 Питомцы: " + ", ".join(f"{PETS[p['kind']][2]} {esc(p['name'])}" for p in pets
                                                if p["kind"] in PETS))
    await life_send(update, context, "\n".join(lines))


# ---------- дома ----------
async def life_houses(update, context):
    me = update.effective_user
    row = urow(me.id)
    cur = row["house"] if row["house"] in HOUSES else None
    lines = ["🏠 <b>Недвижимость</b>", f"Твой баланс: {row['coins'] or 0} 🪙"]
    if cur:
        lines.append(f"Сейчас у тебя: {HOUSES[cur][0]} (старое жильё продаётся за 50%)")
    lines.append("Жильё даёт прибавку к зарплате и общее для супругов.\n")
    btns = []
    for k, (name, price, bonus, url) in HOUSES.items():
        lines.append(f"• {name}: {price} 🪙, +{bonus}% к зарплате")
        r = [InlineKeyboardButton(f"🏠 {name} · {price}🪙", callback_data=f"life:house:{me.id}:{k}")]
        if url:
            r.append(InlineKeyboardButton("👀 Посмотреть", url=url))
        btns.append(r)
    await life_send(update, context, "\n".join(lines), kb=own_kb(btns))


# ---------- питомцы ----------
def my_pets(uid):
    ids = [uid]
    p = pair_of(uid)
    if p and is_married(p):
        ids.append(partner_of(p, uid))
    return db.execute(f"SELECT * FROM pets WHERE owner IN ({','.join('?' * len(ids))})", ids).fetchall()


async def life_pet_shop(update, context):
    me = update.effective_user
    lines = ["🐾 <b>Зоомагазин</b>", f"Баланс: {coins_of(me.id)} 🪙. Питомцев можно держать до {PET_MAX}.",
             f"Кормить: «покормить питомца» ({PET_FEED_COST} 🪙 в день за каждого). "
             f"Без еды {PET_RUNAWAY_DAYS} дней питомец уходит.\n"]
    btns = []
    for k, (name, price, em) in PETS.items():
        lines.append(f"{em} {name}: {price} 🪙")
        btns.append([InlineKeyboardButton(f"{em} {name} · {price}🪙", callback_data=f"life:pet:{me.id}:{k}")])
    await life_send(update, context, "\n".join(lines), kb=own_kb(btns))


async def life_pet_my(update, context):
    pets = my_pets(update.effective_user.id)
    if not pets:
        return await reply(update, "Питомцев нет. Купить: «купить питомца» 🐾")
    lines = ["🐾 <b>Питомцы</b>"]
    for p in pets:
        em = PETS[p["kind"]][2] if p["kind"] in PETS else "🐾"
        fed = "накормлен сегодня" if p["fed_day"] == today() else "голодный"
        lines.append(f"{em} {esc(p['name'])} ({esc(uname(p['owner']))}): {fed}")
    await reply(update, "\n".join(lines) + "\n\nПереименовать: «назвать питомца Барсик»")


async def life_pet_feed(update, context):
    me = update.effective_user
    pets = [p for p in my_pets(me.id) if p["fed_day"] != today()]
    if not my_pets(me.id):
        return await reply(update, "Питомцев нет. Купить: «купить питомца» 🐾")
    if not pets:
        return await reply(update, "Все питомцы уже сыты сегодня 😺")
    cost = PET_FEED_COST * len(pets)
    if coins_of(me.id) < cost:
        return await reply(update, f"Корм стоит {cost} 🪙, а у тебя {coins_of(me.id)}.")
    give_coins(me.id, -cost)
    for p in pets:
        db.execute("UPDATE pets SET fed_day=? WHERE id=?", (today(), p["id"]))
    db.commit()
    await life_send(update, context, f"🍖 {link(me.id, disp(me))} покормил(а) питомцев: "
                                     + ", ".join(esc(p["name"]) for p in pets) + f" (−{cost} 🪙)",
                    key="пет:кормление", api="feed")


async def life_pet_rename(update, context, new):
    me = update.effective_user
    pets = [p for p in my_pets(me.id) if p["owner"] == me.id]
    if not pets:
        return await reply(update, "У тебя нет своих питомцев.")
    new = new.strip()[:20]
    if not new:
        return await reply(update, "Напиши имя: «назвать питомца Барсик»")
    db.execute("UPDATE pets SET name=? WHERE id=?", (new, pets[-1]["id"]))
    db.commit()
    await reply(update, f"✏️ Теперь питомца зовут <b>{esc(new)}</b>")


# ---------- кнопки ----------
async def on_life_btn(update, context):
    q = update.callback_query
    p = (q.data or "").split(":")
    if len(p) != 4 or p[0] != "life" or not p[2].isdigit():
        return await q.answer()
    kind, uid, key = p[1], int(p[2]), p[3]
    if q.from_user.id != uid:
        return await q.answer("Это меню другого человека. Напиши команду сам 🙂", show_alert=True)
    if kind == "done":
        t = open_task(uid)
        if not t or t["expires"] < time.time():
            return await q.answer("Задание уже недоступно", show_alert=True)
        await q.answer("Принято")
        try:
            await q.edit_message_reply_markup(None)
        except Exception:
            pass
        return await finish_task(context.bot, q.message.chat.id, uid, q.message.message_id)
    row = urow(uid)
    if not row:
        return await q.answer("Напиши что-нибудь в чат, чтобы бот тебя запомнил", show_alert=True)
    chat = q.message.chat.id
    text, api, pic, gif = None, None, None, None
    if kind == "job":
        if key not in JOBS:
            return await q.answer()
        miss = job_missing(row, JOBS[key][3])
        if miss:
            return await q.answer("Пока рано: нужно " + ", ".join(miss), show_alert=True)
        db.execute("UPDATE users SET job=?, job_shifts=CASE WHEN job=? THEN job_shifts ELSE 0 END "
                   "WHERE user_id=?", (key, key, uid))
        db.commit()
        text = (f"✅ {link(uid, row['name'])} устроился: <b>{JOBS[key][0]}</b>\n"
                f"Зарплата {JOBS[key][1]} 🪙 за смену. Выходи на смену словом «работать»")
        pic, api, gif = "раб:" + key, "thumbsup", JOB_GIF.get(key)
    elif kind == "house":
        if key not in HOUSES:
            return await q.answer()
        name, price, bonus, url = HOUSES[key]
        old = row["house"] if row["house"] in HOUSES else None
        if old == key:
            return await q.answer("Этот дом у тебя уже есть", show_alert=True)
        refund = HOUSES[old][1] // 2 if old else 0
        if (row["coins"] or 0) + refund < price:
            return await q.answer(f"Не хватает монет: нужно {price - refund}, у тебя {row['coins'] or 0}",
                                  show_alert=True)
        give_coins(uid, refund - price)
        db.execute("UPDATE users SET house=? WHERE user_id=?", (key, uid))
        db.commit()
        text = (f"🏠 {link(uid, row['name'])} купил(а): <b>{name}</b> за {price} 🪙"
                + (f" (старое жильё продано за {refund})" if refund else "")
                + f"\nБонус к зарплате: +{bonus}%")
        pic, api = "дом:" + key, "happy"
    elif kind == "pet":
        if key not in PETS:
            return await q.answer()
        if len([x for x in my_pets(uid)]) >= PET_MAX:
            return await q.answer(f"Больше {PET_MAX} питомцев держать нельзя", show_alert=True)
        name, price, em = PETS[key]
        if (row["coins"] or 0) < price:
            return await q.answer(f"Не хватает монет: нужно {price}, у тебя {row['coins'] or 0}", show_alert=True)
        give_coins(uid, -price)
        db.execute("INSERT INTO pets(owner,kind,name,fed_day,bought) VALUES(?,?,?,?,?)",
                   (uid, key, name, today(), time.time()))
        db.commit()
        text = (f"{em} {link(uid, row['name'])} завёл(а) питомца: <b>{name}</b> за {price} 🪙\n"
                f"Дать имя: «назвать питомца Барсик», кормить: «покормить питомца»")
        pic, api = "пет:" + key, "pat"
    else:
        return await q.answer()
    await q.answer("Готово")
    try:
        await q.edit_message_reply_markup(None)
    except Exception:
        pass
    await send_with_pic(context.bot, chat, text, [pic], reply_to=q.message.message_id, api_cat=api,
                        gif_query=gif)


# ---------- маршрутизация слов ----------
async def handle_life(update, context, low, text):
    clean = re.sub(r"[!.?,]+$", "", low).strip()
    if await task_check(update, context, clean):
        return True
    if await handle_v21(update, context, clean):
        return True
    if clean in ("свидетельство", "сертификат", "свидетельство о браке"):
        who = target_user(update) or update.effective_user
        prow = pair_of(who.id)
        if not prow:
            await reply(update, "У этого человека нет пары." if who.id != update.effective_user.id
                        else "У тебя нет пары. Ответь «предложить встречаться» 💌")
        else:
            await send_certificate(context.bot, update.effective_chat.id, prow, is_married(prow),
                                   update.effective_message.message_id)
        return True
    if clean in JOB_WORDS_FIND:
        await life_jobs_find(update, context)
    elif clean in JOB_WORDS_WORK:
        await life_work(update, context)
    elif clean in JOB_WORDS_QUIT:
        await life_job_quit(update, context)
    elif clean in JOB_WORDS_MY:
        await life_job_my(update, context)
    elif clean in MARRY_PROPOSE:
        await life_marry_propose(update, context)
    elif clean in MARRY_ACCEPT or clean in MARRY_DECLINE:
        if not db.execute("SELECT 1 FROM marry_proposals WHERE to_id=?", (update.effective_user.id,)).fetchone():
            return False
        await life_marry_answer(update, context, clean in MARRY_ACCEPT)
    elif clean in DIVORCE:
        if not pair_of(update.effective_user.id):
            return False                  # обычное слово в разговоре
        await rel_leave_ask(update, context)
    elif clean in OFFEND_WORDS:
        if not await rel_offend(update, context):
            return False
    elif clean in KID_WORDS:
        await rel_kid_ask(update, context)
    elif clean in KIDS_LIST_WORDS:
        prow = pair_of(update.effective_user.id)
        if not prow or not kids_of(prow["id"]):
            return False
        await rel_kids_list(update, context)
    elif clean.startswith(("назвать ребёнка ", "назвать ребенка ")):
        await rel_kid_rename(update, context, text.strip().split(" ", 2)[2] if len(text.split()) > 2 else "")
    elif re.fullmatch(r"мой ?пол [мж]", clean):
        g = clean[-1]
        db.execute("UPDATE users SET gender=? WHERE user_id=?", (g, update.effective_user.id))
        db.commit()
        await reply(update, "✅ Пол сохранён: " + ("мужской" if g == "м" else "женский") +
                    ". Теперь в текстах будут правильные окончания.")
    elif clean in FAMILY:
        if not pair_of(update.effective_user.id) and not target_user(update):
            return False
        await life_family(update, context)
    elif clean in HOUSE_WORDS:
        await life_houses(update, context)
    elif clean in PET_SHOP_WORDS:
        await life_pet_shop(update, context)
    elif clean in PET_MY_WORDS:
        if not my_pets(update.effective_user.id):
            return False
        await life_pet_my(update, context)
    elif clean in PET_FEED_WORDS:
        await life_pet_feed(update, context)
    elif clean.startswith("назвать питомца "):
        await life_pet_rename(update, context, text.strip()[len("назвать питомца "):])
    else:
        return False
    return True


async def life_daily(bot):
    await rel_daily(bot)
    d = today()
    # годовщины
    for row in db.execute("SELECT * FROM pairs WHERE married_at>0").fetchall():
        days = int((time.time() - row["married_at"]) // 86400)
        if days and days % ANNIV_DAYS == 0 and row["anniv_day"] != d:
            db.execute("UPDATE pairs SET anniv_day=? WHERE id=?", (d, row["id"]))
            db.commit()
            for i in (row["a"], row["b"]):
                give_coins(i, ANNIV_COINS)
            try:
                await send_with_pic(bot, CHAT_ID,
                                    f"🎂 {link(row['a'], uname(row['a']))} и {link(row['b'], uname(row['b']))} "
                                    f"женаты уже {days} дн.! Подарок: +{ANNIV_COINS} 🪙 каждому",
                                    ["отн:годовщина"], api_cat="happy")
            except Exception:
                log.exception("anniv")
    # питомцы без еды уходят
    for p in db.execute("SELECT * FROM pets").fetchall():
        last = p["fed_day"] or ""
        try:
            gap = (datetime.strptime(d, FMT) - datetime.strptime(last, FMT)).days if last else 99
        except ValueError:
            gap = 99
        if gap >= PET_RUNAWAY_DAYS:
            db.execute("DELETE FROM pets WHERE id=?", (p["id"],))
            db.commit()
            try:
                await bot.send_message(CHAT_ID, f"😿 Питомец «{esc(p['name'])}» ({esc(uname(p['owner']))}) "
                                                f"ушёл: его давно не кормили", parse_mode=HTML,
                                       link_preview_options=NOPREV)
            except Exception:
                log.exception("pet run")


# ============================ ВЕРСИЯ 21: карьера, свидания, подарки, семейный счёт, админка ============================
db.executescript("""
CREATE TABLE IF NOT EXISTS custom_jobs(key TEXT PRIMARY KEY, name TEXT, pay INTEGER, cd INTEGER, req TEXT);
CREATE TABLE IF NOT EXISTS admin_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, actor INTEGER, actor_name TEXT, cmd TEXT, text TEXT);
""")
try:
    db.execute("ALTER TABLE pairs ADD COLUMN bank INTEGER DEFAULT 0")
except sqlite3.OperationalError:
    pass
db.commit()

BUILTIN_JOBS = set(JOBS)


def load_custom_jobs():
    for r in db.execute("SELECT * FROM custom_jobs").fetchall():
        try:
            req = json.loads(r["req"] or "{}")
        except Exception:
            req = {}
        JOBS[r["key"]] = (r["name"], r["pay"], r["cd"], req)


load_custom_jobs()

# ---------- карьера: должность растёт со сменами ----------
CAREER = [(0, "Стажёр"), (10, "Специалист"), (30, "Старший"), (70, "Эксперт"), (150, "Мастер")]


def career_title(shifts):
    t = CAREER[0][1]
    for n, name in CAREER:
        if shifts >= n:
            t = name
    return t


def career_next(shifts):
    return next(((n, nm) for n, nm in CAREER if n > shifts), None)


async def life_job_my(update, context):
    me = update.effective_user
    row = urow(me.id)
    if row["job"] not in JOBS:
        return await reply(update, "У тебя нет работы. Напиши «найти работу» 💼")
    name, base, cd, req = JOBS[row["job"]]
    left = (row["last_work"] or 0) + cd * 3600 - time.time()
    nxt = "можно выходить на смену прямо сейчас" if left <= 0 else f"следующая смена через {fmt_minutes(left // 60 + 1)}"
    bonus = house_bonus_pct(me.id)
    sh = row["job_shifts"] or 0
    nx = career_next(sh)
    grow = f" (до «{nx[1]}» ещё {nx[0] - sh})" if nx else " (высшая должность)"
    text = (f"💼 <b>{esc(name)}</b> · {career_title(sh)}\nЗарплата за смену: {job_pay(row)} 🪙 (база {base}, "
            f"+стаж {min(sh, 100) // 2}%" + (f", +дом {bonus}%" if bonus else "") +
            f")\nСмен отработано: {sh}{grow}\n{nxt}")
    await life_send(update, context, text, key="проф:" + row["job"])


async def cmd_jobs_list_impl(update):
    lines = ["💼 <b>Список работ</b>"]
    for k, (name, pay, cd, req) in JOBS.items():
        r = ", ".join(f"{lbl} {req[f]}" for f, lbl in (("level", "ур."), ("days", "дн."), ("msgs", "сообщ.")) if f in req)
        lines.append(f"• <b>{esc(name)}</b> ({esc(k)}): {pay} 🪙, пауза {cd} ч." + (f" · нужно: {r}" if r else "")
                     + ("" if k in BUILTIN_JOBS else " · своя"))
    await reply(update, "\n".join(lines))


@need("список работ")
async def cmd_jobs_list(update, context):
    await cmd_jobs_list_impl(update)


@need("добавить работу")
async def cmd_job_add(update, context):
    a = list(context.args or [])
    usage = ("Формат: добавить работу Грузчик 45 3 ур=2 дн=1 сообщ=100\n"
             "(название одним словом, оплата за смену в 🪙, пауза в часах; условия ур=, дн=, сообщ= можно не писать)")
    if len(a) < 3 or not a[1].isdigit() or not a[2].isdigit():
        return await reply(update, usage)
    key = a[0].lower()[:20]
    if key in BUILTIN_JOBS:
        return await reply(update, "Такая работа уже есть в боте, выбери другое название.")
    pay, cd = int(a[1]), int(a[2])
    if not (1 <= pay <= 5000) or not (1 <= cd <= 48):
        return await reply(update, "Оплата от 1 до 5000 🪙, пауза от 1 до 48 часов.")
    req = {}
    for x in a[3:]:
        m = re.fullmatch(r"(ур|дн|сообщ)=(\d{1,6})", x.lower())
        if not m:
            return await reply(update, usage)
        req[{"ур": "level", "дн": "days", "сообщ": "msgs"}[m.group(1)]] = int(m.group(2))
    name = key[:1].upper() + key[1:]
    db.execute("INSERT OR REPLACE INTO custom_jobs(key,name,pay,cd,req) VALUES(?,?,?,?,?)",
               (key, name, pay, cd, json.dumps(req)))
    db.commit()
    JOBS[key] = (name, pay, cd, req)
    await reply(update, f"✅ Работа добавлена: <b>{esc(name)}</b>, {pay} 🪙 за смену, пауза {cd} ч. "
                        f"Она появится в «найти работу».")


@need("удалить работу")
async def cmd_job_del(update, context):
    a = list(context.args or [])
    key = a[0].lower() if a else ""
    if key in BUILTIN_JOBS:
        return await reply(update, "Встроенные работы удалить нельзя, только добавленные командой.")
    if key not in JOBS:
        return await reply(update, "Такой работы нет. Список: «список работ»")
    JOBS.pop(key, None)
    db.execute("DELETE FROM custom_jobs WHERE key=?", (key,))
    db.execute("UPDATE users SET job='' WHERE job=?", (key,))
    db.commit()
    await reply(update, f"🗑 Работа «{esc(key)}» удалена, у работавших она снята.")


# ---------- свидания с выбором места ----------
DATE_PLACES = {"парк": ("🌳 Парк", 0, 50), "кино": ("🎬 Кино", 20, 80),
               "ресторан": ("🍽 Ресторан", 50, 130), "концерт": ("🎤 Концерт", 80, 200)}


def date_kb(uid):
    rows = []
    for k, (nm, cost, gain) in DATE_PLACES.items():
        rows.append([InlineKeyboardButton(f"{nm} · {cost} 🪙 → +{gain} 🔥" if cost else f"{nm} · бесплатно → +{gain} 🔥",
                                          callback_data=f"date:{uid}:{k}")])
    return InlineKeyboardMarkup(rows)


def date_go(uid, place):
    """-> (ok, сообщение). Платит тот, кто выбрал место."""
    row = pair_of(uid)
    if not row:
        return False, "У тебя нет пары"
    if row["date_day"] == today():
        return False, "Сегодня вы уже ходили на свидание 🌹"
    pid = partner_of(row, uid)
    if offended_block(uid, pid):
        return False, "Ваша половинка обижена, действия недоступны"
    nm, cost, gain = DATE_PLACES[place]
    if cost and coins_of(uid) < cost:
        return False, f"Нужно {cost} 🪙, у тебя {coins_of(uid)}"
    if cost:
        give_coins(uid, -cost)
    db.execute("UPDATE pairs SET date_day=?, last_action=?, actions=actions+1 WHERE id=?",
               (today(), time.time(), row["id"]))
    db.commit()
    new = spark_add(row["id"], gain, "свидание", uname(uid))
    return True, (f"🌹 {link(uid, uname(uid))} и {link(pid, uname(pid))} сходили на свидание: <b>{nm}</b>!\n"
                  f"+{gain} 🔥 · всего искр: {new}" + (f" · потрачено {cost} 🪙" if cost else ""))


async def on_date_btn(update, context):
    q = update.callback_query
    p = (q.data or "").split(":")
    if len(p) != 3 or not p[1].isdigit() or p[2] not in DATE_PLACES:
        return await q.answer()
    if q.from_user.id != int(p[1]):
        return await q.answer("Это меню не для тебя", show_alert=True)
    ok, msg = date_go(int(p[1]), p[2])
    if not ok:
        return await q.answer(msg, show_alert=True)
    await q.answer()
    try:
        await q.message.delete()
    except Exception:
        pass
    await send_with_pic(context.bot, q.message.chat_id, msg, ["свид:" + p[2]])


# ---------- подарки партнёру ----------
GIFTS = {"цветы": ("💐 Цветы", 30, 40), "шоколад": ("🍫 Шоколад", 20, 25),
         "мишка": ("🧸 Плюшевый мишка", 80, 110), "украшение": ("💎 Украшение", 200, 320)}
GIFT_MENU_WORDS = {"подарок партнёру", "подарок партнеру", "подарить партнёру", "подарить партнеру"}


def gift_kb(uid):
    return InlineKeyboardMarkup([[InlineKeyboardButton(f"{nm} · {cost} 🪙 → +{gain} 🔥",
                                                       callback_data=f"gift:{uid}:{k}")]
                                 for k, (nm, cost, gain) in GIFTS.items()])


def gift_give(uid, key):
    row = pair_of(uid)
    if not row:
        return False, "У тебя нет пары"
    pid = partner_of(row, uid)
    if offended_block(uid, pid):
        return False, "Ваша половинка обижена, действия недоступны"
    nm, cost, gain = GIFTS[key]
    if coins_of(uid) < cost:
        return False, f"Нужно {cost} 🪙, у тебя {coins_of(uid)}"
    give_coins(uid, -cost)
    new = spark_add(row["id"], gain, "подарок", uname(uid))
    return True, (f"🎁 {link(uid, uname(uid))} подарил(а) {link(pid, uname(pid))}: {nm}!\n"
                  f"+{gain} 🔥 · всего искр: {new}").replace("(а)", ea(uid))


async def on_gift_btn(update, context):
    q = update.callback_query
    p = (q.data or "").split(":")
    if len(p) != 3 or not p[1].isdigit() or p[2] not in GIFTS:
        return await q.answer()
    if q.from_user.id != int(p[1]):
        return await q.answer("Это меню не для тебя", show_alert=True)
    ok, msg = gift_give(int(p[1]), p[2])
    if not ok:
        return await q.answer(msg, show_alert=True)
    await q.answer("Подарок отправлен 🎁")
    await send_with_pic(context.bot, q.message.chat_id, msg, [])


# ---------- семейный счёт ----------
async def handle_v21(update, context, clean):
    if await games_text(update, context, clean, clean):
        return True
    me = update.effective_user
    msg = update.effective_message
    m_in = re.match(r"^(?:в семью|положить в семью|пополнить семью)\s+(\d{1,7})$", clean)
    m_out = re.match(r"^(?:из семьи|снять из семьи|снять с семьи)\s+(\d{1,7})$", clean)
    gm = re.match(r"^подарить\s+(цветы|шоколад|мишка|мишку|украшение)$", clean)
    if not (m_in or m_out or gm or clean in GIFT_MENU_WORDS
            or clean in ("семейный счёт", "семейный счет", "семейный бюджет", "общий счёт", "общий счет")):
        return False
    row = pair_of(me.id)
    if gm or clean in GIFT_MENU_WORDS:
        if not row:
            return False
        if gm:
            key = "мишка" if gm.group(1) == "мишку" else gm.group(1)
            ok, text = gift_give(me.id, key)
            await send_with_pic(context.bot, update.effective_chat.id, text if ok else "🙁 " + text, [],
                                reply_to=msg.message_id)
        else:
            await send_with_pic(context.bot, update.effective_chat.id, "🎁 Что подарим половинке?", [],
                                reply_to=msg.message_id, markup=gift_kb(me.id))
        return True
    if not row or not is_married(row):
        return False
    bank = row["bank"] or 0
    if m_in:
        n = int(m_in.group(1))
        if n <= 0 or coins_of(me.id) < n:
            return await reply(update, f"У тебя {coins_of(me.id)} 🪙, этого мало.") or True
        give_coins(me.id, -n)
        db.execute("UPDATE pairs SET bank=bank+? WHERE id=?", (n, row["id"]))
        db.commit()
        await reply(update, f"🏦 {n} 🪙 положено на семейный счёт. Теперь там {bank + n} 🪙")
    elif m_out:
        n = int(m_out.group(1))
        if n <= 0 or bank < n:
            return await reply(update, f"На семейном счёте {bank} 🪙, этого мало.") or True
        db.execute("UPDATE pairs SET bank=bank-? WHERE id=?", (n, row["id"]))
        db.commit()
        give_coins(me.id, n)
        await reply(update, f"🏦 Снято {n} 🪙. На семейном счёте осталось {bank - n} 🪙")
    else:
        await reply(update, f"🏦 <b>Семейный счёт</b>: {bank} 🪙\n«в семью 100» положить, «из семьи 100» снять")
    return True


# ---------- админка: журнал, приветствие, правила, статистика недели ----------
LOG_SKIP = {"список мута", "список картинок", "админка", "админы", "заказы", "журнал", "статистика",
            "слова дня", "статистика недели", "список работ", "дк"}


def log_admin(update, key):
    try:
        u, m = update.effective_user, update.effective_message
        txt = (m.text or "")[:200]
        t = reply_user(update)
        if t:
            txt += f"  [→ {disp(t)}]"
        db.execute("INSERT INTO admin_log(ts,actor,actor_name,cmd,text) VALUES(?,?,?,?,?)",
                   (time.time(), u.id, disp(u), key, txt))
        db.execute("DELETE FROM admin_log WHERE id < (SELECT MAX(id) FROM admin_log) - 500")
        db.commit()
    except Exception:
        log.exception("admin log")


@need("журнал")
async def cmd_admin_log(update, context):
    a = list(context.args or [])
    n = max(1, min(int(a[0]), 40)) if a and a[0].isdigit() else 15
    rows = db.execute("SELECT * FROM admin_log ORDER BY id DESC LIMIT ?", (n,)).fetchall()
    if not rows:
        return await reply(update, "Журнал пока пуст.")
    lines = [f"📒 <b>Журнал действий</b> (последние {len(rows)})"]
    for r in rows:
        t = datetime.fromtimestamp(r["ts"], now().tzinfo).strftime("%d.%m %H:%M")
        lines.append(f"{t} · {esc(r['actor_name'])}: {esc(r['text'])}")
    await reply(update, "\n".join(lines)[:4000])


@need("установить приветствие")
async def cmd_set_welcome(update, context):
    t = " ".join(context.args or []).strip()
    if not t:
        cur = state_get("welcome")
        return await reply(update, ("Сейчас: " + esc(cur) if cur else "Приветствие выключено.") +
                                   "\nФормат: установить приветствие Привет, {name}! Правила: «правила». "
                                   "Выключить: установить приветствие выкл")
    if t.lower() in ("выкл", "off", "нет"):
        state_set("welcome", "")
        return await reply(update, "Приветствие выключено.")
    state_set("welcome", t[:500])
    await reply(update, "✅ Приветствие сохранено. {name} заменится на имя новичка.")


@need("установить правила")
async def cmd_set_rules(update, context):
    t = " ".join(context.args or []).strip()
    if not t:
        return await reply(update, "Формат: установить правила Текст правил (выкл — убрать)")
    state_set("rules", "" if t.lower() in ("выкл", "off") else t[:1500])
    await reply(update, "✅ Правила сохранены. Участники смотрят их словом «правила».")


@group_only
async def cmd_rules(update, context):
    t = state_get("rules")
    if t:
        await reply(update, "📜 <b>Правила чата</b>\n" + esc(t))


async def on_new_members(update, context):
    msg, chat = update.effective_message, update.effective_chat
    if not msg or not chat or chat.id not in ALLOWED:
        return
    tpl = state_get("welcome")
    if not tpl:
        return
    for u in msg.new_chat_members or []:
        if u.is_bot:
            continue
        touch(u)
        try:
            await context.bot.send_message(chat.id, esc(tpl).replace("{name}", link(u.id, disp(u))),
                                           parse_mode=HTML)
        except Exception:
            log.exception("welcome")


@need("статистика недели")
async def cmd_weekstat(update, context):
    ws = week_start()
    days = db.execute("SELECT day, SUM(cnt) c FROM daily WHERE day>=? GROUP BY day ORDER BY day", (ws,)).fetchall()
    total = sum(r["c"] or 0 for r in days)
    active = db.execute("SELECT COUNT(DISTINCT user_id) FROM daily WHERE day>=? AND cnt>0", (ws,)).fetchone()[0]
    top = db.execute("SELECT u.user_id, u.name, SUM(d.cnt) c FROM daily d JOIN users u ON u.user_id=d.user_id "
                     "WHERE d.day>=? GROUP BY d.user_id ORDER BY c DESC LIMIT 5", (ws,)).fetchall()
    new = db.execute("SELECT COUNT(*) FROM users WHERE first_seen>=?", (time.time() - 7 * 86400,)).fetchone()[0]
    pairs_n = db.execute("SELECT COUNT(*) FROM pairs").fetchone()[0]
    married = db.execute("SELECT COUNT(*) FROM pairs WHERE married_at>0").fetchone()[0]
    mx = max([r["c"] or 0 for r in days] + [1])
    lines = [f"📊 <b>Неделя в чате</b>\nСообщений: {total} · активных: {active} · новых: {new}",
             f"Пар: {pairs_n} (в браке {married})", "\n<b>По дням</b>"]
    for r in days:
        c = r["c"] or 0
        lines.append(f"{r['day'][5:]} {'█' * max(1, round(c * 10 / mx)) if c else '·'} {c}")
    if top:
        lines.append("\n<b>Топ-5</b>")
        for i, r in enumerate(top, 1):
            lines.append(f"{i}. {link(r['user_id'], r['name'])}: {r['c']}")
    await reply(update, "\n".join(lines))


# ============================ МИНИ-ИГРЫ ============================
GAMES = {}                       # chat_id -> состояние текущей игры (одна игра на чат)
GAME_LAST = {}                   # chat_id -> когда запускали последний раз
GAME_EARNED = {}                 # (день, user_id) -> сколько монет уже получено с игр
GAME_CAP, GAME_COOLDOWN, GAME_SEC = 200, 45, 180
GAME_WORDS = ["компьютер", "телефон", "собака", "школа", "машина", "дорога", "солнце", "ракета", "планета",
              "картина", "музыка", "шоколад", "зеркало", "подарок", "каникулы", "пирожное", "велосипед",
              "магазин", "фонарик", "бабочка", "дракон", "корабль", "радуга", "виноград", "арбуз",
              "подушка", "телевизор", "гитара", "программа", "сообщение", "чемпион", "приключение"]
GAME_START = {"угадай число": "number", "анаграмма": "scramble", "кто быстрее": "speed", "виселица": "hang"}
GAME_LIST_WORDS = {"мини игры", "мини-игры", "миниигры"}
GAME_STOP_WORDS = {"стоп игра", "остановить игру"}
HANG_MAX = 7


db.execute("CREATE TABLE IF NOT EXISTS game_wins(user_id INTEGER PRIMARY KEY, wins INTEGER DEFAULT 0)")
db.commit()


def hang_mask(g):
    return " ".join(c if c in g["opened"] else "_" for c in g["word"])


async def game_win(update, uid, name, extra=""):
    db.execute("INSERT INTO game_wins(user_id,wins) VALUES(?,1) ON CONFLICT(user_id) DO UPDATE SET wins=wins+1", (uid,))
    db.commit()
    w = db.execute("SELECT wins FROM game_wins WHERE user_id=?", (uid,)).fetchone()["wins"]
    await reply(update, f"🏆 {link(uid, name)} побеждает! {extra}Побед в играх: {w}")


def game_launch(chat_id, uid, kind):
    """Запускает игру. -> (ok, текст)"""
    g = GAMES.get(chat_id)
    if g and time.time() > g["until"]:
        GAMES.pop(chat_id, None)
        g = None
    if g:
        return False, "Сейчас уже идёт игра, дождись конца или «стоп игра»."
    wait = GAME_COOLDOWN - (time.time() - GAME_LAST.get(chat_id, 0))
    if wait > 0:
        return False, f"Игры можно запускать раз в {GAME_COOLDOWN} сек. Подожди ещё {int(wait) + 1} сек."
    GAME_LAST[chat_id] = time.time()
    g = {"kind": kind, "starter": uid, "until": time.time() + GAME_SEC}
    if kind == "number":
        g["n"] = random.randint(1, 100)
        text = (f"🔢 Я загадал число от 1 до 100. Пишите числа, подскажу «больше» или «меньше». "
                f"Время {GAME_SEC // 60} мин.")
    elif kind == "scramble":
        w = random.choice(GAME_WORDS)
        letters = list(w)
        for _ in range(10):
            random.shuffle(letters)
            if "".join(letters) != w:
                break
        g["word"] = w
        text = f"🔤 Анаграмма: <b>{' '.join(letters).upper()}</b>\nКто первым напишет слово? Время {GAME_SEC // 60} мин."
    elif kind == "speed":
        w = random.choice(GAME_WORDS)
        g["word"] = w
        g["until"] = time.time() + 60
        text = f"⚡️ Кто быстрее! Первый, кто напишет слово <b>{w}</b>, побеждает."
    else:
        g["word"] = random.choice(GAME_WORDS)
        g["opened"] = set()
        g["wrong"] = set()
        text = (f"🪢 Виселица! Слово из {len(g['word'])} букв:\n<code>{hang_mask(g)}</code>\n"
                f"Пишите по одной букве или слово целиком. Ошибок можно {HANG_MAX}.")
    GAMES[chat_id] = g
    return True, text


def games_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔢 Угадай число", callback_data="game:number"),
         InlineKeyboardButton("🔤 Анаграмма", callback_data="game:scramble")],
        [InlineKeyboardButton("⚡️ Кто быстрее", callback_data="game:speed"),
         InlineKeyboardButton("🪢 Виселица", callback_data="game:hang")]])


async def on_game_btn(update, context):
    q = update.callback_query
    p = (q.data or "").split(":")
    if len(p) != 2 or p[1] not in GAME_START.values():
        return await q.answer()
    ok, text = game_launch(q.message.chat_id, q.from_user.id, p[1])
    if not ok:
        return await q.answer(text, show_alert=True)
    await q.answer()
    await context.bot.send_message(q.message.chat_id, text, parse_mode=HTML)


async def games_text(update, context, clean, text):
    chat_id = update.effective_chat.id
    me = update.effective_user
    g = GAMES.get(chat_id)
    if g and time.time() > g["until"]:
        GAMES.pop(chat_id, None)
        g = None
        await reply(update, "⌛ Время игры вышло, никто не справился.")
    if clean in GAME_LIST_WORDS:
        await reply(update, "🎮 <b>Мини-игры</b> для всех участников\n"
                            "Нажми кнопку или напиши: «угадай число», «анаграмма», «кто быстрее», «виселица».\n"
                            "Остановить: «стоп игра». Рейтинг побед: «топ игр»",
                    reply_markup=games_kb())
        return True
    if clean in ("топ игр", "рейтинг игр"):
        rows = db.execute("SELECT g.user_id, g.wins, u.name FROM game_wins g LEFT JOIN users u ON u.user_id=g.user_id "
                          "ORDER BY g.wins DESC LIMIT 10").fetchall()
        if not rows:
            await reply(update, "Пока никто не выигрывал. Начни: «мини игры» 🎮")
        else:
            await reply(update, "🏆 <b>Топ игроков</b>\n" + "\n".join(
                f"{i}. {link(r['user_id'], r['name'] or str(r['user_id']))}: {r['wins']}" for i, r in enumerate(rows, 1)))
        return True
    if clean in GAME_STOP_WORDS:
        if not g:
            return False
        if g["starter"] != me.id and rank_of(me) < 1:
            return False
        GAMES.pop(chat_id, None)
        await reply(update, "🛑 Игра остановлена.")
        return True
    if clean in GAME_START:
        ok, txt = game_launch(chat_id, me.id, GAME_START[clean])
        await reply(update, txt)
        return True
    if not g:
        return False
    kind = g["kind"]
    if kind == "number" and clean.isdigit() and len(clean) <= 4:
        v = int(clean)
        if v == g["n"]:
            GAMES.pop(chat_id, None)
            await game_win(update, me.id, disp(me), f"Число {v}! ")
        else:
            await reply(update, "⬆️ Больше" if v < g["n"] else "⬇️ Меньше")
        return True
    if kind in ("scramble", "speed") and clean == g["word"]:
        GAMES.pop(chat_id, None)
        await game_win(update, me.id, disp(me), f"Слово «{g['word']}». ")
        return True
    if kind == "hang":
        if clean == g["word"]:
            GAMES.pop(chat_id, None)
            await game_win(update, me.id, disp(me), f"Слово «{g['word']}». ")
            return True
        if len(clean) == 1 and clean.isalpha():
            if clean in g["opened"] or clean in g["wrong"]:
                return True
            if clean in g["word"]:
                g["opened"].add(clean)
                if all(c in g["opened"] for c in g["word"]):
                    GAMES.pop(chat_id, None)
                    await game_win(update, me.id, disp(me), f"Слово «{g['word']}». ")
                else:
                    await reply(update, f"✅ Есть такая буква!\n<code>{hang_mask(g)}</code>")
            else:
                g["wrong"].add(clean)
                left = HANG_MAX - len(g["wrong"])
                if left <= 0:
                    GAMES.pop(chat_id, None)
                    await reply(update, f"💀 Виселица победила. Слово было: <b>{g['word']}</b>")
                else:
                    await reply(update, f"❌ Нет такой буквы. Осталось ошибок: {left}\n"
                                        f"<code>{hang_mask(g)}</code>")
            return True
    return False


# ============================ МЕНЮ В ЛИЧКЕ БОТА (кнопки внизу) ============================
MENU_BTNS = ["📋 Команды", "🎮 Мини-игры", "💞 Отношения", "💼 Работа и монеты", "🛠 Для админов", "ℹ️ О боте"]
SECTION_GAMES = ("🎮 <b>Мини-игры</b> (для всех, прямо в чате)\n"
                 "• «мини игры»: меню с кнопками\n"
                 "• «угадай число»: бот загадывает 1–100, все пишут числа\n"
                 "• «анаграмма»: собери слово из перемешанных букв\n"
                 "• «кто быстрее»: кто первым напишет слово\n"
                 "• «виселица»: угадывайте слово по буквам\n"
                 "• «топ игр»: рейтинг побед, «стоп игра»: остановить\n"
                 "Ещё: /dice, /slots, /coin, «дуэль», викторина и квесты (/quests)")
SECTION_LOVE = ("💞 <b>Отношения и семья</b>\n"
                "«предложить отношения @юз» → кнопка «Да». Общий баланс пары это искры 🔥\n"
                "Для партнёра с точкой: «.поцеловать», «.обнять», «.взять за руку»; обычное «поцеловать @юз» без искр\n"
                "«свидание» (выбор места), «подарок партнёру», «моя пара», «список пар», «топ пар», «обида», «расстаться»\n"
                "💍 «предложить брак» → «принять брак», «семья», «развод», «свидетельство»\n"
                "В браке: «завести ребёнка», «дети», «семейный счёт», «в семью 100», «из семьи 100»\n"
                "🏠 «дом», 🐾 «купить питомца», «питомцы», «покормить питомца», «мойпол м/ж»")
SECTION_WORK = ("💼 <b>Работа и монеты</b>\n"
                "«найти работу», «работать» (мини-игра на смене), «моя работа», «уволиться»\n"
                "Должность растёт со сменами: Стажёр → Специалист → Старший → Эксперт → Мастер\n"
                "🪙 «баланс», «бонус» (раз в день), «магазин», «купить 1», «топ монет», «дуэли»")


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


# ============================ СТАТЬЯ С КОМАНДАМИ В TELEGRAPH ============================
DOC_VER = "24-1"          # поменяй, если правишь список ниже: бот сам обновит статью при запуске
DOC_TITLE = "Команды бота " + CHAT_TAG
DOC_SECTIONS = [
    ("📊 Активность и профиль", [
        ("/me, «профиль»", "твой профиль; ответом на сообщение или с @юз показывает чужой"),
        ("/top, /week, /month", "топы активности за день, неделю и месяц (можно словами: топ, неделя, месяц)"),
        ("/quests, «квесты»", "ежедневные задания"),
        ("+реп", "ответом на сообщение или «+реп @юз» — репутация"),
        ("/quiztop", "рейтинг викторины"),
        ("/анрег, /рег", "выйти из созыва или вернуться"),
        ("«правила»", "правила чата"),
    ]),
    ("🎭 РП-команды", [
        ("поцеловать @юз", "или ответом на сообщение. Без искр и без эффектов для отношений"),
        ("Список действий", "обнять, обнять крепко, поцеловать, погладить, дать пять, пожать руку, взять за руку, "
                            "пощекотать, ткнуть, покормить, помахать, похвалить, ударить, пнуть, укусить, отшлёпать, убить"),
        ("Картинка", "к действиям приходит гифка или картинка"),
    ]),
    ("💞 Отношения", [
        ("предложить отношения @юз", "потом у человека 2 минуты, чтобы нажать «Да» или «Нет» (или написать «принять» / «отказать»)"),
        (".поцеловать, .обнять, .взять за руку…", "действия с точкой работают на партнёра и дают искры 🔥"),
        ("«свидание»", "выбор места: парк, кино, ресторан, концерт; раз в день"),
        ("«подарок партнёру»", "или «подарить цветы / шоколад / мишку / украшение» — подарки за монеты, дают искры"),
        ("«моя пара», «пара @юз»", "профиль пары: искры, уровень, срок вместе, кнопки"),
        ("«список пар», «топ пар»", "все пары и рейтинги"),
        ("«обида»", "обидеться на партнёра (повтор снимает обиду, пока обида включена, действия недоступны)"),
        ("«расстаться»", "расторжение кнопкой"),
        ("«мойпол м» / «мойпол ж»", "пол для правильных окончаний в текстах"),
        ("Искры 🔥", "общий баланс пары: растёт от действий, свиданий, подарков и работы, тратится раз в сутки; на нуле пара распадается"),
    ]),
    ("💍 Брак и семья", [
        ("«предложить брак @юз»", "через пару дней отношений, нужны искры и монеты на свадьбу"),
        ("«принять брак» / «отказать в браке»", "ответ на предложение"),
        ("«свидетельство»", "картинка-свидетельство пары или брака"),
        ("«семья»", "профиль семьи"),
        ("«завести ребёнка», «дети», «назвать ребёнка Имя»", "дети в браке"),
        ("«семейный счёт», «в семью 100», «из семьи 100»", "общий счёт супругов"),
        ("«развод»", "расторжение брака"),
    ]),
    ("🏠 Дом и питомцы", [
        ("«дом»", "купить жильё: комната, квартира, дом, особняк. Даёт бонус к зарплате"),
        ("«купить питомца», «питомцы»", "кот, собака, хомяк, попугай, кролик, лиса"),
        ("«покормить питомца», «назвать питомца Имя»", "уход за питомцами; без кормления питомец убегает"),
    ]),
    ("💼 Работа", [
        ("«найти работу»", "вам предлагают работы; лучшие открываются по уровню, времени в чате и числу сообщений"),
        ("«работать»", "выйти на смену: мини-игра (курьер развозит заказы людям из чата, остальные решают задания)"),
        ("«моя работа», «уволиться»", "статус и смена работы"),
        ("Карьера", "Стажёр → Специалист (10 смен) → Старший (30) → Эксперт (70) → Мастер (150), с наградой за повышение"),
    ]),
    ("🪙 Монеты и игры", [
        ("«баланс», «бонус»", "кошелёк и ежедневный бонус"),
        ("«магазин», «купить 1»", "магазин подарков"),
        ("«топ монет», «дуэли»", "рейтинги"),
        ("/duel @юз, «дуэль»", "дуэль профилей"),
        ("/dice, /slots, /coin", "кости, слоты, монетка"),
        ("«мини игры»", "меню игр: угадай число, анаграмма, кто быстрее, виселица. «топ игр», «стоп игра»"),
        ("«репорт» + причина", "жалоба админам ответом на сообщение нарушителя"),
    ]),
    ("🎁 NFT", [
        ("!ссылка на NFT", "например «!t.me/nft/...»: карточка и анимация; можно несколько ссылок сразу"),
    ]),
    ("🛠 Для админов (по рангам)", [
        ("мут 30 @юз причина", "время: 30, 2ч, 1д. Также «размут», «список мута»"),
        ("бан, разбан", "ответом или @юз"),
        ("тег Текст, снять тег", "тег участнику"),
        ("повысить 2, разжаловать, админы", "ранги 1–8 (повысить только 8 ранг)"),
        ("дк мут 2", "с какого ранга доступна команда («дк» без цифры покажет все)"),
        ("добавить картинку обнять", "ответом на гифку, картинку или видео; для отношений: добавить картинку отн поцелуй"),
        ("список картинок, очистить картинки", "управление картинками действий"),
        ("добавить товар Мишка 500, удалить товар 1", "магазин; «заказы», «выдан 5»"),
        ("выдать монеты @юз 100", "отрицательное число забирает"),
        ("добавить работу Грузчик 45 3 ур=2", "оплата за смену, пауза в часах, условия ур=, дн=, сообщ=; «удалить работу», «список работ»"),
        ("журнал [N]", "последние действия админов"),
        ("установить приветствие Привет, {name}!", "приветствие новичков («выкл» отключает)"),
        ("установить правила Текст", "правила для команды «правила»"),
        ("статистика, статистика недели, слова дня, итоги", "статистика чата"),
        ("запустить вопрос, запустить викторину", "активности для чата"),
    ]),
]


def doc_nodes():
    nodes = [{"tag": "p", "children": [f"Все команды бота {CHAT_TAG}. Писать можно словами, без слеша, "
                                       "если не указано иное. «@юз» можно заменить ответом на сообщение."]}]
    for title, items in DOC_SECTIONS:
        nodes.append({"tag": "h3", "children": [title]})
        nodes.append({"tag": "ul", "children": [
            {"tag": "li", "children": [{"tag": "b", "children": [cmd]}, " — " + desc]} for cmd, desc in items]})
    nodes.append({"tag": "p", "children": [{"tag": "i", "children": ["Статья обновляется ботом автоматически."]}]})
    return nodes


async def telegraph_sync(force=False):
    """Создаёт или обновляет статью. -> ссылка или None."""
    import httpx
    if not force and state_get("tgph_ver") == DOC_VER and state_get("tgph_url"):
        return state_get("tgph_url")
    content = json.dumps(doc_nodes(), ensure_ascii=False)
    async with httpx.AsyncClient(timeout=25) as c:
        token = state_get("tgph_token")
        if not token:
            r = (await c.post("https://api.telegra.ph/createAccount", data={
                "short_name": "clavekbot", "author_name": CHAT_TAG})).json()
            if not r.get("ok"):
                raise RuntimeError(f"createAccount: {r}")
            token = r["result"]["access_token"]
            state_set("tgph_token", token)
        path = state_get("tgph_path")
        if path:
            r = (await c.post("https://api.telegra.ph/editPage", data={
                "access_token": token, "path": path, "title": DOC_TITLE, "content": content,
                "author_name": CHAT_TAG})).json()
            if not r.get("ok"):
                path = None          # статью не нашли, создадим заново
        if not path:
            r = (await c.post("https://api.telegra.ph/createPage", data={
                "access_token": token, "title": DOC_TITLE, "content": content,
                "author_name": CHAT_TAG})).json()
        if not r.get("ok"):
            raise RuntimeError(f"telegraph: {r}")
        state_set("tgph_path", r["result"]["path"])
        state_set("tgph_url", r["result"]["url"])
        state_set("tgph_ver", DOC_VER)
        return r["result"]["url"]


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


async def on_reaction_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rc = update.message_reaction_count
    if not rc or rc.chat.id not in ALLOWED:
        return
    total = sum(r.total_count for r in rc.reactions)
    db.execute("UPDATE msgs SET reactions=? WHERE message_id=?", (total, rc.message_id))
    db.commit()


async def on_error(update, context):
    log.error("Ошибка: %s", context.error, exc_info=context.error)


# ============================ ЗАПУСК ============================
async def post_init(app):
    me = await app.bot.get_me()
    print(f"Бот @{me.username} запущен")
    print(f"Основной чат: {CHAT_ID}" + (f", тестовый: {TEST_CHAT_ID}" if TEST_CHAT_ID else ""))
    oid = state_get("owner_id")
    print(f"Владелец: @{OWNER_USERNAME}" + (f" (id {oid})" if oid else
          " — id определится, когда он напишет в чат"))
    if MessageReactionHandler is None:
        print("! Старая версия библиотеки: «лучшее сообщение дня» не работает. "
              "Обнови: py -3.14 -m pip install -U python-telegram-bot")
    print("Бот должен быть АДМИНОМ чата (иначе он не видит реакции и не может мутить/банить).")
    try:
        url = await telegraph_sync()
        print(f"Статья с командами: {url}")
    except Exception as e:
        print("Статья в Telegraph не опубликована:", repr(e)[:200])
    app.create_task(scheduler(app))


def main():
    token = (os.environ.get("BOT_TOKEN") or os.environ.get("TOKEN") or TOKEN).strip()
    if not token:
        p = os.path.join(BASE, "token.txt")
        if os.path.exists(p):
            token = open(p, encoding="utf-8").read().strip()
    if not token:
        print("Нет токена. Вставь его в TOKEN в bot.py или положи в файл token.txt рядом с ботом.")
        return
    app = Application.builder().token(token).post_init(post_init).build()
    for name, fn in (
        ("start", cmd_start), ("help", cmd_help), ("id", cmd_id), ("me", cmd_me),
        ("top", cmd_top), ("week", cmd_week), ("month", cmd_month),
        ("quiztop", cmd_quiztop), ("quests", cmd_quests), ("coin", cmd_coin),
        ("slots", cmd_slots), ("dice", cmd_dice), ("duel", cmd_duel),
        ("admin", cmd_admin), ("mute", cmd_mute), ("unmute", cmd_unmute),
        ("ban", cmd_ban), ("unban", cmd_unban), ("tag", cmd_tag), ("untag", cmd_untag),
        ("stat", cmd_stat), ("topwords", cmd_topwords), ("award", cmd_award),
        ("question", cmd_question), ("quiz", cmd_quiz),
        ("mutelist", cmd_mutelist), ("promote", cmd_promote), ("demote", cmd_demote),
        ("access", cmd_access), ("admins", cmd_admins),
        ("balance", cmd_balance), ("bonus", cmd_bonus), ("shop", cmd_shop), ("buy", cmd_buy),
        ("topcoins", cmd_topcoins), ("duels", cmd_duels), ("report", cmd_report),
        ("additem", cmd_item_add), ("delitem", cmd_item_del), ("givecoins", cmd_coins_give),
        ("orders", cmd_orders), ("done", cmd_order_done),
    ):
        app.add_handler(CommandHandler(name, fn))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_members))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.UpdateType.MESSAGE, on_text))
    if MessageReactionHandler is not None:
        app.add_handler(MessageReactionHandler(
            on_reaction_count,
            message_reaction_types=MessageReactionHandler.MESSAGE_REACTION_COUNT_UPDATED))
    app.add_handler(CallbackQueryHandler(on_report_btn, pattern=r"^rp:"))
    app.add_handler(CallbackQueryHandler(on_life_btn, pattern=r"^life:"))
    app.add_handler(CallbackQueryHandler(on_rel_btn, pattern=r"^rel:"))
    app.add_handler(CallbackQueryHandler(on_date_btn, pattern=r"^date:"))
    app.add_handler(CallbackQueryHandler(on_game_btn, pattern=r"^game:"))
    app.add_handler(CallbackQueryHandler(on_gift_btn, pattern=r"^gift:"))
    app.add_error_handler(on_error)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
