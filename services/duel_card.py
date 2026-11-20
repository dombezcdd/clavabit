# -*- coding: utf-8 -*-
"""Картинка дуэли на выстрелах: жизни, патроны, действия прошлого раунда, итог."""

import io

from services.monopoly_board import _font

W, H = 900, 560
BG1, BG2 = (20, 22, 38), (10, 11, 20)
RED, GOLD, GREEN, GREY = (235, 70, 80), (245, 195, 70), (80, 205, 130), (110, 116, 145)
PANEL = (32, 35, 56)


def _heart(d, cx, cy, s, fill, outline=None):
    r = s * 0.27
    d.ellipse((cx - s / 2, cy - s / 2 + 1, cx, cy + s * 0.05), fill=fill)
    d.ellipse((cx, cy - s / 2 + 1, cx + s / 2, cy + s * 0.05), fill=fill)
    d.polygon([(cx - s / 2 + 1, cy - s * 0.12), (cx + s / 2 - 1, cy - s * 0.12), (cx, cy + s * 0.5)], fill=fill)


def _bullet(d, x, y, on):
    c = GOLD if on else (58, 62, 90)
    d.rounded_rectangle((x, y + 8, x + 16, y + 40), 3, fill=c)
    d.pieslice((x, y, x + 16, y + 16), 180, 360, fill=c)
    d.rectangle((x, y + 36, x + 16, y + 40), fill=(150, 110, 30) if on else (45, 48, 72))


def _icon(d, kind, cx, cy, col):
    if kind == "s":          # прицел
        d.ellipse((cx - 14, cy - 14, cx + 14, cy + 14), outline=col, width=3)
        d.line((cx - 20, cy, cx + 20, cy), fill=col, width=3)
        d.line((cx, cy - 20, cx, cy + 20), fill=col, width=3)
    elif kind == "b":        # щит
        d.polygon([(cx - 15, cy - 16), (cx + 15, cy - 16), (cx + 15, cy + 2), (cx, cy + 18), (cx - 15, cy + 2)], outline=col, fill=None, width=3)
    elif kind == "r":        # перезарядка
        d.arc((cx - 15, cy - 15, cx + 15, cy + 15), 40, 320, fill=col, width=4)
        d.polygon([(cx + 9, cy - 19), (cx + 21, cy - 5), (cx + 4, cy - 6)], fill=col)
    else:                    # потерян ход
        d.line((cx - 12, cy - 12, cx + 12, cy + 12), fill=col, width=4)
        d.line((cx + 12, cy - 12, cx - 12, cy + 12), fill=col, width=4)


def _clean(s):
    import unicodedata
    s = unicodedata.normalize("NFKC", s or "")
    return "".join(ch for ch in s if ch.isprintable() and ord(ch) < 0x2E80 and not (0x1F000 <= ord(ch) <= 0x1FFFF))[:18].strip() or "Игрок"


def duel_card(players, rnd, events, winner=None, hp_max=3, ammo_max=3, title="ДУЭЛЬ НА ВЫСТРЕЛАХ"):
    """players: [{name, hp, ammo, hit(bool)}, ...] (2 шт.); events: [(act, текст)] по игроку; winner: индекс или None"""
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (W, H), BG1)
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(BG1[c] * (1 - t) + BG2[c] * t) for c in range(3)))
    d.rectangle((0, 0, W, 8), fill=GOLD if winner is not None else RED)
    d.text((W // 2, 40), title, font=_font(30, True), fill=(255, 255, 255), anchor="mm")
    sub = "ИТОГ" if winner is not None else f"РАУНД {rnd}"
    d.text((W // 2, 74), sub, font=_font(18, True), fill=GOLD, anchor="mm")
    for i, p in enumerate(players):
        x0 = 30 if i == 0 else W // 2 + 30
        x1 = W // 2 - 30 if i == 0 else W - 30
        dead = p["hp"] <= 0
        col = GOLD if winner == i else (RED if p.get("hit") or dead else (70, 76, 112))
        d.rounded_rectangle((x0, 100, x1, 340), 22, fill=PANEL, outline=col, width=4 if col != (70, 76, 112) else 2)
        cx = (x0 + x1) // 2
        acc = (90, 140, 255) if i == 0 else (255, 130, 90)
        d.ellipse((cx - 36, 114, cx + 36, 186), fill=acc if not dead else (70, 70, 80))
        nm = _clean(p["name"])
        d.text((cx, 150), nm[0].upper(), font=_font(38, True), fill=(255, 255, 255), anchor="mm")
        d.text((cx, 208), nm, font=_font(24, True), fill=(255, 255, 255) if not dead else GREY, anchor="mm")
        # жизни
        hw = 44
        sx = cx - (hp_max * hw) // 2 + hw // 2
        for k in range(hp_max):
            _heart(d, sx + k * hw, 250, 34, RED if k < p["hp"] else (58, 62, 90))
        # патроны
        bw = 26
        bx = cx - (ammo_max * bw) // 2
        for k in range(ammo_max):
            _bullet(d, bx + k * bw + 4, 284, k < p["ammo"])
        if winner == i:
            d.text((cx, 330 - 6), "ПОБЕДИТЕЛЬ", font=_font(15, True), fill=GOLD, anchor="mm")
    d.text((W // 2, 220), "VS", font=_font(34, True), fill=(255, 255, 255), anchor="mm")
    # события раунда
    d.text((36, 360), "ЧТО БЫЛО В РАУНДЕ" if events else "", font=_font(15, True), fill=GREY)
    for i, (act, text) in enumerate(events[:2]):
        y = 400 + i * 66
        d.rounded_rectangle((30, y - 28, W - 30, y + 28), 16, fill=PANEL)
        col = {"s": RED, "b": (100, 170, 255), "r": GREEN, "x": GREY}.get(act, GREY)
        _icon(d, act, 70, y, col)
        d.text((110, y), text[:62], font=_font(20, True), fill=(235, 238, 250), anchor="lm")
    buf = io.BytesIO()
    im.quantize(colors=64).save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
