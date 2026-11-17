# -*- coding: utf-8 -*-
"""Звание, ник, анкета (город, день рождения), «−реп», погода и поздравления с днём рождения."""

import asyncio
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime

from config import ALLOWED, CHAT_ID
from core.helpers import reply, target_user
from core.logger import log
from core.utils import disp, esc, find_by_username, link, now, today, touch, urow
from database.db import db
from database.state import state_get, state_set
from services.clans import clan_of
from services.economy import COIN, give_coins
from services.xp import bump

TEXT_MAX = 30
WEATHER_WORDS = {0: "☀️ ясно", 1: "🌤 малооблачно", 2: "⛅️ переменная облачность", 3: "☁️ пасмурно",
                 45: "🌫 туман", 48: "🌫 туман", 51: "🌦 морось", 53: "🌦 морось", 55: "🌦 морось",
                 61: "🌧 дождь", 63: "🌧 дождь", 65: "🌧 сильный дождь", 71: "🌨 снег", 73: "🌨 снег",
                 75: "❄️ сильный снег", 80: "🌦 ливень", 81: "🌧 ливень", 82: "⛈ сильный ливень",
                 95: "⛈ гроза", 96: "⛈ гроза с градом", 99: "⛈ гроза с градом"}
BDAY_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?$")


def _clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def _who(update):
    t = target_user(update)
    return t if t else update.effective_user


async def handle_profile_text(update, context, low, text):
    if update.effective_chat.id not in ALLOWED:
        return False
    me = update.effective_user
    orig = text.strip()
    word, _, rest_low = low.partition(" ")
    rest = orig.partition(" ")[2].strip()
    if word == "звание":
        return await _set_text(update, me, "ztitle", "звание", rest, rest_low)
    if word == "ник":
        return await _set_text(update, me, "nick", "ник", rest, rest_low)
    if low in ("моя анкета", "анкета") or (word == "анкета" and update.effective_message.reply_to_message):
        return await _form(update)
    if low.startswith("мой город"):
        return await _city(update, me, orig[9:].strip())
    if low == "-мой город":
        db.execute("UPDATE users SET city='' WHERE user_id=?", (me.id,)); db.commit()
        await reply(update, "Город удалён из анкеты")
        return True
    if low.startswith("мой др"):
        return await _bday(update, me, orig[6:].strip())
    if low == "-мой др":
        db.execute("UPDATE users SET bday='' WHERE user_id=?", (me.id,)); db.commit()
        await reply(update, "День рождения удалён из анкеты")
        return True
    if word in ("погода", "!погода"):
        return await _weather(update, me, rest)
    if re.match(r"^[-−–—]\s?(реп|rep)\b\s*(@\w+)?$", low):
        return await _minus_rep(update, context, me, low)
    return False


async def _set_text(update, me, col, label, rest, rest_low):
    touch(me)
    if not rest:
        t = _who(update)
        r = urow(t.id)
        v = (r[col] if r else "") or ""
        await reply(update, f"{label.capitalize()} {link(t.id, disp(t))}: <b>{esc(v)}</b>" if v else
                            f"У {link(t.id, disp(t))} нет поля «{label}». Установить: «{label} Текст»")
        return True
    if rest_low in ("удалить", "сброс"):
        db.execute(f"UPDATE users SET {col}='' WHERE user_id=?", (me.id,)); db.commit()
        await reply(update, f"🗑 Поле «{label}» очищено")
        return True
    v = _clean(rest)
    if len(v) > TEXT_MAX:
        await reply(update, f"Слишком длинно: максимум {TEXT_MAX} символов")
        return True
    db.execute(f"UPDATE users SET {col}=? WHERE user_id=?", (v, me.id)); db.commit()
    await reply(update, f"✅ Поле «{label}» обновлено: <b>{esc(v)}</b>")
    return True


async def _form(update):
    t = _who(update)
    touch(t)
    r = urow(t.id)
    if not r:
        await reply(update, "Не нашёл такого участника")
        return True
    c = clan_of(t.id)
    lines = [f"📇 <b>Анкета</b> · {link(t.id, r['name'])}"]
    for lab, col in (("Звание", "ztitle"), ("Ник", "nick"), ("Город", "city")):
        if r[col]:
            lines.append(f"{lab}: {esc(r[col])}")
    if r["gender"]:
        lines.append("Пол: " + ("мужской" if r["gender"] == "м" else "женский"))
    if r["bday"]:
        lines.append(f"День рождения: {esc(r['bday'])}")
    if c:
        lines.append(f"Клан: «{esc(c['name'])}»")
    lines.append(f"Репутация: ✨ {r['rep']}")
    if len(lines) == 2:
        lines.append("Пока пусто. Заполнить: «звание …», «ник …», «мой город …», «мой др 15.03», «мойпол м/ж»")
    await reply(update, "\n".join(lines))
    return True


async def _city(update, me, v):
    touch(me)
    v = _clean(v)
    if not v or len(v) > 40:
        await reply(update, "Напиши: «мой город Москва»")
        return True
    db.execute("UPDATE users SET city=? WHERE user_id=?", (v, me.id)); db.commit()
    await reply(update, f"🏙 Город: <b>{esc(v)}</b>. Теперь «погода» покажет прогноз для него")
    return True


