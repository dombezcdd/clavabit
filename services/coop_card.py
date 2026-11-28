# -*- coding: utf-8 -*-
"""Картинка «Сотрудничество»."""

import io
import math

from PIL import Image, ImageDraw

from services.monopoly_board import _font

W, H = 1080, 1350


def _star(d, cx, cy, r, fill):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=fill)


def _panel(d, x0, y0, x1, y1, col):
    d.rounded_rectangle((x0, y0, x1, y1), 28, fill=(28, 30, 56), outline=col, width=3)


def coop_card():
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line((0, y, W, y), fill=(int(30 - 14 * t), int(18 - 6 * t), int(64 - 22 * t)))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.ellipse((-200, -220, 520, 420), fill=(120, 70, 255, 70))
    od.ellipse((620, 820, 1320, 1500), fill=(255, 70, 160, 60))
    img.paste(ov, (0, 0), ov)
    d = ImageDraw.Draw(img)
    gold, mint, soft = (255, 205, 90), (110, 240, 180), (190, 195, 230)
    # заголовок
    d.text((W // 2, 110), "СОТРУДНИЧЕСТВО", font=_font(78, True), fill=gold, anchor="mm")
    d.text((W // 2, 185), "Снимай видео и зарабатывай вместе с нами", font=_font(32), fill=soft, anchor="mm")
    # плашка выплат
    _panel(d, 60, 250, W - 60, 640, (120, 110, 255))
    d.text((W // 2, 305), "ВЫПЛАТА ЗА ПРОСМОТРЫ", font=_font(34, True), fill=soft, anchor="mm")
    d.text((W // 2, 400), "1000 просмотров = 1$", font=_font(62, True), fill=mint, anchor="mm")
    for i, (a, b) in enumerate((("от 0.5$", "минимум"), ("до 5$", "максимум"), ("1000–10 000", "просмотров"))):
        cx = 60 + (W - 120) * (i * 2 + 1) / 6
        d.text((cx, 515), a, font=_font(40, True), fill=(255, 255, 255), anchor="mm")
        d.text((cx, 565), b, font=_font(26), fill=soft, anchor="mm")
    # комментарии
    _panel(d, 60, 670, W - 60, 850, (255, 90, 170))
    _star(d, 160, 760, 54, gold)
    d.text((250, 725), "Плюс за комментарии в TikTok", font=_font(36, True), fill=(255, 255, 255), anchor="lm")
    d.text((250, 780), "50 комментариев = 15 Telegram Stars", font=_font(34, True), fill=gold, anchor="lm")
    d.text((250, 825), "от 50 до 100, не должны удаляться", font=_font(26), fill=soft, anchor="lm")
    # способы вывода
    d.text((W // 2, 910), "ВЫВОД", font=_font(30, True), fill=soft, anchor="mm")
    for i, (name, col) in enumerate((("Telegram Stars", (255, 205, 90)), ("USDT", (60, 200, 150)), ("TON", (70, 150, 255)))):
        x0 = 60 + i * 335
        d.rounded_rectangle((x0, 940, x0 + 310, 1020), 40, fill=col)
        d.text((x0 + 155, 980), name, font=_font(30, True), fill=(20, 20, 40), anchor="mm")
    # условия
    _panel(d, 60, 1060, W - 60, 1230, (80, 90, 160))
    for i, t in enumerate(("уникальный контент и правильный юзернейм", "доказательства: скриншоты переходов и юзернеймы",
                           "заявка не раньше чем через 5 дней после публикации")):
        y = 1105 + i * 50
        d.ellipse((96, y - 9, 114, y + 9), fill=mint)
        d.text((134, y), t, font=_font(28), fill=(255, 255, 255), anchor="lm")
    # контакт
    d.rounded_rectangle((W // 2 - 200, 1262, W // 2 + 200, 1328), 33, fill=(255, 255, 255))
    d.text((W // 2, 1295), "@swagslave", font=_font(40, True), fill=(30, 20, 70), anchor="mm")
    bio = io.BytesIO()
    img.save(bio, "JPEG", quality=90)
    bio.seek(0)
    return bio
