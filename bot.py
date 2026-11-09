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
from datetime import datetime, timedelta, timezone

from telegram import (ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup,
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
    "/duel — дуэль профилей (ответом на сообщение)\n"
    "!ссылка на NFT (t.me/nft/...) — карточка и анимация NFT; также «гиф ссылка»\n"
    "/dice — кости против другого (ответом), /slots, /coin\n"
    "/quiztop — рейтинг викторины\n"
    "РП (ответом на сообщение, с гифкой): обнять, обнять крепко, поцеловать, погладить, "
    "дать пять, пожать руку, взять за руку, пощекотать, ткнуть, покормить, помахать, "
    "похвалить, ударить, пнуть, укусить, отшлёпать, убить\n"
    "💞 Отношения (ответом на сообщение человека): «предложить отношения», потом он пишет "
    "«принять» или «отказать». Дальше: «моя пара», «свидание», «поцеловать», «обнять», "
    "«расстаться», «топ пар». Без внимания любовь угасает, и пара может распасться\n\n"
    "🪙 Монеты: «баланс», «бонус» (раз в день), «магазин», «купить 1», «топ монет», «дуэли»\n"
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
             "duel_l INTEGER DEFAULT 0", "bonus_day TEXT DEFAULT ''"):
    try:
        db.execute("ALTER TABLE users ADD COLUMN " + _col)
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
        ("relations", REL_TIME, lambda: rel_daily(bot)),
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
    await update.effective_message.reply_text(START_TEXT)


async def cmd_help(update, context):
    await reply(update, HELP_TEXT)


async def cmd_id(update, context):
    cid = update.effective_chat.id
    ok = "✅ бот тут работает" if cid in ALLOWED else "❌ бот здесь молчит: этот чат не совпадает с CHAT_ID в коде"
    await update.effective_message.reply_text(
        f"ID этого чата: {cid}\n{ok}\nCHAT_ID в коде: {CHAT_ID}\nверсия: 13")


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


def target_user(update):
    """Пользователь из ответа на сообщение (не бот)."""
    m = update.effective_message
    if m.reply_to_message and m.reply_to_message.from_user:
        u = m.reply_to_message.from_user
        if not u.is_bot:
            touch(u)
            return u
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


