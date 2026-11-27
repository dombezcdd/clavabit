# -*- coding: utf-8 -*-
"""Бои питомцев: характеристики, симуляция боя и красивые картинки (мордочки рисуем сами, без эмодзи-шрифта)."""

import io
import random
import time

from PIL import Image, ImageDraw

from database.db import db
from services.monopoly_board import _font

# характеристики: hp, атака, скорость, способность
KIND = {
    "кот": (90, 14, 14, "crit"), "собака": (120, 15, 9, "tank"), "хомяк": (70, 10, 12, "dodge"),
    "попугай": (80, 13, 13, "stun"), "кролик": (85, 11, 16, "double"), "лиса": (100, 16, 12, "crit2"),
}
ABIL = {"crit": "Крит-коготь", "tank": "Толстая шкура", "dodge": "Ловкач", "stun": "Оглушающий крик", "double": "Двойной удар", "crit2": "Хитрый укус"}
COL = {"кот": (232, 150, 70), "собака": (176, 124, 84), "хомяк": (238, 205, 160), "попугай": (70, 195, 120),
       "кролик": (240, 240, 246), "лиса": (236, 118, 42)}
DAILY_LIMIT = 6


def ensure():
    db.execute("CREATE TABLE IF NOT EXISTS pet_fights(user_id INTEGER PRIMARY KEY, wins INTEGER DEFAULT 0, losses INTEGER DEFAULT 0, day TEXT, today INTEGER DEFAULT 0)")
    db.commit()


def record(uid, win, day):
    ensure()
    r = db.execute("SELECT * FROM pet_fights WHERE user_id=?", (uid,)).fetchone()
    if not r:
        db.execute("INSERT INTO pet_fights(user_id,wins,losses,day,today) VALUES(?,?,?,?,0)", (uid, 0, 0, day))
        r = db.execute("SELECT * FROM pet_fights WHERE user_id=?", (uid,)).fetchone()
    today_n = (r["today"] if r["day"] == day else 0) + 1
    db.execute("UPDATE pet_fights SET wins=wins+?, losses=losses+?, day=?, today=? WHERE user_id=?",
               (1 if win else 0, 0 if win else 1, day, today_n, uid))
    db.commit()


def fights_today(uid, day):
    ensure()
    r = db.execute("SELECT * FROM pet_fights WHERE user_id=?", (uid,)).fetchone()
    return r["today"] if r and r["day"] == day else 0


def record_of(uid):
    ensure()
    r = db.execute("SELECT * FROM pet_fights WHERE user_id=?", (uid,)).fetchone()
    return (r["wins"], r["losses"]) if r else (0, 0)


def fighter(pet, day):
    """Питомец из БД -> боец. Уровень растёт с возрастом, голодный слабее."""
    hp, atk, spd, ab = KIND[pet["kind"]]
    days = int((time.time() - (pet["bought"] or time.time())) // 86400)
    lvl = min(8, 1 + days // 2)
    m = 1 + 0.06 * (lvl - 1)
    hungry = (pet["fed_day"] or "") < day and days >= 2 and (pet["fed_day"] or "") != day
    if hungry:
        m *= 0.85
    return dict(kind=pet["kind"], name=pet["name"] or pet["kind"].capitalize(), owner=pet["owner"], lvl=lvl,
                hp=int(hp * m), maxhp=int(hp * m), atk=atk * m, spd=spd, ab=ab, hungry=hungry, stun=False)


def best_pet(pets, day):
    fs = [fighter(p, day) for p in pets if p["kind"] in KIND]
    return max(fs, key=lambda f: f["maxhp"] + f["atk"] * 4) if fs else None


def simulate(a, b):
    """-> (кадры, победитель 'a'/'b'). Кадр: (hp_a, hp_b, события раунда, кто получил урон/что-то)"""
    frames = [(a["hp"], b["hp"], ["Бой начинается!"], None)]
    for rnd in range(1, 16):
        ev, hit = [], None
        order = sorted((("a", a), ("b", b)), key=lambda x: x[1]["spd"] + random.random() * 6, reverse=True)
        for side, att in order:
            dfn = b if att is a else a
            if att["hp"] <= 0 or dfn["hp"] <= 0:
                continue
            if att["stun"]:
                att["stun"] = False
                ev.append(f"{att['name']} оглушён и пропускает ход")
                continue
            if dfn["ab"] == "dodge" and random.random() < 0.25:
                ev.append(f"{dfn['name']} ловко уворачивается!")
                continue
            hits = 2 if att["ab"] == "double" and random.random() < 0.2 else 1
            for _ in range(hits):
                dmg = att["atk"] * random.uniform(0.8, 1.2)
                tag = "бьёт"
                if att["ab"] in ("crit", "crit2") and random.random() < (0.22 if att["ab"] == "crit" else 0.16):
                    dmg *= 1.8
                    tag = "КРИТ!"
                if dfn["ab"] == "tank":
                    dmg *= 0.85
                dmg = max(1, int(dmg))
                dfn["hp"] = max(0, dfn["hp"] - dmg)
                ev.append(f"{att['name']} {tag} -{dmg}")
                hit = "b" if dfn is b else "a"
            if att["ab"] == "stun" and random.random() < 0.15 and dfn["hp"] > 0:
                dfn["stun"] = True
                ev.append(f"{att['name']}: оглушающий крик!")
        frames.append((a["hp"], b["hp"], ev, hit))
        if a["hp"] <= 0 or b["hp"] <= 0:
            break
    wa, wb = a["hp"] / a["maxhp"], b["hp"] / b["maxhp"]
    return frames, ("a" if wa >= wb else "b")


# ---------- рисование ----------
W, H = 900, 520


def _grad(img, c1, c2):
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line((0, y, W, y), fill=tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)))


