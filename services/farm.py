# -*- coding: utf-8 -*-
"""Рыбалка и огород: заняться и вернуться позже. Награды нарочно маленькие."""

import io
import random
import time

from database.db import db
from database.state import state_get, state_set

db.executescript("""
CREATE TABLE IF NOT EXISTS outdoor(
  user_id INTEGER, slot TEXT, item TEXT, ready REAL, PRIMARY KEY(user_id, slot));
""")
db.commit()

FISH_MIN = (30, 60)               # минут до улова
FISH_DAY = 3                       # забросов в сутки
FISH_TABLE = (                     # (вес, название, монеты)
    (30, "ничего, одна тина", 0),
    (30, "плотву", 1),
    (20, "окуня", 2),
    (12, "щуку", 3),
    (6, "карпа-великана", 5),
    (2, "ЗОЛОТУЮ РЫБКУ", 10),
)
PLOTS = 2
CROPS = {                         # ключ: (название, цена семян, часы, монеты за урожай, опыт)
    "морковь": ("🥕 Морковь", 2, 3, 3, 5),
    "тыква": ("🎃 Тыква", 4, 8, 7, 10),
    "клубника": ("🍓 Клубника", 6, 12, 11, 15),
}


def _slot(uid, slot):
    return db.execute("SELECT * FROM outdoor WHERE user_id=? AND slot=?", (uid, slot)).fetchone()


# ---------- рыбалка ----------
def fish_cast(uid, day):
    """-> (ok, текст)"""
    cur = _slot(uid, "fish")
    if cur:
        left = cur["ready"] - time.time()
        return False, (f"Удочка уже закинута, поплавок дёргается через {int(left // 60) + 1} мин. Забрать: «улов»" if left > 0
                       else "Клюнуло! Забери улов: «улов»")
    key = f"fishcnt_{day}_{uid}"
    n = int(state_get(key) or 0)
    if n >= FISH_DAY:
        return False, f"Сегодня уже {FISH_DAY} заброса, рыба спит. Приходи завтра 🌙"
    state_set(key, n + 1)
    mins = random.randint(*FISH_MIN)
    db.execute("INSERT OR REPLACE INTO outdoor VALUES(?,?,?,?)", (uid, "fish", "", time.time() + mins * 60))
    db.commit()
    return True, f"🎣 Удочка закинута! Улов через {mins} мин. Забрать: «улов» (заброс {n + 1} из {FISH_DAY})"


def fish_take(uid):
    """-> (ok, текст, монеты, редкая)"""
    cur = _slot(uid, "fish")
    if not cur:
        return False, "Удочка не закинута. Попробуй «рыбалка»", 0, False
    left = cur["ready"] - time.time()
    if left > 0:
        return False, f"Рано, поплавок спокоен. Ещё {int(left // 60) + 1} мин.", 0, False
    db.execute("DELETE FROM outdoor WHERE user_id=? AND slot='fish'", (uid,))
    db.commit()
    _, name, coins = random.choices(FISH_TABLE, weights=[x[0] for x in FISH_TABLE])[0]
    return True, name, coins, coins >= 10


# ---------- огород ----------
def plot_state(uid):
    rows = {r["slot"]: r for r in db.execute("SELECT * FROM outdoor WHERE user_id=? AND slot LIKE 'plot%'", (uid,))}
    out = []
    for i in range(1, PLOTS + 1):
        r = rows.get(f"plot{i}")
        if not r:
            out.append(None)
        else:
            out.append((r["item"], r["ready"]))
    return out


def plant(uid, i, crop):
    from services.economy import coins_of, give_coins
    if crop not in CROPS or not (1 <= i <= PLOTS):
        return False, "Нет такой культуры или грядки"
    if _slot(uid, f"plot{i}"):
        return False, "Грядка занята"
    name, cost, hours, _, _ = CROPS[crop]
    if coins_of(uid) < cost:
        return False, f"Семена стоят {cost} славКоин, не хватает"
    give_coins(uid, -cost, commit=False)
    db.execute("INSERT OR REPLACE INTO outdoor VALUES(?,?,?,?)", (uid, f"plot{i}", crop, time.time() + hours * 3600))
    db.commit()
    return True, f"{name} посажена на грядке {i}, созреет через {hours} ч."


