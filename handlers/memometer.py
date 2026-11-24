# -*- coding: utf-8 -*-
"""Мем-метры для шутки: «попаметр», «писяметр», «мозгометр», «красотометр», «кринжометр», «лютометр», «ленометр».
Своё значение раз в час растёт или меняется, можно ответом на сообщение померить другого."""

import random
import re
import time

from config import HTML
from core.helpers import reply, target_user
from core.utils import disp, link, today, touch

RE = re.compile(r"^(попаметр|попа метр|писяметр|пися метр|мозгометр|красотометр|кринжометр|лютометр|ленометр|сигмаметр|меметр|метры)$")

# ключ: (иконка, название, единица, мин, макс, шкала (до чего заполняем полоску), реплики по четвертям)
M = {
    "попаметр": ("🍑", "Попаметр", "см", 70, 140, 140, ["Скромная, но своя", "Достойно", "Лавка подвинься!", "Центр гравитации района 🌍"]),
    "писяметр": ("📏", "Писяметр", "см", 3, 25, 25, ["Главное не размер", "Нормально, не переживай", "Респект", "Легенда чата 😎"]),
    "мозгометр": ("🧠", "Мозгометр", "IQ", 60, 160, 160, ["Мозг в отпуске", "Среднестатистический гений", "Умник!", "Эйнштейн нервно курит"]),
    "красотометр": ("✨", "Красотометр", "%", 20, 100, 100, ["Зато с характером", "Миленько", "Красавчик/красотка", "Обложка журнала 📸"]),
    "кринжометр": ("😬", "Кринжометр", "%", 0, 100, 100, ["Всё норм", "Лёгкий кринж", "Ой-ой-ой", "Максимальный кринж, закрой лицо 🙈"]),
    "лютометр": ("🔥", "Лютометр", "%", 0, 100, 100, ["Тихий зайка", "Бывает лютым", "Лютый!", "Хозяин чата 👑"]),
    "ленометр": ("🛋", "Ленометр", "%", 0, 100, 100, ["Трудоголик", "Иногда отдыхает", "Диван зовёт", "Прилип к дивану навсегда"]),
    "сигмаметр": ("🗿", "Сигмаметр", "%", 0, 100, 100, ["Бета-самец", "Почти сигма", "Сигма!", "Абсолютный сигма-босс 🗿"]),
}
ALIAS = {"попа метр": "попаметр", "пися метр": "писяметр"}


OBJ = {"попаметр": "к попе", "писяметр": "к писе", "мозгометр": "к уму", "красотометр": "к красоте", "кринжометр": "к кринжу",
       "лютометр": "к лютости", "ленометр": "к лени", "сигмаметр": "к сигме"}
GAIN = {"см": (1, 3, 300), "IQ": (-3, 4, 200), "%": (-5, 8, 100)}   # прирост за час: мин, макс; потолок
HOUR = 3600
_ready = [False]


def _tbl():
    from database.db import db
    if not _ready[0]:
        db.execute("CREATE TABLE IF NOT EXISTS meters(user_id INTEGER, kind TEXT, value INTEGER, ts REAL, PRIMARY KEY(user_id, kind))")
        db.commit()
        _ready[0] = True
    return db


def _get(uid, kind):
    return _tbl().execute("SELECT * FROM meters WHERE user_id=? AND kind=?", (uid, kind)).fetchone()


def _start(uid, kind):
    mn, mx = M[kind][3], M[kind][4]
    return random.Random(f"{uid}:{kind}").randint(mn, mx)


def _line(uid, name, kind, note=""):
    ic, title, unit, mn, mx, scale, phr = M[kind]
    r = _get(uid, kind)
    v = r["value"] if r else _start(uid, kind)
    top = GAIN[unit][2]
    frac = max(0.0, min(1.0, (v - mn) / max(1, min(top, mx * 1.5) - mn)))
    bar = "█" * round(frac * 10) + "░" * (10 - round(frac * 10))
    return (f"{ic} <b>{title}</b> · {link(uid, name)}\n"
            f"<code>{bar}</code> <b>{v} {unit}</b>{note}\n<i>{phr[min(3, int(frac * 4))]}</i>")


def _grow(uid, kind):
    """-> (изменение, секунд до следующего замера); раз в час своё значение меняется"""
    db = _tbl()
    r = _get(uid, kind)
    now_ = time.time()
    if r and now_ - r["ts"] < HOUR:
        return None, int(HOUR - (now_ - r["ts"]))
    unit = M[kind][2]
    lo, hi, top = GAIN[unit]
    cur = r["value"] if r else _start(uid, kind)
    d = random.randint(lo, hi)
    if unit == "см" and random.random() < 0.08:
        d = -random.randint(1, 2)                                  # редкое «усыхание» для смеха
    new = max(M[kind][3] if unit != "см" else 1, min(top, cur + d))
    db.execute("INSERT INTO meters(user_id,kind,value,ts) VALUES(?,?,?,?) ON CONFLICT(user_id,kind) DO UPDATE SET value=?, ts=?",
               (uid, kind, new, now_, new, now_))
    db.commit()
    return new - cur, 0


async def handle_meter_text(update, context, low, text):
    low = low.strip()
    if not RE.match(low):
        return False
    low = ALIAS.get(low, low)
    me = update.effective_user
    if not me:
        return False
    touch(me)
    if low in ("меметр", "метры"):
        await reply(update, "📏 <b>Мем-метры</b> (шутка: раз в час значение меняется):\n" +
                    " · ".join(f"<code>{k}</code>" for k in M) + "\nОтветом на сообщение можно померить другого.")
        return True
    t = target_user(update)
    if t and t.id != me.id:                                         # чужое значение только смотрим
        await reply(update, _line(t.id, disp(t), low))
        return True
    d, left = _grow(me.id, low)
    unit = M[low][2]
    if d is None:
        await reply(update, _line(me.id, disp(me), low, f"\n⏳ Кд 1 час, следующий замер через {left // 60 + 1} мин."))
        return True
    head = (f"<b>{'+' if d > 0 else ''}{d} {unit} {OBJ[low]}!</b>" if d else "<b>Без изменений 😐</b>")
    await reply(update, head + "\n" + _line(me.id, disp(me), low))
    return True
