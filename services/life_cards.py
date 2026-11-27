# -*- coding: utf-8 -*-
"""Картинки для «купить дом» (четыре нарисованных жилья) и «найти работу» (плитки профессий с зарплатой)."""

import io

from PIL import Image, ImageDraw

from services.monopoly_board import _font

W = 900


def _grad(img, c1, c2, h):
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        d.line((0, y, img.width, y), fill=tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)))


def _scene(d, x, y, w, h, kind):
    """Рисует жильё внутри прямоугольника (x, y, w, h)."""
    d.rounded_rectangle((x, y, x + w, y + h), 18, fill=(40, 52, 96))
    d.rectangle((x, y + h * 0.78, x + w, y + h), fill=(52, 96, 66))
    d.rounded_rectangle((x, y, x + w, y + h), 18, outline=(120, 130, 190), width=3)
    gx, gy = x + w / 2, y + h * 0.78
    win = (255, 226, 130)
    if kind == "комната":
        d.rectangle((x + w * .15, y + h * .2, x + w * .85, gy), fill=(212, 190, 160))
        d.rectangle((x + w * .15, gy - 8, x + w * .85, gy), fill=(140, 100, 70))
        d.rectangle((x + w * .55, y + h * .3, x + w * .78, y + h * .55), fill=(130, 190, 250), outline=(250, 250, 250), width=4)
        d.line((x + w * .665, y + h * .3, x + w * .665, y + h * .55), fill=(250, 250, 250), width=3)
        d.rectangle((x + w * .2, gy - h * .17, x + w * .5, gy - 8), fill=(180, 90, 100))
        d.rectangle((x + w * .2, gy - h * .22, x + w * .27, gy - h * .17), fill=(240, 235, 235))
        d.ellipse((x + w * .8, gy - h * .26, x + w * .86, gy - h * .2), fill=win)
    elif kind == "квартира":
        bx0, bx1, by0 = x + w * .22, x + w * .78, y + h * .1
        d.rectangle((bx0, by0, bx1, gy), fill=(170, 150, 150), outline=(90, 80, 90), width=3)
        for r in range(4):
            for c in range(3):
                wx, wy = bx0 + 16 + c * ((bx1 - bx0 - 32) / 3), by0 + 16 + r * ((gy - by0 - 40) / 4)
                d.rectangle((wx, wy, wx + 28, wy + 30), fill=win if (r + c) % 2 == 0 else (90, 110, 150))
        d.rectangle((gx - 16, gy - 34, gx + 16, gy), fill=(90, 60, 50))
    elif kind == "дом":
        bx0, bx1, by0 = x + w * .2, x + w * .8, y + h * .42
        d.rectangle((bx0, by0, bx1, gy), fill=(232, 205, 160), outline=(120, 90, 60), width=3)
        d.polygon([(bx0 - 14, by0), (gx, y + h * .14), (bx1 + 14, by0)], fill=(190, 70, 60), outline=(100, 40, 40))
        d.rectangle((bx1 - 40, y + h * .14, bx1 - 22, y + h * .3), fill=(120, 80, 70))
        d.rectangle((gx - 18, gy - 52, gx + 18, gy), fill=(110, 70, 50))
        for wx in (bx0 + 22, bx1 - 62):
            d.rectangle((wx, by0 + 26, wx + 40, by0 + 64), fill=win, outline=(120, 90, 60), width=3)
        d.ellipse((x + w * .04, gy - 74, x + w * .18, gy - 6), fill=(48, 128, 70)); d.rectangle((x + w * .105, gy - 20, x + w * .115, gy), fill=(100, 70, 40))
    else:  # особняк
        bx0, bx1, by0 = x + w * .1, x + w * .9, y + h * .36
        d.rectangle((bx0, by0, bx1, gy), fill=(238, 232, 220), outline=(150, 140, 120), width=3)
        d.polygon([(bx0 - 10, by0), (gx, y + h * .1), (bx1 + 10, by0)], fill=(70, 80, 120), outline=(40, 46, 80))
        for i in range(5):
            cx = bx0 + 24 + i * ((bx1 - bx0 - 48) / 4)
            d.rectangle((cx - 7, by0 + 10, cx + 7, gy), fill=(250, 248, 240), outline=(170, 160, 140))
        for r in range(2):
            for c in range(4):
                wx = bx0 + 40 + c * ((bx1 - bx0 - 80) / 4)
                d.rectangle((wx, by0 + 26 + r * 50, wx + 22, by0 + 54 + r * 50), fill=win)
        d.rectangle((gx - 16, gy - 46, gx + 16, gy), fill=(110, 70, 50))
        d.line((gx, y + h * .1, gx, y + h * .02), fill=(220, 220, 230), width=3)
        d.polygon([(gx, y + h * .02), (gx + 26, y + h * .05), (gx, y + h * .08)], fill=(230, 70, 70))
        d.ellipse((x + w * .02, gy + 4, x + w * .2, gy + 22), fill=(110, 170, 230))