def _cards_to_gif(items, out):
    """items — список (lottie_json_str, bg). Рисует карточки как в подборках NFT:
    скруглённые плитки с мягким свечением на тёмном фоне. Одна — по центру, несколько — сеткой."""
    from PIL import Image, ImageDraw
    from rlottie_python import LottieAnimation
    k = len(items)
    anims = [LottieAnimation.from_data(it[0]) for it in items]
    totals = [max(1, a.lottie_animation_get_totalframe()) for a in anims]
    fps = anims[0].lottie_animation_get_framerate() or 30
    if k == 1:
        S, W, H, cols, gap = 300, 640, 360, 1, 0
    else:
        S, gap, cols = 200, 14, min(3, k)
        rows = (k + cols - 1) // cols
        W, H = cols * S + (cols + 1) * gap, rows * S + (rows + 1) * gap
    base = Image.new("RGB", (W, H), (22, 19, 21))
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
            pos.append(((W - S) // 2, (H - S) // 2))
        else:
            pos.append((gap + c * (S + gap), gap + r * (S + gap)))
    n = max(totals)
    step = max(1, n // 90)
    gs = int(S * 0.8)
    frames = []
    for i in range(0, n, step):
        canvas = base.copy()
        for j, a in enumerate(anims):
            fr = a.render_pillow_frame(frame_num=i % totals[j], width=gs, height=gs).convert("RGBA")
            t = tiles[j].convert("RGBA")
            t.alpha_composite(fr, ((S - gs) // 2, (S - gs) // 2))
            canvas.paste(t.convert("RGB"), pos[j], rmask)
        frames.append(canvas.convert("P", palette=Image.ADAPTIVE, colors=200))
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
    u = target_user(update)
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
    return None


def pic_names_text():
    return ("РП-действия: " + ", ".join(RP) + "\n\nОтношения (пиши с «отн »):\n" +
            "\n".join(f"отн {k} — {v}" for k, v in REL_EVENTS.items()))


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


async def send_with_pic(bot, chat_id, text, actions, reply_to=None, api_cat=None):
    """Картинка к сообщению. Порядок: свои картинки из базы -> файлы из папки rp ->
    гифка с nekos.best -> просто текст."""
    rp = ReplyParameters(message_id=reply_to, allow_sending_without_reply=True) if reply_to else None

    async def send(kind, media):
        kw = dict(caption=text, parse_mode=HTML, reply_parameters=rp)
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
    return await bot.send_message(chat_id, text, parse_mode=HTML,
                                  link_preview_options=NOPREV, reply_parameters=rp)


async def handle_rp(update, context, key):
    me = update.effective_user
    other = target_user(update)
    if not other:
        return await reply(update, f"Ответь словом «{key}» на сообщение того, к кому обращаешься")
    if other.id == me.id:
        return await reply(update, "Давай лучше кого-нибудь другого 🙂")
    tpl, emoji = RP[key]
    text = emoji + " " + tpl.format(a=link(me.id, disp(me)), b=link(other.id, disp(other)))
    actions = [key]
    gain = REL_GAIN.get(key)
    if gain:
        res = rel_add(me.id, other.id, gain)
        if res is not None:
            add, love = res
            text += (f"\n💞 +{add} к любви ({love}/100)" if add
                     else "\n💞 На сегодня лимит любви набран")
            if key in REL_PIC:
                actions.insert(0, "отн:" + REL_PIC[key])
    await send_with_pic(context.bot, update.effective_chat.id, text, actions,
                        reply_to=update.effective_message.message_id, api_cat=RP_API.get(key))


# ============================ ОТНОШЕНИЯ ============================
REL_START, REL_DAILY_CAP, REL_DATE_GAIN, REL_DECAY, REL_WARN_BELOW = 30, 30, 15, 5, 30
REL_TIME = (10, 15)            # когда раз в день проверять, кто забросил партнёра
REL_GAIN = {"поцеловать": 10, "обнять": 6, "обнять крепко": 8, "взять за руку": 5,
            "погладить": 4, "покормить": 3, "пощекотать": 3, "похвалить": 3, "помахать": 1}
REL_PIC = {"поцеловать": "поцелуй", "обнять": "объятие", "обнять крепко": "объятие"}
REL_EVENTS = {
    "предложение": "кто-то предложил отношения",
    "пара": "предложение принято, пара создана",
    "поцелуй": "партнёры целуются (команда «поцеловать»)",
    "объятие": "партнёры обнимаются (команды «обнять»)",
    "свидание": "команда «свидание»",
    "скучаю": "напоминание: давно не было внимания",
    "расставание": "расставание",
}
PROPOSE = {"предложить отношения", "предложить встречаться", "встречаться"}
ACCEPT = {"принять", "принимаю", "согласна", "согласен"}
DECLINE = {"отказать", "отказываюсь", "отказаться"}
LEAVE = {"расстаться", "расстаёмся", "расстаемся", "порвать отношения"}
STATUS_SELF = {"моя пара", "мои отношения"}
STATUS_OTHER = {"пара", "отношения"}   # только ответом на сообщение человека
DATE_WORDS = {"свидание", "пойти на свидание"}
TOPPAIRS = {"топ пар"}


def pair_of(uid):
    return db.execute("SELECT * FROM pairs WHERE a=? OR b=?", (uid, uid)).fetchone()


def partner_of(row, uid):
    return row["b"] if row["a"] == uid else row["a"]


def uname(uid):
    r = urow(uid)
    return r["name"] if r else str(uid)


def love_bar(n):
    full = max(0, min(10, round(n / 10)))
    return "💗" * full + "🤍" * (10 - full) + f" {n}/100"


def rel_add(uid, other, amount):
    """Начислить любовь, если uid и other — пара. -> (начислено, всего) или None."""
    row = pair_of(uid)
    if not row or partner_of(row, uid) != other:
        return None
    d = today()
    gain = row["gain"] if row["gain_day"] == d else 0
    add = max(0, min(amount, REL_DAILY_CAP - gain))
    love = min(100, row["love"] + add)
    db.execute("UPDATE pairs SET love=?, gain=?, gain_day=?, last_action=? WHERE id=?",
               (love, gain + add, d, time.time(), row["id"]))
    db.commit()
    return add, love


async def handle_relation(update, context, low):
    clean = re.sub(r"[!.?,]+$", "", low).strip()
    if not (clean in PROPOSE or clean in ACCEPT or clean in DECLINE or clean in LEAVE
            or clean in STATUS_SELF or clean in STATUS_OTHER or clean in DATE_WORDS
            or clean in TOPPAIRS):
        return False
    msg, me, chat = update.effective_message, update.effective_user, update.effective_chat
    bot = context.bot

    async def say(text, pic=None):
        await send_with_pic(bot, chat.id, text, ["отн:" + pic] if pic else [],
                            reply_to=msg.message_id)

    if clean in PROPOSE:
        other = target_user(update)
        if not other or other.id == me.id:
            await say("Ответь этими словами на сообщение человека: «предложить отношения» 💌")
        elif pair_of(me.id):
            await say("Ты уже в отношениях. Сначала «расстаться».")
        elif pair_of(other.id):
            await say(f"У {esc(disp(other))} уже есть пара.")
        else:
            db.execute("INSERT OR REPLACE INTO proposals(to_id,from_id,created,msg_id) "
                       "VALUES(?,?,?,?)", (other.id, me.id, time.time(), msg.message_id))
            db.commit()
            await say(f"💌 {link(me.id, disp(me))} предлагает отношения "
                      f"{link(other.id, disp(other))}!\nОтветь «принять» или «отказать» "
                      f"(24 часа).", "предложение")
        return True

    if clean in ACCEPT or clean in DECLINE:
        pr = db.execute("SELECT * FROM proposals WHERE to_id=?", (me.id,)).fetchone()
        if not pr:
            return False
        db.execute("DELETE FROM proposals WHERE to_id=?", (me.id,))
        db.commit()
        if time.time() - pr["created"] > 86400:
            return False
        a = pr["from_id"]
        if clean in DECLINE:
            await say(f"💔 {link(me.id, disp(me))} отказал(а) {link(a, uname(a))}.")
        elif pair_of(a) or pair_of(me.id):
            await say("Кто-то из вас уже в отношениях.")
        else:
            db.execute("INSERT INTO pairs(a,b,love,since,last_action) VALUES(?,?,?,?,?)",
                       (a, me.id, REL_START, time.time(), time.time()))
            db.commit()
            await say(f"💞 {link(a, uname(a))} и {link(me.id, disp(me))} теперь пара!\n"
                      f"{love_bar(REL_START)}\nУделяйте друг другу внимание: «поцеловать», "
                      f"«обнять», «свидание». Без внимания любовь угасает.", "пара")
        return True

    if clean in LEAVE:
        row = pair_of(me.id)
        if not row:
            return False
        else:
            p = partner_of(row, me.id)
            db.execute("DELETE FROM pairs WHERE id=?", (row["id"],))
            db.commit()
            await say(f"💔 {link(me.id, disp(me))} расстался(ась) с {link(p, uname(p))}.",
                      "расставание")
        return True

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
            p = partner_of(row, u.id)
            days = int((time.time() - row["since"]) // 86400) + 1
            await say(f"💞 <b>Пара:</b> {link(u.id, disp(u))} и {link(p, uname(p))}\n"
                      f"{love_bar(row['love'])}\n📅 Вместе: {days} дн.\n"
                      f"🕰 Последнее внимание: {fmt_when(row['last_action'])}")
        return True

    if clean in DATE_WORDS:
        row = pair_of(me.id)
        if not row:
            return False
        elif row["date_day"] == today():
            await say("Сегодня вы уже ходили на свидание 🌹")
        else:
            p = partner_of(row, me.id)
            love = min(100, row["love"] + REL_DATE_GAIN)
            db.execute("UPDATE pairs SET love=?, date_day=?, last_action=? WHERE id=?",
                       (love, today(), time.time(), row["id"]))
            db.commit()
            await say(f"🌹 {link(me.id, disp(me))} и {link(p, uname(p))} сходили на свидание! "
                      f"+{REL_DATE_GAIN} к любви\n{love_bar(love)}", "свидание")
        return True

    rows = db.execute("SELECT * FROM pairs ORDER BY love DESC, since LIMIT 10").fetchall()
    if not rows:
        await say("Пока нет ни одной пары 💔")
    else:
        await say("💞 <b>Топ пар</b>\n" + "\n".join(
            f"{i}. {esc(uname(r['a']))} ❤ {esc(uname(r['b']))} — {r['love']}/100"
            for i, r in enumerate(rows, 1)))
    return True


async def rel_daily(bot):
    """Раз в день: у кого не было внимания больше суток, любовь падает."""
    now_ts = time.time()
    for row in db.execute("SELECT * FROM pairs").fetchall():
        if now_ts - (row["last_action"] or row["since"]) < 86400:
            continue
        love = max(0, row["love"] - REL_DECAY)
        a, b = row["a"], row["b"]
        names = f"{link(a, uname(a))} и {link(b, uname(b))}"
        try:
            if love <= 0:
                db.execute("DELETE FROM pairs WHERE id=?", (row["id"],))
                db.commit()
                await send_with_pic(bot, CHAT_ID, f"💔 {names} расстались: без внимания любовь угасла.",
                                    ["отн:расставание"])
            else:
                db.execute("UPDATE pairs SET love=? WHERE id=?", (love, row["id"]))
                db.commit()
                if love <= REL_WARN_BELOW:
                    await send_with_pic(
                        bot, CHAT_ID,
                        f"🥀 {names}, вы давно не уделяли друг другу внимание.\n{love_bar(love)}\n"
                        f"Напишите «поцеловать» или «свидание», пока не поздно!", ["отн:скучаю"])
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
    "дуэли": cmd_duels, "бонус": cmd_bonus, "репорт": cmd_report, "жалоба": cmd_report,
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
        return
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

    if low in RP:
        return await handle_rp(update, context, low)

    if await handle_relation(update, context, low):
        return

    if await run_alias(update, context, low, text):
        return

    if low in ("профиль", "мой профиль"):
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
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.UpdateType.MESSAGE, on_text))
    if MessageReactionHandler is not None:
        app.add_handler(MessageReactionHandler(
            on_reaction_count,
            message_reaction_types=MessageReactionHandler.MESSAGE_REACTION_COUNT_UPDATED))
    app.add_handler(CallbackQueryHandler(on_report_btn, pattern=r"^rp:"))
    app.add_error_handler(on_error)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
