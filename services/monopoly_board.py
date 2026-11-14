# -*- coding: utf-8 -*-
"""Монополия: рисует игровое поле картинкой (Pillow, шрифт DejaVu из assets/fonts)."""

import io
import os

from config import BASE
from services.monopoly import GROUPS, N, SEAT_COLORS, TILES

S = 960                     # размер картинки
M = 20                      # поля
C = (S - 2 * M) // 8        # размер клетки
_fonts = {}


def _font(size, bold=False):
    from PIL import ImageFont
    key = (size, bold)
    if key not in _fonts:
        name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        for p in (os.path.join(BASE, "assets", "fonts", name), "/usr/share/fonts/truetype/dejavu/" + name):
            try:
                _fonts[key] = ImageFont.truetype(p, size)
                break
            except Exception:
                continue
        else:
            _fonts[key] = ImageFont.load_default(size)
    return _fonts[key]


def cell_pos(i):
    """номер клетки -> (строка, столбец) на сетке 8x8; СТАРТ в правом нижнем углу"""
    if i == 0:
        return 7, 7
    if i <= 7:
        return 7, 7 - i
    if i <= 14:
        return 14 - i, 0
    if i <= 21:
        return 0, i - 14
    return i - 21, 7


def _wrap(draw, text, font, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + [cur] if cur else lines


def _plain(t):
    """убирает эмодзи: шрифт их не рисует"""
    return "".join(ch for ch in t if ord(ch) < 0x2190 or 0x2200 <= ord(ch) < 0x2600).strip()


def _center(draw, xy_center, text, font, fill):
    draw.text(xy_center, text, font=font, fill=fill, anchor="mm")


def _die(draw, x, y, size, v):
    draw.rounded_rectangle((x, y, x + size, y + size), 12, fill="#f5f1ff", outline="#bdb3e0", width=3)
    r = size // 9
    g = {1: [(1, 1)], 2: [(0, 0), (2, 2)], 3: [(0, 0), (1, 1), (2, 2)], 4: [(0, 0), (2, 0), (0, 2), (2, 2)],
         5: [(0, 0), (2, 0), (1, 1), (0, 2), (2, 2)], 6: [(0, 0), (2, 0), (0, 1), (2, 1), (0, 2), (2, 2)]}[v]
    for cx, cy in g:
        px, py = x + size * (0.25 + 0.25 * cx), y + size * (0.25 + 0.25 * cy)
        draw.ellipse((px - r, py - r, px + r, py + r), fill="#2a2150")


_BASE = None


def _base():
    """Статичная часть поля (клетки, названия, цены, рамка центра): рисуется один раз и копируется."""
    global _BASE
    if _BASE is not None:
        return _BASE.copy()
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (S, S), "#17122b")
    d = ImageDraw.Draw(im)
    f_n, f_p = _font(17, True), _font(16)
    for i, t in enumerate(TILES):
        r, c = cell_pos(i)
        x0, y0 = M + c * C, M + r * C
        d.rounded_rectangle((x0 + 2, y0 + 2, x0 + C - 2, y0 + C - 2), 10, fill="#2d2650", outline="#463d78", width=2)
        top = 0
        if t.get("g"):
            col = GROUPS[t["g"]][0]
            d.rounded_rectangle((x0 + 2, y0 + 2, x0 + C - 2, y0 + 34), 10, fill=col)
            d.rectangle((x0 + 2, y0 + 20, x0 + C - 2, y0 + 34), fill=col)
            top = 36
        label = {"start": "СТАРТ", "chance": "ШАНС ?", "jail": "ТЮРЬМА", "parking": "ОТДЫХ", "gojail": "В ТЮРЬМУ"}.get(t["t"], t["n"])
        if t["t"] == "tax":
            label = f"НАЛОГ ${t['amt']}"
        fn = f_n
        for sz in (17, 15, 13):
            fn = _font(sz, True)
            if d.textlength(label, font=fn) <= C - 10:
                break
        lns = _wrap(d, label, fn, C - 10)[:2]
        ty = y0 + top + (8 if t.get("g") else (C // 2 - 10 * len(lns) - 6 if not t.get("p") else 14))
        for ln in lns:
            _center(d, (x0 + C // 2, ty + 9), ln, fn, "#ffffff")
            ty += 20
        if t.get("p"):
            _center(d, (x0 + C // 2, y0 + 72), f"${t['p']}", f_p, "#cfc7ee")
    x0, y0, x1, y1 = M + C + 6, M + C + 6, M + 7 * C - 6, M + 7 * C - 6
    d.rounded_rectangle((x0, y0, x1, y1), 18, fill="#211b3d", outline="#463d78", width=2)
    _center(d, ((x0 + x1) // 2, y0 + 40), "МОНОПОЛИЯ", _font(30, True), "#ffd166")
    _BASE = im
    return im.copy()


def render(g, lines=None):
    """Игра -> PNG (BytesIO). lines: последние события для центра поля"""
    from PIL import ImageDraw
    im = _base()
    d = ImageDraw.Draw(im)
    f_n, f_p, f_s = _font(17, True), _font(16), _font(13)
    for i, t in enumerate(TILES):
        r, c = cell_pos(i)
        x0, y0 = M + c * C, M + r * C
        if t.get("g"):
            h = g.houses.get(i, 0)
            if h == 5:
                d.rectangle((x0 + C // 2 - 14, y0 + 8, x0 + C // 2 + 14, y0 + 26), fill="#e74c3c", outline="#fff")
            else:
                for k in range(h):
                    d.rectangle((x0 + 14 + k * 22, y0 + 8, x0 + 28 + k * 22, y0 + 26), fill="#2ecc71", outline="#0b3d1f")
        o = g.owner.get(i)
        if o is not None:
            col = SEAT_COLORS[g.seat(g.by_id(o))]
            d.rounded_rectangle((x0 + 6, y0 + C - 14, x0 + C - 6, y0 + C - 6), 4, fill=col)
        here = [p for p in g.players if not p.dead and p.pos == i]
        for k, p in enumerate(here):
            cx = x0 + C // 2 + (k - (len(here) - 1) / 2) * 25
            cy = y0 + C - 25
            s = g.seat(p)
            d.ellipse((cx - 11, cy - 11, cx + 11, cy + 11), fill=SEAT_COLORS[s], outline="#ffffff", width=2)
            _center(d, (cx, cy), str(s + 1), _font(14, True), "#000000" if SEAT_COLORS[s] in ("#f1c40f", "#2ecc71") else "#ffffff")
    x0, y0, x1, y1 = M + C + 6, M + C + 6, M + 7 * C - 6, M + 7 * C - 6
    cx = (x0 + x1) // 2
    _center(d, (cx, y0 + 78), f"круг {min(g.round, g.max_rounds)} из {g.max_rounds}", f_p, "#a79fd0")
    a, b = g.dice
    if a:
        _die(d, cx - 86, y0 + 104, 70, a)
        _die(d, cx + 16, y0 + 104, 70, b)
    py = y0 + 205
    for p in g.players:
        s = g.seat(p)
        cur = p is g.cur() and g.phase != "over"
        if cur:
            d.rounded_rectangle((x0 + 18, py - 4, x1 - 18, py + 34), 10, outline="#ffd166", width=3)
        d.ellipse((x0 + 30, py + 3, x0 + 56, py + 29), fill=SEAT_COLORS[s], outline="#fff", width=2)
        _center(d, (x0 + 43, py + 16), str(s + 1), _font(15, True), "#000000" if SEAT_COLORS[s] in ("#f1c40f", "#2ecc71") else "#ffffff")
        name = p.name if len(p.name) <= 13 else p.name[:12] + "…"
        d.text((x0 + 68, py + 16), name + ("" if p.human else " (бот)"), font=f_p, fill="#8a83ad" if p.dead else "#ffffff", anchor="lm")
        d.text((x1 - 28, py + 16), "банкрот" if p.dead else f"${p.cash}", font=f_n, fill="#8a83ad" if p.dead else "#7dffb0", anchor="rm")
        py += 44
    ly = py + 14
    if lines:
        d.line((x0 + 30, ly - 8, x1 - 30, ly - 8), fill="#463d78", width=2)
        for ln in lines[-8:]:
            for part in _wrap(d, _plain(ln), f_s, x1 - x0 - 70)[:2]:
                if ly < y1 - 18:
                    d.text((x0 + 34, ly), part, font=f_s, fill="#cfc7ee")
                    ly += 19
    buf = io.BytesIO()
    im.save(buf, "PNG", compress_level=3)
    buf.seek(0)
    return buf
