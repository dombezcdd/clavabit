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

from telegram import (ChatPermissions, LinkPreviewOptions, ReplyParameters,
                      Update)
from telegram.constants import ParseMode
from telegram.ext import (Application, CommandHandler, ContextTypes,
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
AD_EVERY_MIN = 60               # реклама канала: раз в N минут
INVITE_EVERY_MIN = 90           # напоминание про приглашения: раз в N минут
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
    "РП: обнять, ударить, погладить, дать пять, пожать руку, укусить, "
    "обнять крепко, пнуть (ответом на сообщение)\n"
    "/анрег — выйти из созыва, /рег — вернуться\n\n"
    "💡 Можно писать словами без слеша (сообщение целиком): "
    "профиль, топ, неделя, месяц, квесты, дуэль, кости, слоты, монетка, помощь"
)

ADMIN_HELP = (
    "🛠 <b>Админ-панель</b> (только владелец)\n"
    "/mute [минуты] — ответом, по умолчанию 60\n"
    "/unmute — ответом\n"
    "/ban, /unban — ответом\n"
    "/tag текст — выдать тег (ответом), /untag — снять\n"
    "/stat — активность чата\n"
    "/topwords — о чём чат говорил сегодня (общие слова)\n"
    "/award — итоги прямо сейчас\n"
    "/question, /quiz — запустить вручную\n\n"
    "💡 Словами (только от владельца): мут 30, размут, бан, разбан, тег Текст, "
    "снять тег, статистика, слова дня, итоги, запустить вопрос, запустить викторину"
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
""")
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
    if len(done) >= 3 and "ALL" not in done:
        db.execute("INSERT OR IGNORE INTO quest_done VALUES(?,?,?)", (d, uid, "ALL"))
        db.commit()
        out.append(f"🏅 {link(uid, u['name'])} выполнил ВСЕ квесты дня! (+{QUEST_ALL_BONUS_XP} опыта)")
        out += give_xp(uid, QUEST_ALL_BONUS_XP)
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
    for name, (h, m), fn in (
        ("question", QUESTION_TIME, lambda: post_question(bot)),
        ("quiz", QUIZ_TIME, lambda: post_quiz(bot)),
        ("summary", SUMMARY_TIME, lambda: send_summary(bot, d, True)),
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
    for name, minutes, fn in (
        ("ad", AD_EVERY_MIN, post_ad),
        ("invite", INVITE_EVERY_MIN, post_invite),
    ):
        last = state_get("last_" + name)
        if last is None:
            state_set("last_" + name, time.time())
            continue
        if time.time() - float(last) >= minutes * 60:
            if quiet:
                continue
            state_set("last_" + name, time.time())
            await fn(bot)


async def scheduler(app):
    await asyncio.sleep(5)
    while True:
        try:
            await tick(app)
        except Exception:
            log.exception("tick")
        await asyncio.sleep(30)


async def post_ad(bot):
    await send_text(bot, f"📢 Не забудьте подписаться на наш канал, чтобы не пропускать важные "
                         f"розыгрыши! {esc(CHANNEL)}")


async def post_invite(bot):
    ids = [r["user_id"] for r in db.execute(
        "SELECT user_id FROM users WHERE registered=1 AND total>0")]
    text = ("🎁 Приглашайте друзей в чат — за приглашения можно получить подарки! "
            f"Подробности: @{OWNER_USERNAME}\n"
            "Не хотите получать напоминания — напишите /анрег")
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
        f"ID этого чата: {cid}\n{ok}\nCHAT_ID в коде: {CHAT_ID}\nверсия: 3")


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
    return (
        f"👤 Это пользователь {name}\n{tag}"
        f"👨🏻‍🔧 {role}\n\n"
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
        db.execute("UPDATE users SET game_pts=game_pts+? WHERE user_id=?", (pts, uid))
        db.commit()
    await reply(update, text)
    await played(context.bot, uid)


@group_only
async def cmd_dice(update, context):
    me = update.effective_user
    other = target_user(update)
    if not other or other.id == me.id:
        return await reply(update, "Ответь командой /dice на сообщение соперника 🎲")
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
        db.execute("UPDATE users SET game_pts=game_pts+1 WHERE user_id=?", (win["user_id"],))
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


def _frames_to_gif(frames, fps, out):
    step = max(1, len(frames) // 90)          # не больше ~90 кадров
    frames = frames[::step]
    frames[0].save(out, save_all=True, append_images=frames[1:], loop=0,
                   duration=int(1000 / max(fps, 1) * step), disposal=2, optimize=False)


def _lottie_to_gif(data, out, bg):
    """data — JSON-строка Lottie. Требует пакеты rlottie-python и Pillow."""
    from PIL import Image
    from rlottie_python import LottieAnimation
    anim = LottieAnimation.from_data(data)
    total = anim.lottie_animation_get_totalframe()
    fps = anim.lottie_animation_get_framerate() or 30
    size = 384
    frames = []
    for i in range(total):
        fr = anim.render_pillow_frame(frame_num=i, width=size, height=size).convert("RGBA")
        base = Image.new("RGBA", fr.size, bg + (255,))
        base.alpha_composite(fr)
        frames.append(base.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=200))
    _frames_to_gif(frames, fps, out)


async def fetch_nft_gif(name, num):
    """Возвращает путь к gif или None."""
    import gzip
    import httpx
    slug = f"{name}-{num}".lower()
    page = f"https://t.me/nft/{name}-{num}"
    cands, bg = [], (45, 45, 55)
    async with httpx.AsyncClient(timeout=25, follow_redirects=True,
                                 headers={"User-Agent": "Mozilla/5.0"}) as c:
        try:
            r = await c.get(page)
            txt = html.unescape(r.text)
            cands += re.findall(r'https?://[^\s"\'<>\\)]+\.(?:tgs|json|webm|mp4|gif)(?:\?[^\s"\'<>\\)]*)?', txt)
            mm = re.search(r'og:image"\s+content="([^"]+)"', txt)
            if mm:
                try:
                    from io import BytesIO
                    from PIL import Image
                    im = Image.open(BytesIO((await c.get(mm.group(1))).content)).convert("RGB")
                    bg = im.getpixel((6, 6))
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
                out = os.path.join(BASE, f"nft_{slug}.gif")
                path = u.split("?")[0].lower()
                if path.endswith((".mp4", ".gif")):
                    out = os.path.join(BASE, f"nft_{slug}" + path[-4:])
                    open(out, "wb").write(r.content)
                    return out
                if path.endswith(".webm"):
                    continue
                raw = r.content
                if raw[:2] == b"\x1f\x8b":
                    raw = gzip.decompress(raw)
                await asyncio.to_thread(_lottie_to_gif, raw.decode("utf-8"), out, bg)
                return out
            except ImportError:
                print("NFT: не установлены rlottie-python/Pillow. Выполни: "
                      "py -m pip install rlottie-python Pillow")
                return None
            except Exception as e:
                print("NFT: источник не подошёл:", u, "->", repr(e)[:200])
    return None


async def handle_nft(update, context, m, text):
    name, num = m.group(1), m.group(2)
    pretty = re.sub(r"(?<!^)(?=[A-Z])", " ", name)
    url = f"https://t.me/nft/{name}-{num}"
    try:
        await context.bot.send_chat_action(update.effective_chat.id, "upload_video")
        gif = await fetch_nft_gif(name, num)
    except Exception as e:
        print("NFT: ошибка:", repr(e)[:200])
        gif = None
    if gif:
        try:
            with open(gif, "rb") as f:
                await update.effective_message.reply_animation(
                    f, caption=f"🎁 <b>{esc(pretty)}</b> #{esc(num)}\n"
                               f"Запросил: {link(update.effective_user.id, disp(update.effective_user))}",
                    parse_mode=HTML)
            return
        except Exception as e:
            print("NFT: не удалось отправить gif:", repr(e)[:200])
        finally:
            try:
                os.remove(gif)
            except OSError:
                pass
    await update.effective_message.reply_text(
        f"🎁 <b>{esc(pretty)}</b> #{esc(num)}\n"
        f"<a href=\"{url}\">Открыть NFT</a>\n"
        f"Запросил: {link(update.effective_user.id, disp(update.effective_user))}",
        parse_mode=HTML,
        link_preview_options=LinkPreviewOptions(
            url=url, prefer_large_media=True, show_above_text=True))


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
    db.execute("UPDATE users SET game_pts=game_pts+2 WHERE user_id=?", (win["user_id"],))
    db.commit()
    await reply(update,
                f"⚔️ <b>Дуэль профилей</b>\n"
                f"{esc(ra['name'])}: <b>{sa}</b> ({fmt(pa)})\n"
                f"{esc(rb['name'])}: <b>{sb}</b> ({fmt(pb)})\n\n"
                f"🏆 Побеждает {link(win['user_id'], win['name'])} (+2 игровых очка)\n"
                f"<i>В счёт идут: аватарка, описание, юзернейм, уровень, репутация, олдство, тег, "
                f"NFT-подарки и обычные подарки из профиля + немного удачи. "
                f"Скрытые подарки бот не видит. NFT-юзернейм отличить нельзя.</i>")
    await played(context.bot, me.id)
    await played(context.bot, other.id)


# ---------- админ-панель ----------
@owner_only
async def cmd_admin(update, context):
    await reply(update, ADMIN_HELP)


def admin_target(update, context):
    u = target_user(update)
    if u:
        return u.id, disp(u)
    for a in context.args or []:
        if a.startswith("@"):
            r = find_by_username(a)
            if r:
                return r["user_id"], r["name"]
        elif a.isdigit() and len(a) > 5:
            r = urow(int(a))
            return int(a), r["name"] if r else a
    return None, None


@owner_only
async def cmd_mute(update, context):
    uid, name = admin_target(update, context)
    if not uid:
        return await reply(update, "Ответь командой на сообщение участника: /mute [минуты]")
    minutes = 60
    for a in context.args or []:
        if a.isdigit() and len(a) <= 6:
            minutes = int(a)
            break
    try:
        await context.bot.restrict_chat_member(
            update.effective_chat.id, uid, ChatPermissions.no_permissions(),
            until_date=int(time.time() + minutes * 60))
        await reply(update, f"🔇 {esc(name)} в муте на {minutes} мин.")
    except Exception as e:
        await reply(update, f"Не вышло: {esc(e)}\nПроверь, что у бота есть права админа.")


@owner_only
async def cmd_unmute(update, context):
    uid, name = admin_target(update, context)
    if not uid:
        return await reply(update, "Ответь командой на сообщение участника: /unmute")
    try:
        await context.bot.restrict_chat_member(
            update.effective_chat.id, uid, ChatPermissions.all_permissions())
        await reply(update, f"🔊 {esc(name)} размучен.")
    except Exception as e:
        await reply(update, f"Не вышло: {esc(e)}")


@owner_only
async def cmd_ban(update, context):
    uid, name = admin_target(update, context)
    if not uid:
        return await reply(update, "Ответь командой на сообщение участника: /ban")
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, uid)
        await reply(update, f"⛔ {esc(name)} забанен.")
    except Exception as e:
        await reply(update, f"Не вышло: {esc(e)}")


@owner_only
async def cmd_unban(update, context):
    uid, name = admin_target(update, context)
    if not uid:
        return await reply(update, "Ответь командой на сообщение или укажи id: /unban 123456789")
    try:
        await context.bot.unban_chat_member(update.effective_chat.id, uid, only_if_banned=True)
        await reply(update, f"✅ {esc(name)} разбанен.")
    except Exception as e:
        await reply(update, f"Не вышло: {esc(e)}")


@owner_only
async def cmd_tag(update, context):
    uid, name = admin_target(update, context)
    if not uid:
        return await reply(update, "Ответь на сообщение участника: /tag Текст тега")
    words = [a for a in (context.args or []) if not a.startswith("@") and not a.isdigit()]
    tag = " ".join(words).strip()[:30]
    if not tag:
        return await reply(update, "Напиши текст тега: /tag Текст")
    if not urow(uid):
        return await reply(update, "Этот участник ещё не писал в чат.")
    db.execute("UPDATE users SET tag=? WHERE user_id=?", (tag, uid))
    db.commit()
    await reply(update, f"🏷 Тег для {esc(name)}: <b>{esc(tag)}</b>")


@owner_only
async def cmd_untag(update, context):
    uid, name = admin_target(update, context)
    if not uid:
        return await reply(update, "Ответь на сообщение участника: /untag")
    db.execute("UPDATE users SET tag='' WHERE user_id=?", (uid,))
    db.commit()
    await reply(update, f"Тег у {esc(name)} снят.")


@owner_only
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


@owner_only
async def cmd_topwords(update, context):
    rows = db.execute("SELECT word, cnt FROM words WHERE day=? ORDER BY cnt DESC LIMIT 15",
                      (today(),)).fetchall()
    if not rows:
        return await reply(update, "Пока мало данных.")
    await reply(update, "💬 <b>О чём говорят сегодня</b>\n" +
                ", ".join(f"{esc(r['word'])} ({r['cnt']})" for r in rows))


@owner_only
async def cmd_award(update, context):
    await send_summary(context.bot, today(), False)


@owner_only
async def cmd_question(update, context):
    await post_question(context.bot)


@owner_only
async def cmd_quiz(update, context):
    await post_quiz(context.bot)


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
        return await reply(update, "Ответь на сообщение участника: «+реп» или напиши «+реп @юз»")
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


async def handle_rp(update, context, key):
    me = update.effective_user
    other = target_user(update)
    if not other:
        return await reply(update, f"Ответь словом «{key}» на сообщение того, к кому обращаешься")
    if other.id == me.id:
        return await reply(update, "Давай лучше кого-нибудь другого 🙂")
    tpl, emoji = RP[key]
    text = emoji + " " + tpl.format(a=link(me.id, disp(me)), b=link(other.id, disp(other)))
    folder = os.path.join(BASE, RP_DIR)
    for ext in ("gif", "mp4", "jpg", "png", "webp"):
        p = os.path.join(folder, f"{key}.{ext}")
        if os.path.exists(p):
            try:
                with open(p, "rb") as f:
                    if ext in ("gif", "mp4"):
                        await update.effective_message.reply_animation(f, caption=text, parse_mode=HTML)
                    else:
                        await update.effective_message.reply_photo(f, caption=text, parse_mode=HTML)
                return
            except Exception:
                log.exception("rp media")
                break
    await reply(update, text)


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
}
# слово -> (команда, сколько слов-аргументов можно дописать)
OWNER_ALIASES = {
    "админка": (cmd_admin, 0), "админ панель": (cmd_admin, 0),
    "мут": (cmd_mute, 1), "размут": (cmd_unmute, 0),
    "бан": (cmd_ban, 0), "разбан": (cmd_unban, 1),
    "тег": (cmd_tag, 5), "снять тег": (cmd_untag, 0),
    "статистика": (cmd_stat, 0), "слова дня": (cmd_topwords, 0),
    "итоги": (cmd_award, 0),
    "запустить вопрос": (cmd_question, 0), "запустить викторину": (cmd_quiz, 0),
}


def set_args(context, args):
    try:
        context.args = args
    except AttributeError:
        context._args = args


async def run_alias(update, context, low):
    clean = re.sub(r"[!.?,]+$", "", low).strip()
    fn = USER_ALIASES.get(clean)
    if fn:
        set_args(context, [])
        await fn(update, context)
        return True
    words = clean.split()
    for n in (2, 1):
        key = " ".join(words[:n])
        item = OWNER_ALIASES.get(key)
        if item and len(words) - n <= item[1]:
            if is_owner(update.effective_user):
                set_args(context, words[n:])
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
        return await handle_nft(update, context, nm, text)

    m = REP_RE.match(low)
    if m:
        return await handle_rep(update, context, m)

    if low in RP:
        return await handle_rp(update, context, low)

    if await run_alias(update, context, low):
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
    ):
        app.add_handler(CommandHandler(name, fn))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.UpdateType.MESSAGE, on_text))
    if MessageReactionHandler is not None:
        app.add_handler(MessageReactionHandler(
            on_reaction_count,
            message_reaction_types=MessageReactionHandler.MESSAGE_REACTION_COUNT_UPDATED))
    app.add_error_handler(on_error)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
