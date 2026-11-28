# -*- coding: utf-8 -*-
"""Красивая обложка «Сотрудничество»: градиент, узоры и крупная надпись."""

import io
import math

from PIL import Image, ImageDraw, ImageFilter

from services.monopoly_board import _font

W, H = 1280, 720


def coop_card():
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):                      # диагональный градиент фиолетовый -> розовый
        for x in range(0, W, 8):
            t = (x / W * 0.6 + y / H * 0.4)
            d.rectangle((x, y, x + 8, y), fill=(int(40 + 150 * t), int(20 + 30 * t), int(110 + 40 * (1 - t))))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    # концентрические кольца по углам
    for cx, cy in ((0, 0), (W, H)):
        for r in range(60, 700, 52):
            od.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 255, 255, 38), width=3)
    # ромбовая сетка
    for gx in range(-40, W + 80, 80):
        for gy in range(-40, H + 80, 80):
            if (gx // 80 + gy // 80) % 2 == 0:
                od.polygon([(gx, gy - 14), (gx + 14, gy), (gx, gy + 14), (gx - 14, gy)], fill=(255, 255, 255, 26))
    # волны снизу
    for k, a in enumerate((60, 45, 30)):
        pts = [(x, 600 + k * 34 + 22 * math.sin(x / 90 + k * 1.3)) for x in range(0, W + 10, 10)]
        od.polygon(pts + [(W, H), (0, H)], fill=(255, 255, 255, a // 3))
        od.line(pts, fill=(255, 255, 255, a + 40), width=3)
    # звёзды-искры
    for sx, sy, s in ((210, 150, 16), (1080, 130, 12), (980, 560, 18), (140, 520, 11), (640, 90, 9), (1170, 360, 10)):
        od.polygon([(sx, sy - s), (sx + s // 3, sy - s // 3), (sx + s, sy), (sx + s // 3, sy + s // 3), (sx, sy + s),
                    (sx - s // 3, sy + s // 3), (sx - s, sy), (sx - s // 3, sy - s // 3)], fill=(255, 235, 170, 230))
    img.paste(ov, (0, 0), ov)
    # рамка и надпись
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((60, 60, W - 60, H - 60), 40, outline=(255, 255, 255), width=4)
    d.rounded_rectangle((76, 76, W - 76, H - 76), 30, outline=(255, 220, 140), width=2)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((W // 2 + 4, H // 2 + 8), "СОТРУДНИЧЕСТВО", font=_font(90, True), fill=(20, 0, 50, 170), anchor="mm")
    sh = sh.filter(ImageFilter.GaussianBlur(7))
    img.paste(sh, (0, 0), sh)
    d = ImageDraw.Draw(img)
    d.text((W // 2, H // 2), "СОТРУДНИЧЕСТВО", font=_font(90, True), fill=(255, 255, 255), anchor="mm")
    d.line((W // 2 - 200, H // 2 + 70, W // 2 + 200, H // 2 + 70), fill=(255, 220, 140), width=4)
    d.text((W // 2, H // 2 + 112), "@swagslave", font=_font(38, True), fill=(255, 235, 190), anchor="mm")
    bio = io.BytesIO()
    img.save(bio, "JPEG", quality=92)
    bio.seek(0)
    return bio
