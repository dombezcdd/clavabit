# -*- coding: utf-8 -*-
"""Картинки для биржи: панель котировок и «взлёт/падение» (Pillow, шрифт DejaVu)."""

import io

from services.monopoly_board import _font

GREEN, RED, BG, CARD, TXT, DIM = (46, 204, 113), (231, 76, 60), (22, 27, 38), (34, 41, 56), (240, 243, 248), (140, 150, 170)


def _png(img):
    out = io.BytesIO()
    img.convert("RGB").quantize(64).save(out, "PNG", optimize=True)
    out.seek(0)
    return out


def _spark(d, pts, box, color, width=4):
    x0, y0, x1, y1 = box
    if len(pts) < 2:
        return
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or 1
    xy = [(x0 + (x1 - x0) * i / (len(pts) - 1), y1 - (y1 - y0) * (p - lo) / span) for i, p in enumerate(pts)]
    d.line(xy, fill=color, width=width, joint="curve")
    d.ellipse([xy[-1][0] - 6, xy[-1][1] - 6, xy[-1][0] + 6, xy[-1][1] + 6], fill=color)


def _arrow(d, cx, cy, size, up, color):
    h = size
    if up:
        d.polygon([(cx, cy - h), (cx - h, cy + h // 2), (cx + h, cy + h // 2)], fill=color)
    else:
        d.polygon([(cx, cy + h), (cx - h, cy - h // 2), (cx + h, cy - h // 2)], fill=color)


def overview(rows):
    """rows: [(sym, name, price, prev, [hist])]"""
    from PIL import Image, ImageDraw
    W, H, RH = 900, 90 + 100 * len(rows), 100
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((30, 24), "БИРЖА  ·  славКоины", font=_font(34, True), fill=TXT)
    for i, (sym, name, price, prev, hist) in enumerate(rows):
        y = 80 + i * RH
        d.rounded_rectangle([20, y, W - 20, y + RH - 12], 16, fill=CARD)
        ch = (price - prev) / prev * 100 if prev else 0
        up = ch >= 0
        col = GREEN if up else RED
        _arrow(d, 62, y + 40, 16, up, col)
        d.text((100, y + 12), sym, font=_font(30, True), fill=TXT)
        d.text((100, y + 52), name, font=_font(20), fill=DIM)
        _spark(d, hist, (330, y + 16, 600, y + 66), col)
        d.text((640, y + 12), f"{price:.2f}", font=_font(30, True), fill=TXT)
        d.text((640, y + 52), f"{ch:+.1f}%", font=_font(22, True), fill=col)
    return _png(img)


def alert(sym, name, price, prev, hist):
    """Большая карточка: ракета вверх или обвал."""
    from PIL import Image, ImageDraw
    ch = (price - prev) / prev * 100
    up = ch >= 0
    col = GREEN if up else RED
    W, H = 900, 520
    img = Image.new("RGB", (W, H), (18, 40, 30) if up else (45, 22, 24))
    d = ImageDraw.Draw(img)
    d.text((40, 30), "ВЗЛЁТ" if up else "ПАДЕНИЕ", font=_font(54, True), fill=col)
    d.text((40, 110), f"{sym} · {name}", font=_font(30), fill=TXT)
    d.text((40, 160), f"{price:.2f}", font=_font(64, True), fill=TXT)
    d.text((40, 245), f"{ch:+.1f}% за полчаса", font=_font(34, True), fill=col)
    _arrow(d, 790, 110, 60, up, col)
    d.rounded_rectangle([30, 320, W - 30, H - 30], 20, fill=(0, 0, 0))
    _spark(d, hist, (60, 345, W - 60, H - 55), col, 6)
    return _png(img)