async def _bday(update, me, v):
    touch(me)
    m = BDAY_RE.match(v.strip())
    ok = False
    if m:
        d, mo = int(m.group(1)), int(m.group(2))
        try:
            datetime(2000, mo, d)
            ok = True
        except ValueError:
            pass
    if not ok:
        await reply(update, "Напиши: «мой др 15.03» или «мой др 15.03.2001»")
        return True
    val = f"{int(m.group(1)):02d}.{int(m.group(2)):02d}" + (f".{m.group(3)}" if m.group(3) else "")
    db.execute("UPDATE users SET bday=? WHERE user_id=?", (val, me.id)); db.commit()
    await reply(update, f"🎂 День рождения: <b>{val}</b>. Бот поздравит тебя в этот день")
    return True


async def _minus_rep(update, context, me, low):
    m = re.search(r"@(\w+)", low)
    tid = tname = None
    if m:
        r = find_by_username("@" + m.group(1))
        if r:
            tid, tname = r["user_id"], r["name"]
    else:
        t = target_user(update)
        if t:
            tid, tname = t.id, disp(t)
    if not tid:
        await reply(update, "Ответь на сообщение: «-реп» или «-реп @юз»")
        return True
    if tid == me.id:
        await reply(update, "Себе репутацию менять нельзя 😉")
        return True
    d = today()
    if db.execute("SELECT 1 FROM rep_log WHERE day=? AND giver=? AND target=?", (d, me.id, tid)).fetchone():
        await reply(update, "Этому участнику ты уже менял репутацию сегодня")
        return True
    if db.execute("SELECT COUNT(*) FROM rep_log WHERE day=? AND giver=?", (d, me.id)).fetchone()[0] >= 5:
        await reply(update, "Лимит: 5 репутаций в день")
        return True
    db.execute("INSERT INTO rep_log VALUES(?,?,?)", (d, me.id, tid))
    db.execute("UPDATE users SET rep=rep-1 WHERE user_id=?", (tid,))
    db.commit()
    await reply(update, f"💢 {link(me.id, disp(me))} понизил репутацию {link(tid, tname)} (теперь {urow(tid)['rep']})")
    return True


def _fetch_weather(city):
    def get(url):
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read().decode())
    g = get("https://geocoding-api.open-meteo.com/v1/search?count=1&language=ru&name=" + urllib.parse.quote(city))
    if not g.get("results"):
        return None
    p = g["results"][0]
    w = get("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s&timezone=auto&forecast_days=3"
            "&current_weather=true&daily=temperature_2m_max,temperature_2m_min,weathercode,precipitation_probability_max"
            % (p["latitude"], p["longitude"]))
    return p, w


async def _weather(update, me, city):
    touch(me)
    city = _clean(city) or (urow(me.id)["city"] or "")
    if not city:
        await reply(update, "Напиши: «погода Москва» или сохрани город: «мой город Москва»")
        return True
    try:
        data = await asyncio.to_thread(_fetch_weather, city)
    except Exception as e:
        log.warning("Погода: %s", e)
        await reply(update, "Сервис погоды сейчас недоступен, попробуй позже")
        return True
    if not data:
        await reply(update, f"Не нашёл город «{esc(city)}»")
        return True
    p, w = data
    cur = w["current_weather"]
    dl = w["daily"]
    lines = [f"🌍 <b>{esc(p['name'])}</b>{', ' + esc(p['country']) if p.get('country') else ''}",
             f"Сейчас: {cur['temperature']:+.0f}°, ветер {cur['windspeed']:.0f} км/ч · "
             f"{WEATHER_WORDS.get(cur['weathercode'], '')}"]
    names = ["Сегодня", "Завтра", "Послезавтра"]
    for i in range(min(3, len(dl["time"]))):
        lines.append(f"{names[i]}: {dl['temperature_2m_min'][i]:+.0f}…{dl['temperature_2m_max'][i]:+.0f}° · "
                     f"{WEATHER_WORDS.get(dl['weathercode'][i], '')} · осадки {dl['precipitation_probability_max'][i] or 0}%")
    await reply(update, "\n".join(lines))
    return True


async def bday_tick(bot):
    """Раз в день после 9:00 по времени бота: поздравить именинников и подарить славКоины."""
    n = now()
    d = today()
    if n.hour < 9 or state_get("ran_bday") == d:
        return
    state_set("ran_bday", d)
    key = n.strftime("%d.%m")
    rows = db.execute("SELECT user_id,name,bday FROM users WHERE bday LIKE ?", (key + "%",)).fetchall()
    for r in rows:
        age = ""
        if len(r["bday"]) == 10:
            age = f" Ему/ей исполняется {n.year - int(r['bday'][6:])}!"
        try:
            await bot.send_message(CHAT_ID, f"🎂🎉 Сегодня день рождения у {link(r['user_id'], r['name'])}!{age}\n"
                                            "Поздравляем! 🥳", parse_mode="HTML")
        except Exception:
            log.exception("bday")