def houses_card(houses, cur=None, coins=None):
    """houses: {ключ: (название, цена, бонус%, url)}. -> BytesIO JPEG."""
    keys = list(houses)
    cw, ch, pad = 410, 300, 26
    H = 110 + 2 * (ch + 90) + pad
    img = Image.new("RGB", (W, H))
    _grad(img, (24, 20, 56), (12, 12, 28), H)
    d = ImageDraw.Draw(img)
    d.text((W // 2, 44), "НЕДВИЖИМОСТЬ", font=_font(36, True), fill=(250, 205, 90), anchor="mm")
    d.text((W // 2, 82), "Жильё даёт прибавку к зарплате" + (f" · у тебя {coins} славКоин" if coins is not None else ""), font=_font(18), fill=(190, 195, 225), anchor="mm")
    for i, k in enumerate(keys[:4]):
        name, price, bonus = houses[k][0], houses[k][1], houses[k][2]
        x = pad + (i % 2) * (cw + pad - 12)
        y = 112 + (i // 2) * (ch + 96)
        _scene(d, x, y, cw, ch, k)
        d.text((x + 6, y + ch + 24), name, font=_font(28, True), fill=(255, 255, 255), anchor="lm")
        d.text((x + 6, y + ch + 58), f"{price} славКоин  ·  +{bonus}% к зарплате", font=_font(20), fill=(130, 230, 170), anchor="lm")
        if cur == k:
            d.rounded_rectangle((x + cw - 130, y + 12, x + cw - 12, y + 46), 12, fill=(46, 160, 100))
            d.text((x + cw - 71, y + 29), "У ТЕБЯ", font=_font(18, True), fill=(255, 255, 255), anchor="mm")
    bio = io.BytesIO(); img.save(bio, "JPEG", quality=88); bio.seek(0)
    return bio


JOB_COL = {"курьер": (230, 140, 60), "уборщик": (80, 170, 200), "продавец": (220, 100, 130), "официант": (190, 120, 220),
           "таксист": (240, 200, 60), "программист": (70, 130, 240), "врач": (60, 200, 150), "пилот": (110, 150, 250),
           "рыбак": (60, 150, 210), "повар": (235, 110, 80), "сварщик": (250, 150, 50), "машинист": (150, 110, 90),
           "стюардесса": (230, 90, 150), "адвокат": (120, 120, 160), "директор": (250, 190, 70)}


def jobs_card(items, cur=None):
    """items: [(ключ, название, зарплата, пауза_ч, закрыта)]. Плитки профессий с цветом, буквой и зарплатой."""
    cols = 3
    rows = (len(items) + cols - 1) // cols
    tw, th, gap = 270, 150, 20
    H = 110 + rows * (th + gap) + 10
    img = Image.new("RGB", (W, H))
    _grad(img, (24, 20, 56), (12, 12, 28), H)
    d = ImageDraw.Draw(img, "RGBA")
    d.text((W // 2, 44), "БИРЖА ТРУДА", font=_font(36, True), fill=(250, 205, 90), anchor="mm")
    d.text((W // 2, 82), "зарплата за смену · пауза между сменами", font=_font(18), fill=(190, 195, 225), anchor="mm")
    for i, (k, name, pay, cd, locked) in enumerate(items):
        x = gap + (i % cols) * (tw + gap // 2 + 2)
        y = 108 + (i // cols) * (th + gap)
        col = JOB_COL.get(k, (130, 140, 200))
        dim = 0.35 if locked else 1.0
        c = tuple(int(v * dim) for v in col)
        d.rounded_rectangle((x, y, x + tw, y + th), 20, fill=(30, 32, 58, 255), outline=c + (255,), width=3)
        d.ellipse((x + 16, y + 20, x + 96, y + 100), fill=c + (255,))
        d.text((x + 56, y + 60), name[0].upper(), font=_font(46, True), fill=(255, 255, 255, 255), anchor="mm")
        d.text((x + 112, y + 36), name, font=_font(23, True), fill=(255, 255, 255, 255 if not locked else 140), anchor="lm")
        d.text((x + 112, y + 74), f"{pay} СК", font=_font(26, True), fill=(130, 235, 170, 255 if not locked else 120), anchor="lm")
        cd_txt = f"{cd:g} ч" if cd >= 1 else f"{int(cd * 60)} мин"
        d.text((x + 112, y + 106), f"пауза {cd_txt}", font=_font(18), fill=(190, 195, 225, 255 if not locked else 120), anchor="lm")
        if locked:
            d.rounded_rectangle((x + 16, y + th - 38, x + tw - 16, y + th - 12), 10, fill=(0, 0, 0, 150))
            d.text((x + tw // 2, y + th - 25), "ЗАКРЫТО", font=_font(16, True), fill=(250, 200, 90, 255), anchor="mm")
        elif cur == k:
            d.rounded_rectangle((x + 16, y + th - 38, x + tw - 16, y + th - 12), 10, fill=(46, 160, 100, 220))
            d.text((x + tw // 2, y + th - 25), "ТВОЯ РАБОТА", font=_font(16, True), fill=(255, 255, 255, 255), anchor="mm")
    bio = io.BytesIO(); img.save(bio, "JPEG", quality=88); bio.seek(0)
    return bio
