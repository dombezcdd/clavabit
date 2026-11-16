# -*- coding: utf-8 -*-
"""Картинки для мафии: карточки ролей, ночь/день, конец игры (Pillow)."""

import math

from services.charts import _png
from services.mafia import ROLES
from services.monopoly_board import _font

THEME = {"mafia": ((60, 14, 20), (230, 70, 70)), "solo": ((30, 10, 40), (190, 90, 255)),
         "town": ((14, 36, 58), (90, 190, 255))}
TXT = (240, 243, 248)


def _wrap(d, text, font, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + [cur]


def _star(d, cx, cy, r, fill, pts=5):
    xy = []
    for i in range(pts * 2):
        a = -math.pi / 2 + i * math.pi / pts
        rr = r if i % 2 == 0 else r * 0.45
        xy.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    d.polygon(xy, fill=fill)


def _symbol(d, role, cx, cy):
    W, K = (245, 245, 245), (20, 20, 24)
    if role in ("mafia", "don"):
        d.ellipse([cx - 120, cy + 10, cx + 120, cy + 60], fill=K)
        d.rounded_rectangle([cx - 70, cy - 90, cx + 70, cy + 30], 24, fill=K)
        d.rectangle([cx - 70, cy - 10, cx + 70, cy + 20], fill=(200, 40, 40))
        if role == "don":
            _star(d, cx, cy - 45, 22, (255, 210, 60))
        d.ellipse([cx - 70, cy + 80, cx - 10, cy + 110], fill=K)
        d.ellipse([cx + 10, cy + 80, cx + 70, cy + 110], fill=K)
    elif role == "jason":
        d.rounded_rectangle([cx - 85, cy - 120, cx + 85, cy + 120], 70, fill=(235, 232, 220))
        for dx in (-45, 45):
            d.ellipse([cx + dx - 22, cy - 55, cx + dx + 22, cy - 15], fill=K)
        for k in range(3):
            d.line([(cx + 20, cy + 20 + k * 22), (cx + 70, cy + 5 + k * 22)], fill=(200, 30, 30), width=8)
        for dx, dy in ((-30, 60), (0, 75), (30, 60), (-15, 95), (15, 95)):
            d.ellipse([cx + dx - 7, cy + dy - 7, cx + dx + 7, cy + dy + 7], fill=K)
        d.polygon([(cx - 4, cy - 10), (cx + 4, cy - 10), (cx + 2, cy + 30), (cx - 2, cy + 30)], fill=(180, 175, 160))
    elif role == "freddy":
        d.ellipse([cx - 80, cy - 70, cx + 80, cy + 90], fill=(205, 150, 120))
        d.ellipse([cx - 110, cy - 50, cx + 110, cy - 20], fill=(90, 60, 40))
        d.rounded_rectangle([cx - 65, cy - 120, cx + 65, cy - 30], 18, fill=(90, 60, 40))
        d.rectangle([cx - 65, cy - 55, cx + 65, cy - 35], fill=(160, 30, 30))
        for dx in (-30, 30):
            d.ellipse([cx + dx - 14, cy - 5, cx + dx + 14, cy + 20], fill=K)
        for k in range(4):
            d.line([(cx + 60 + k * 14, cy + 110), (cx + 75 + k * 14, cy + 40)], fill=(200, 200, 210), width=7)
    elif role == "comm":
        _star(d, cx, cy, 120, (255, 205, 60), 6)
        d.ellipse([cx - 40, cy - 40, cx + 40, cy + 40], fill=(40, 70, 120))
        d.ellipse([cx - 18, cy - 18, cx + 18, cy + 18], fill=(255, 205, 60))
    elif role == "doc":
        d.ellipse([cx - 110, cy - 110, cx + 110, cy + 110], fill=W)
        d.rectangle([cx - 28, cy - 80, cx + 28, cy + 80], fill=(220, 50, 50))
        d.rectangle([cx - 80, cy - 28, cx + 80, cy + 28], fill=(220, 50, 50))
    elif role == "beauty":
        d.ellipse([cx - 110, cy - 50, cx, cy + 50], fill=(220, 40, 90))
        d.ellipse([cx, cy - 50, cx + 110, cy + 50], fill=(220, 40, 90))
        d.ellipse([cx - 90, cy - 5, cx + 90, cy + 70], fill=(190, 25, 75))
        d.line([(cx - 80, cy + 8), (cx + 80, cy + 8)], fill=(110, 10, 40), width=6)
    elif role == "witch":
        d.polygon([(cx, cy - 130), (cx - 90, cy + 60), (cx + 90, cy + 60)], fill=(110, 50, 170))
        d.ellipse([cx - 130, cy + 40, cx + 130, cy + 90], fill=(70, 30, 120))
        d.rectangle([cx - 60, cy + 20, cx + 60, cy + 45], fill=(40, 20, 70))
        d.rectangle([cx - 14, cy + 17, cx + 14, cy + 48], fill=(255, 210, 60))
    elif role == "hunter":
        d.ellipse([cx - 110, cy - 110, cx + 110, cy + 110], outline=(240, 90, 60), width=9)
        d.ellipse([cx - 55, cy - 55, cx + 55, cy + 55], outline=(240, 90, 60), width=6)
        d.line([(cx - 140, cy), (cx + 140, cy)], fill=(240, 90, 60), width=6)
        d.line([(cx, cy - 140), (cx, cy + 140)], fill=(240, 90, 60), width=6)
    else:
        d.polygon([(cx, cy - 120), (cx - 120, cy), (cx + 120, cy)], fill=(200, 80, 60))
        d.rectangle([cx - 90, cy, cx + 90, cy + 110], fill=(240, 220, 170))
        d.rectangle([cx - 22, cy + 40, cx + 22, cy + 110], fill=(110, 70, 40))
        d.rectangle([cx + 40, cy + 20, cx + 75, cy + 55], fill=(110, 170, 230))


def role_card(role):
    from PIL import Image, ImageDraw
    bg, accent = THEME[ROLES[role][2]]
    name, _emoji, team, desc = ROLES[role]
    img = Image.new("RGB", (900, 480), bg)
    d = ImageDraw.Draw(img)
    for i in range(0, 900, 36):
        d.line([(i, 0), (i - 240, 480)], fill=tuple(min(255, c + 8) for c in bg), width=2)
    d.rounded_rectangle([30, 30, 330, 450], 28, fill=tuple(min(255, c + 16) for c in bg), outline=accent, width=4)
    _symbol(d, role, 180, 240)
    d.text((370, 40), "ТВОЯ РОЛЬ", font=_font(24), fill=accent)
    d.text((370, 78), name, font=_font(52, True), fill=TXT)
    tm = {"mafia": "Команда мафии", "solo": "Одиночка", "town": "Город"}[team]
    d.text((370, 152), tm, font=_font(28, True), fill=accent)
    y = 210
    for line in _wrap(d, desc, _font(26), 480):
        d.text((370, y), line, font=_font(26), fill=TXT)
        y += 38
    return _png(img)


def phase_card(kind, n):
    from PIL import Image, ImageDraw
    night = kind == "night"
    img = Image.new("RGB", (900, 420), (10, 14, 40) if night else (255, 170, 90))
    d = ImageDraw.Draw(img)
    if night:
        for k in range(40):
            x, y = (k * 211) % 900, (k * 97) % 300
            d.ellipse([x, y, x + 4, y + 4], fill=(230, 230, 255))
        d.ellipse([560, 50, 760, 250], fill=(245, 240, 200))
        d.ellipse([610, 30, 790, 210], fill=(10, 14, 40))
        d.polygon([(0, 420), (0, 330), (120, 290), (260, 340), (420, 280), (600, 350), (900, 300), (900, 420)], fill=(5, 8, 24))
        txt, col = f"НОЧЬ {n}", (200, 210, 255)
    else:
        d.ellipse([560, 70, 760, 270], fill=(255, 235, 120))
        for k in range(12):
            a = k * math.pi / 6
            d.line([(660 + math.cos(a) * 110, 170 + math.sin(a) * 110), (660 + math.cos(a) * 150, 170 + math.sin(a) * 150)],
                   fill=(255, 235, 120), width=8)
        d.polygon([(0, 420), (0, 340), (150, 300), (300, 350), (500, 310), (900, 360), (900, 420)], fill=(90, 50, 40))
        txt, col = f"ДЕНЬ {n}", (90, 30, 20)
    d.text((50, 60), txt, font=_font(80, True), fill=col)
    d.text((50, 170), "Город засыпает…" if night else "Город просыпается", font=_font(34), fill=col)
    return _png(img)


def end_card(side):
    from PIL import Image, ImageDraw
    bg, accent = THEME["mafia" if side == "mafia" else "solo" if side == "solo" else "town"]
    img = Image.new("RGB", (900, 420), bg)
    d = ImageDraw.Draw(img)
    _star(d, 700, 210, 150, accent, 5)
    title = {"mafia": "ПОБЕДА МАФИИ", "town": "ПОБЕДА ГОРОДА", "solo": "ПОБЕДА УБИЙЦЫ"}[side]
    d.text((40, 120), title, font=_font(62, True), fill=TXT)
    d.text((40, 220), {"mafia": "Ночь принадлежит им", "town": "Преступность разгромлена",
                       "solo": "Остался только один"}[side], font=_font(34), fill=accent)
    return _png(img)