def harvest(uid):
    """Собирает всё созревшее -> (список строк, монеты, опыт)"""
    from services.economy import give_coins
    lines, coins, xp = [], 0, 0
    for i, st in enumerate(plot_state(uid), 1):
        if st and st[1] <= time.time():
            name, _, _, reward, x = CROPS[st[0]]
            coins += reward
            xp += x
            lines.append(f"{name}: +{reward}")
            db.execute("DELETE FROM outdoor WHERE user_id=? AND slot=?", (uid, f"plot{i}"))
    if coins:
        give_coins(uid, coins, commit=False)
    db.commit()
    return lines, coins, xp


def garden_card(name, uid):
    from PIL import Image, ImageDraw
    from services.monopoly_board import _font
    W, H = 760, 400
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(120 + 70 * t * 0), int(200 - 20 * t), int(240 - 90 * t)) if y < 150 else (96, 158, 70))
    d.ellipse((620, 20, 700, 100), fill=(255, 236, 140))
    d.rectangle((0, 150, W, H), fill=(104, 168, 76))
    for i, st in enumerate(plot_state(uid)):
        x0 = 60 + i * 340
        d.rounded_rectangle((x0, 190, x0 + 300, 340), 18, fill=(112, 76, 44), outline=(70, 46, 24), width=4)
        for k in range(0, 300, 30):
            d.line((x0 + k + 15, 200, x0 + k + 15, 330), fill=(92, 60, 34), width=3)
        cx, cy = x0 + 150, 290
        if not st:
            d.text((cx, 265), "пусто", font=_font(22, True), fill=(200, 170, 130), anchor="mm")
        else:
            crop, ready = st
            total = CROPS[crop][2] * 3600
            p = 1.0 if ready <= time.time() else max(0.0, 1 - (ready - time.time()) / total)
            h = int(20 + 70 * p)
            d.line((cx, cy, cx, cy - h), fill=(60, 140, 50), width=6)
            for s in (-1, 1):
                d.ellipse((cx + (8 if s > 0 else -34), cy - h * 0.6, cx + (34 if s > 0 else -8), cy - h * 0.6 + 16), fill=(70, 170, 60))
            if p >= 1.0:
                col = {"морковь": (240, 130, 30), "тыква": (240, 150, 20), "клубника": (220, 40, 60)}[crop]
                d.ellipse((cx - 24, cy - h - 8, cx + 24, cy - h + 36), fill=col)
                d.text((cx, 360), "ГОТОВО!", font=_font(20, True), fill=(255, 255, 255), anchor="mm", stroke_width=2, stroke_fill=(40, 80, 20))
            else:
                d.ellipse((cx - 9, cy - h - 8, cx + 9, cy - h + 10), fill=(120, 200, 90))
                left = int((ready - time.time()) // 60)
                d.text((cx, 360), f"ещё {left // 60} ч {left % 60} мин", font=_font(18, True), fill=(255, 255, 255), anchor="mm", stroke_width=2, stroke_fill=(40, 80, 20))
        d.text((x0 + 150, 172), f"Грядка {i + 1}", font=_font(18, True), fill=(255, 255, 255), anchor="mm", stroke_width=2, stroke_fill=(40, 80, 20))
    nm = "".join(ch for ch in (name or "") if ord(ch) < 0x2E80 and ch.isprintable())[:18].strip() or "Игрок"
    d.rounded_rectangle((20, 20, 330, 80), 14, fill=(30, 50, 30), outline=(240, 220, 120), width=2)
    d.text((36, 30), f"Огород: {nm}", font=_font(22, True), fill=(255, 255, 255))
    buf = io.BytesIO()
    im.quantize(colors=64).save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