def draw_pet(d, kind, cx, cy, s, flip=False, dead=False, hurt=False):
    """Мультяшная мордочка. s — радиус головы."""
    body = COL[kind]
    dark = tuple(int(c * 0.72) for c in body)
    light = (255, 236, 220)
    k = -1 if flip else 1
    # ушки
    if kind == "кролик":
        for sx in (-1, 1):
            d.ellipse((cx + sx * s * 0.45 - s * 0.2, cy - s * 1.95, cx + sx * s * 0.45 + s * 0.2, cy - s * 0.5), fill=body, outline=dark, width=3)
            d.ellipse((cx + sx * s * 0.45 - s * 0.1, cy - s * 1.7, cx + sx * s * 0.45 + s * 0.1, cy - s * 0.7), fill=(250, 170, 190))
    elif kind in ("кот", "лиса"):
        for sx in (-1, 1):
            d.polygon([(cx + sx * s * 0.95, cy - s * 0.3), (cx + sx * s * 0.75, cy - s * 1.45), (cx + sx * s * 0.2, cy - s * 0.85)], fill=body, outline=dark)
            d.polygon([(cx + sx * s * 0.8, cy - s * 0.55), (cx + sx * s * 0.72, cy - s * 1.15), (cx + sx * s * 0.4, cy - s * 0.8)], fill=(250, 170, 190) if kind == "кот" else (60, 40, 40))
    elif kind == "собака":
        for sx in (-1, 1):
            d.ellipse((cx + sx * s * 0.95 - s * 0.3, cy - s * 0.7, cx + sx * s * 0.95 + s * 0.3, cy + s * 0.55), fill=dark, outline=(70, 45, 30), width=3)
    elif kind == "хомяк":
        for sx in (-1, 1):
            d.ellipse((cx + sx * s * 0.7 - s * 0.22, cy - s * 1.05, cx + sx * s * 0.7 + s * 0.22, cy - s * 0.55), fill=body, outline=dark, width=3)
    elif kind == "попугай":
        for i, c in enumerate(((240, 70, 80), (250, 200, 60), (70, 140, 240))):
            d.polygon([(cx - s * 0.15 + i * s * 0.18, cy - s * 0.95), (cx - s * 0.05 + i * s * 0.18, cy - s * 1.55 - i * 6), (cx + s * 0.12 + i * s * 0.18, cy - s * 0.95)], fill=c)
    # голова
    d.ellipse((cx - s, cy - s * 0.9, cx + s, cy + s * 0.95), fill=body, outline=dark, width=4)
    if kind in ("лиса", "кролик", "хомяк"):
        d.ellipse((cx - s * 0.7, cy + s * 0.05, cx + s * 0.7, cy + s * 0.9), fill=light)
    if kind == "хомяк":
        for sx in (-1, 1):
            d.ellipse((cx + sx * s * 0.75 - s * 0.25, cy + s * 0.1, cx + sx * s * 0.75 + s * 0.25, cy + s * 0.6), fill=(250, 190, 170))
    if kind == "собака":
        d.ellipse((cx - s * 0.5, cy + s * 0.05, cx + s * 0.5, cy + s * 0.85), fill=(236, 214, 188))
    # глаза
    for sx in (-1, 1):
        ex, ey = cx + sx * s * 0.42, cy - s * 0.18
        if dead:
            d.line((ex - 9, ey - 9, ex + 9, ey + 9), fill=(30, 20, 30), width=4); d.line((ex + 9, ey - 9, ex - 9, ey + 9), fill=(30, 20, 30), width=4)
        elif hurt:
            d.arc((ex - 11, ey - 8, ex + 11, ey + 12), 200, 340, fill=(30, 20, 30), width=4)
        else:
            d.ellipse((ex - 12, ey - 14, ex + 12, ey + 14), fill=(255, 255, 255), outline=(30, 20, 30), width=2)
            d.ellipse((ex - 6 + k * 3, ey - 7, ex + 6 + k * 3, ey + 9), fill=(25, 20, 30))
            d.ellipse((ex - 3 + k * 3, ey - 5, ex + 1 + k * 3, ey - 1), fill=(255, 255, 255))
    # нос / клюв / рот
    if kind == "попугай":
        d.polygon([(cx - s * 0.2, cy + s * 0.05), (cx + s * 0.2, cy + s * 0.05), (cx, cy + s * 0.5)], fill=(250, 170, 50), outline=(160, 100, 20))
    else:
        d.ellipse((cx - 11, cy + s * 0.1, cx + 11, cy + s * 0.1 + 14), fill=(60, 35, 40))
        d.arc((cx - 22, cy + s * 0.18, cx, cy + s * 0.5), 20, 160, fill=(60, 35, 40), width=3)
        d.arc((cx, cy + s * 0.18, cx + 22, cy + s * 0.5), 20, 160, fill=(60, 35, 40), width=3)
    if kind in ("кот", "лиса"):
        for sx in (-1, 1):
            for dy in (-6, 6):
                d.line((cx + sx * s * 0.55, cy + s * 0.25 + dy, cx + sx * s * 1.25, cy + s * 0.18 + dy * 1.6), fill=(250, 250, 250), width=2)


