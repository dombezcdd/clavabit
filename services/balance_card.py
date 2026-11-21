# -*- coding: utf-8 -*-
"""Картинка баланса: пляж, сундук с золотом. Чем больше монет, тем больше золота."""

import io
import math
import random

from services.monopoly_board import _font

W, H = 800, 480


def _coin(d, x, y, r=13):
    d.ellipse((x - r, y - r * 0.6, x + r, y + r * 0.6 + 3), fill=(190, 140, 30))
    d.ellipse((x - r, y - r * 0.6 - 2, x + r, y + r * 0.6), fill=(250, 205, 70), outline=(255, 238, 150))
    d.ellipse((x - r * 0.5, y - r * 0.3 - 2, x + r * 0.5, y + r * 0.3), outline=(210, 160, 40))


def _level(coins):
    """сколько монет рисовать: от 0 до 90, логарифмически"""
    if coins <= 0:
        return 0
    return min(90, int(8 + 14 * math.log10(max(1, coins)) ** 1.6))


def balance_card(name, coins):
    from PIL import Image, ImageDraw
    rng = random.Random(coins * 7 + 3)
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    for y in range(H):                                  # небо
        t = y / 270
        if y < 270:
            d.line([(0, y), (W, y)], fill=(int(90 + 120 * t), int(170 + 60 * t), int(235 + 10 * t)))
    d.ellipse((600, 36, 700, 136), fill=(255, 236, 140))   # солнце
    d.ellipse((620, 56, 680, 116), fill=(255, 248, 190))
    d.rectangle((0, 235, W, 300), fill=(40, 140, 200))   # море
    for i in range(0, W, 46):
        d.arc((i, 244 + (i // 46 % 2) * 8, i + 40, 264 + (i // 46 % 2) * 8), 200, 340, fill=(190, 235, 255), width=3)
    d.polygon([(0, 300), (W, 288), (W, H), (0, H)], fill=(238, 214, 150))   # песок
    for _ in range(40):
        x, y = rng.randint(0, W), rng.randint(310, H)
        d.ellipse((x, y, x + 3, y + 2), fill=(215, 188, 120))
    # пальма
    d.line((90, 330, 120, 150), fill=(120, 80, 40), width=14)
    for a in (-150, -110, -70, -30, 10):
        ex, ey = 120 + 90 * math.cos(math.radians(a)), 150 + 60 * math.sin(math.radians(a)) + 20
        d.line((120, 150, ex, ey), fill=(40, 150, 70), width=9)
        d.line((120, 150, (120 + ex) / 2, (150 + ey) / 2 - 14, ex, ey), fill=(60, 180, 90), width=5)
    # сундук
    cx, cy = 470, 380
    d.ellipse((cx - 190, cy + 30, cx + 190, cy + 80), fill=(205, 180, 120))              # тень
    d.rectangle((cx - 150, cy - 30, cx + 150, cy + 60), fill=(125, 78, 36), outline=(70, 42, 18), width=4)
    for k in (-100, 0, 100):
        d.rectangle((cx + k - 8, cy - 30, cx + k + 8, cy + 60), fill=(190, 150, 60))
    d.rectangle((cx - 150, cy + 8, cx + 150, cy + 22), fill=(190, 150, 60))
    # золото в сундуке
    n = _level(coins)
    pile = min(n, 45)
    for i in range(pile):
        t = i / max(1, pile)
        x = cx + rng.randint(-int(130 * (1 - t * 0.4)), int(130 * (1 - t * 0.4)))
        y = cy - 34 - int(t * (20 + n * 0.9)) + rng.randint(-5, 5)
        _coin(d, x, y, 15)
    # крышка открыта (за кучей)
    d.polygon([(cx - 150, cy - 30), (cx + 150, cy - 30), (cx + 130, cy - 105), (cx - 130, cy - 105)], outline=(70, 42, 18),
              fill=(105, 64, 28), width=4)
    d.rectangle((cx - 150, cy - 40, cx + 150, cy - 28), fill=(190, 150, 60))
    for i in range(pile // 2):                                       # ещё монеты поверх
        t = i / max(1, pile // 2)
        _coin(d, cx + rng.randint(-120, 120), cy - 40 - int(t * (14 + n * 0.5)) + rng.randint(-4, 4), 15)
    # россыпь на песке
    for _ in range(max(0, n - 45)):
        _coin(d, rng.randint(250, 760), rng.randint(412, 462), 12)
    # плашка
    d.rounded_rectangle((24, 24, 430, 116), 18, fill=(20, 30, 50), outline=(245, 195, 70), width=3)
    nm = "".join(ch for ch in (name or "") if ord(ch) < 0x2E80 and ch.isprintable())[:18].strip() or "Игрок"
    d.text((44, 38), nm, font=_font(26, True), fill=(255, 255, 255))
    d.text((44, 74), f"{coins} славКоин", font=_font(32, True), fill=(250, 205, 70))
    buf = io.BytesIO()
    im.quantize(colors=96).save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
