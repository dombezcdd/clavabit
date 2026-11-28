# -*- coding: utf-8 -*-
"""Красивая обложка «Сотрудничество»: градиент, узоры и крупная надпись."""

import io
import math

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from services.monopoly_board import _font

W, H = 1280, 720


def coop_card():
    import os
    import random
    rnd = random.Random(7)
    img = Image.new("RGB", (W, H), (8, 6, 22))
    # северное сияние: крупные размытые пятна
    glow = Image.new("RGB", (W, H), (8, 6, 22))
    gd = ImageDraw.Draw(glow)
    for (x, y, rx, ry, col) in ((260, 120, 420, 200, (110, 60, 255)), (980, 160, 380, 190, (255, 60, 150)),
                                (640, 640, 620, 170, (30, 170, 255)), (1180, 620, 300, 200, (160, 60, 255)),
                                (80, 600, 300, 180, (255, 90, 120))):
        gd.ellipse((x - rx, y - ry, x + rx, y + ry), fill=col)
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    img = Image.blend(img, glow, 0.85)
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for _ in range(170):                     # звёздная пыль
        x, y, r = rnd.randrange(W), rnd.randrange(H), rnd.choice((1, 1, 2, 2, 3))
        od.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, rnd.randrange(60, 220)))
    for _ in range(14):                      # боке
        x, y, r = rnd.randrange(W), rnd.randrange(H), rnd.randrange(18, 60)
        od.ellipse((x - r, y - r, x + r, y + r), outline=(255, 255, 255, 60), width=2)
    for k in range(7):                       # тонкие дуги-узоры
        r = 300 + k * 46
        od.arc((W // 2 - r, H // 2 - r * 0.62, W // 2 + r, H // 2 + r * 0.62), 200, 340, fill=(255, 255, 255, 40), width=2)
        od.arc((W // 2 - r, H // 2 - r * 0.62, W // 2 + r, H // 2 + r * 0.62), 20, 160, fill=(255, 255, 255, 40), width=2)
    for sx, sy, s in ((190, 140, 20), (1100, 120, 15), (1010, 580, 22), (130, 540, 13), (700, 70, 10)):
        od.polygon([(sx, sy - s), (sx + s // 3, sy - s // 3), (sx + s, sy), (sx + s // 3, sy + s // 3), (sx, sy + s),
                    (sx - s // 3, sy + s // 3), (sx - s, sy), (sx - s // 3, sy - s // 3)], fill=(255, 240, 190, 235))
    img = img.convert("RGBA")
    img.alpha_composite(ov)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((56, 56, W - 56, H - 56), 44, outline=(255, 255, 255, 150), width=3)
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        title = ImageFont.truetype(os.path.join(here, "assets", "Loki.ttf"), 190)
        small = ImageFont.truetype(os.path.join(here, "assets", "Loki.ttf"), 64)
    except Exception:
        title, small = _font(110, True), _font(48, True)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((W // 2, H // 2 - 20), "Cooperation", font=title, fill=(255, 80, 170, 200), anchor="mm")
    sh = sh.filter(ImageFilter.GaussianBlur(18))
    img.alpha_composite(sh)
    d = ImageDraw.Draw(img)
    d.text((W // 2 + 5, H // 2 - 15), "Cooperation", font=title, fill=(60, 20, 120), anchor="mm")
    d.text((W // 2, H // 2 - 20), "Cooperation", font=title, fill=(255, 255, 255), anchor="mm")
    d.text((W // 2, H // 2 + 105), "СОТРУДНИЧЕСТВО", font=_font(38, True), fill=(255, 215, 150), anchor="mm")
    d.text((W // 2, H // 2 + 175), "@swagslave", font=small, fill=(255, 255, 255), anchor="mm")
    bio = io.BytesIO()
    img.convert("RGB").save(bio, "JPEG", quality=92)
    bio.seek(0)
    return bio