def _bar(d, x, y, w, frac, col):
    d.rounded_rectangle((x, y, x + w, y + 22), 8, fill=(28, 30, 50), outline=(80, 86, 120), width=2)
    f = max(0.0, min(1.0, frac))
    if f > 0:
        c = col if f > 0.35 else (235, 70, 80)
        d.rounded_rectangle((x + 3, y + 3, x + 3 + int((w - 6) * f), y + 19), 6, fill=c)


def _crown(d, cx, cy, s):
    d.polygon([(cx - s, cy), (cx - s, cy - s * 0.9), (cx - s * 0.5, cy - s * 0.4), (cx, cy - s * 1.1), (cx + s * 0.5, cy - s * 0.4), (cx + s, cy - s * 0.9), (cx + s, cy)], fill=(250, 205, 70), outline=(170, 120, 20))


def battle_card(a, b, hp_a, hp_b, names, events, hit=None, winner=None, title="БОЙ ПИТОМЦЕВ", bet=0):
    """names = (владелец A, владелец B). hit: 'a'/'b' — кто получил урон в этом кадре."""
    img = Image.new("RGB", (W, H))
    _grad(img, (30, 24, 60), (12, 12, 26))
    d = ImageDraw.Draw(img, "RGBA")
    d.ellipse((-200, 340, W + 200, H + 300), fill=(52, 46, 90, 255))                       # арена
    d.ellipse((120, 372, 340, 410), fill=(0, 0, 0, 90)); d.ellipse((560, 372, 780, 410), fill=(0, 0, 0, 90))
    d.text((W // 2, 26), title, font=_font(30, True), fill=(250, 205, 90), anchor="mm")
    if bet:
        d.text((W // 2, 56), f"ставка {bet}", font=_font(18), fill=(190, 195, 225), anchor="mm")
    for side, f, hp, x in (("a", a, hp_a, 230), ("b", b, hp_b, 670)):
        dead = hp <= 0
        lose = winner and winner != side
        cy = 292 + (16 if dead else 0)
        draw_pet(d, f["kind"], x + (-26 if hit == side else 0) * (1 if side == "a" else -1) * 0, cy, 72, flip=(side == "b"), dead=dead or bool(lose), hurt=(hit == side and not dead))
        if winner == side:
            _crown(d, x, cy - 56, 26)
        _bar(d, x - 150, 74, 300, hp / f["maxhp"], (80, 205, 130))
        d.text((x, 118), f"{f['name']}", font=_font(24, True), fill=(255, 255, 255), anchor="mm")
        d.text((x, 144), f"{f['kind']} · ур. {f['lvl']} · {max(0, hp)}/{f['maxhp']}" + (" · голодный" if f["hungry"] else ""), font=_font(15), fill=(190, 195, 225), anchor="mm")
        d.text((x, 392), names[0 if side == "a" else 1], font=_font(18), fill=(235, 238, 255), anchor="mm")
        d.text((x, 416), ABIL[f["ab"]], font=_font(14), fill=(160, 168, 205), anchor="mm")
    d.text((W // 2, 292), "VS", font=_font(46, True), fill=(250, 90, 100), anchor="mm")
    d.rounded_rectangle((60, 438, W - 60, 500), 14, fill=(14, 15, 30, 235), outline=(90, 96, 140), width=2)
    lines = events[-2:] if events else [""]
    for i, t in enumerate(lines):
        d.text((W // 2, 456 + i * 28), t, font=_font(19, i == len(lines) - 1), fill=(255, 235, 170) if i == len(lines) - 1 else (190, 195, 225), anchor="mm")
    bio = io.BytesIO(); img.save(bio, "JPEG", quality=88); bio.seek(0)
    return bio
