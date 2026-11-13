# -*- coding: utf-8 -*-
"""Мини-игры в чате: монетка, слоты, кости и игры со словами и числами."""

import asyncio
import random
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import HTML
from core.antispam import cooldown
from core.helpers import group_only, reply
from core.logger import log
from core.ranks import rank_of
from core.utils import disp, link
from database.db import db
from handlers.duel import played, send_challenge


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
    await send_challenge(update, context, "dice")


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


def hang_mask(g):
    return " ".join(c if c in g["opened"] else "_" for c in g["word"])


async def game_end(bot, g):
    for u in set(g.get("players", set())):
        try:
            await played(bot, u)
        except Exception:
            log.exception("game played")


async def game_win(update, uid, name, extra="", bot=None, g=None):
    db.execute("INSERT INTO game_wins(user_id,wins) VALUES(?,1) ON CONFLICT(user_id) DO UPDATE SET wins=wins+1", (uid,))
    db.commit()
    w = db.execute("SELECT wins FROM game_wins WHERE user_id=?", (uid,)).fetchone()["wins"]
    await reply(update, f"🏆 {link(uid, name)} побеждает! {extra}Побед в играх: {w}")
    if bot is not None and g is not None:
        g.setdefault("players", set()).add(uid)
        await game_end(bot, g)


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
        await game_end(context.bot, g)
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
        await game_end(context.bot, g)
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
        g.setdefault("players", set()).add(me.id)
        if v == g["n"]:
            GAMES.pop(chat_id, None)
            await game_win(update, me.id, disp(me), f"Число {v}! ", context.bot, g)
        else:
            await reply(update, "⬆️ Больше" if v < g["n"] else "⬇️ Меньше")
        return True
    if kind in ("scramble", "speed") and clean == g["word"]:
        GAMES.pop(chat_id, None)
        await game_win(update, me.id, disp(me), f"Слово «{g['word']}». ", context.bot, g)
        return True
    if kind == "hang":
        if clean == g["word"]:
            GAMES.pop(chat_id, None)
            await game_win(update, me.id, disp(me), f"Слово «{g['word']}». ", context.bot, g)
            return True
        if len(clean) == 1 and clean.isalpha():
            g.setdefault("players", set()).add(me.id)
            if clean in g["opened"] or clean in g["wrong"]:
                return True
            if clean in g["word"]:
                g["opened"].add(clean)
                if all(c in g["opened"] for c in g["word"]):
                    GAMES.pop(chat_id, None)
                    await game_win(update, me.id, disp(me), f"Слово «{g['word']}». ", context.bot, g)
                else:
                    await reply(update, f"✅ Есть такая буква!\n<code>{hang_mask(g)}</code>")
            else:
                g["wrong"].add(clean)
                left = HANG_MAX - len(g["wrong"])
                if left <= 0:
                    GAMES.pop(chat_id, None)
                    await game_end(context.bot, g)
                    await reply(update, f"💀 Виселица победила. Слово было: <b>{g['word']}</b>")
                else:
                    await reply(update, f"❌ Нет такой буквы. Осталось ошибок: {left}\n"
                                        f"<code>{hang_mask(g)}</code>")
            return True
    return False
