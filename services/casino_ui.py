# -*- coding: utf-8 -*-
"""Картинки казино: баннер-меню, стол блэкджека, рейтинг, GIF краша."""

import io
import math
import random

from services.monopoly_board import _font

GOLD, RED, GREEN, WHITE = (245, 195, 70), (225, 60, 70), (70, 200, 120), (255, 255, 255)

TITLES = ((0, "Новичок"), (1500, "Игрок"), (3000, "Азартный"), (7000, "Высокий роллер"), (15000, "Король казино"))


def casino_title(best):
    t = TITLES[0][1]
    for need, name in TITLES:
        if (best or 0) >= need:
            t = name
    return t


def _png(im, colors=64):
    buf = io.BytesIO()
    im.quantize(colors=colors).save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


def _clean(s, n=18):
    return "".join(ch for ch in (s or "") if ord(ch) < 0x2E80 and ch.isprintable())[:n].strip() or "Игрок"


def _felt(w, h, dark=False):
    from PIL import Image, ImageDraw
    a, b = ((12, 84, 52), (6, 44, 28)) if not dark else ((38, 16, 52), (14, 8, 24))
    im = Image.new("RGB", (w, h), a)
    d = ImageDraw.Draw(im)
    for y in range(h):
        t = y / h
        d.line([(0, y), (w, y)], fill=tuple(int(a[c] * (1 - t) + b[c] * t) for c in range(3)))
    return im, d


def _lights(d, w, h, n=18):
    for i in range(n):
        x = 20 + i * (w - 40) / (n - 1)
        c = GOLD if i % 2 == 0 else (255, 120, 60)
        d.ellipse((x - 4, 8, x + 4, 16), fill=c)
        d.ellipse((x - 4, h - 17, x + 4, h - 9), fill=c)


def lobby_card(name, chips, best):
    """Баннер казино: имя, баланс, титул."""
    W, H = 800, 360
    im, d = _felt(W, H, dark=True)
    d.rounded_rectangle((8, 8, W - 9, H - 9), 22, outline=GOLD, width=4)
    _lights(d, W, H, 24)
    d.text((W // 2, 74), "КАЗИНО", font=_font(74, True), fill=GOLD, anchor="mm", stroke_width=4, stroke_fill=(90, 40, 0))
    d.text((W // 2, 130), "СлавБакс · СЛОТЫ · РУЛЕТКА · БЛЭКДЖЕК · КРЭШ", font=_font(17, True), fill=(235, 220, 255), anchor="mm")
    # фишки
    for i, c in enumerate(((RED), (40, 40, 48), (60, 120, 230), GREEN)):
        x = 90 + i * 40
        d.ellipse((x - 26, 205, x + 26, 257), fill=c, outline=WHITE, width=3)
        d.ellipse((x - 16, 215, x + 16, 247), outline=WHITE, width=2)
    d.rounded_rectangle((300, 170, W - 40, 320), 18, fill=(22, 14, 38), outline=(120, 90, 180), width=2)
    d.text((324, 184), _clean(name), font=_font(28, True), fill=WHITE)
    d.text((324, 226), f"{chips} славБакс", font=_font(40, True), fill=GOLD)
    d.text((324, 282), f"Статус: {casino_title(best)}", font=_font(20, True), fill=(190, 170, 235))
    d.text((90, 300), "ставка 10–1000", font=_font(16), fill=(180, 160, 220), anchor="lm")
    return _png(im)


def top_card(rows):
    W, H = 800, 120 + 52 * max(1, len(rows))
    im, d = _felt(W, H, dark=True)
    d.rounded_rectangle((8, 8, W - 9, H - 9), 22, outline=GOLD, width=4)
    d.text((W // 2, 52), "ТОП КАЗИНО", font=_font(40, True), fill=GOLD, anchor="mm")
    medal = {1: (245, 195, 70), 2: (200, 205, 215), 3: (205, 130, 70)}
    for i, r in enumerate(rows, 1):
        y = 104 + (i - 1) * 52
        d.rounded_rectangle((30, y, W - 30, y + 44), 12, fill=(30, 20, 52))
        d.ellipse((42, y + 6, 74, y + 38), fill=medal.get(i, (70, 70, 100)))
        d.text((58, y + 22), str(i), font=_font(20, True), fill=(20, 20, 20), anchor="mm")
        d.text((92, y + 22), _clean(r["name"] or "?", 20), font=_font(22, True), fill=WHITE, anchor="lm")
        d.text((470, y + 22), casino_title(r["best"] if "best" in r.keys() else r["chips"]), font=_font(16), fill=(190, 170, 235), anchor="lm")
        d.text((W - 48, y + 22), f"{r['chips']}", font=_font(24, True), fill=GOLD, anchor="rm")
    return _png(im)


# ------------------------------ блэкджек ------------------------------
SUITS = {"s": ("♠", (20, 20, 30)), "h": ("♥", (210, 40, 50)), "d": ("♦", (210, 40, 50)), "c": ("♣", (20, 20, 30))}


def _card(d, x, y, card, hidden=False, w=84, h=120):
    if hidden:
        d.rounded_rectangle((x, y, x + w, y + h), 10, fill=(150, 30, 60), outline=WHITE, width=3)
        d.rounded_rectangle((x + 8, y + 8, x + w - 8, y + h - 8), 6, outline=(255, 190, 200), width=2)
        d.text((x + w // 2, y + h // 2), "♠", font=_font(40, True), fill=(255, 190, 200), anchor="mm")
        return
    rank, suit = card
    sym, col = SUITS[suit]
    d.rounded_rectangle((x + 3, y + 4, x + w + 3, y + h + 4), 10, fill=(0, 0, 0))
    d.rounded_rectangle((x, y, x + w, y + h), 10, fill=(252, 250, 244), outline=(180, 180, 180), width=2)
    d.text((x + 8, y + 6), rank, font=_font(26, True), fill=col)
    d.text((x + 8, y + 34), sym, font=_font(24, True), fill=col)
    d.text((x + w // 2 + 4, y + h // 2 + 14), sym, font=_font(46, True), fill=col, anchor="mm")


def hand_value(cards):
    tot, aces = 0, 0
    for r, _ in cards:
        if r == "A":
            aces += 1
            tot += 11
        elif r in ("K", "Q", "J", "10"):
            tot += 10
        else:
            tot += int(r)
    while tot > 21 and aces:
        tot -= 10
        aces -= 1
    return tot


def bj_card(player, dealer, hide, bet, status=None, col=WHITE, name=""):
    W, H = 640, 400
    im, d = _felt(W, H)
    d.rounded_rectangle((8, 8, W - 9, H - 9), 22, outline=GOLD, width=3)
    d.text((W // 2, 30), "БЛЭКДЖЕК", font=_font(22, True), fill=GOLD, anchor="mm")
    d.text((26, 56), "КРУПЬЕ" + ("" if hide else f"  ·  {hand_value(dealer)}"), font=_font(18, True), fill=(220, 240, 225))
    for i, c in enumerate(dealer):
        _card(d, 26 + i * 62, 82, c, hidden=(hide and i == 1))
    d.text((26, 222), f"{_clean(name, 14)}  ·  {hand_value(player)}", font=_font(18, True), fill=(220, 240, 225))
    for i, c in enumerate(player):
        _card(d, 26 + i * 62, 248, c)
    d.rounded_rectangle((W - 150, 150, W - 26, 214), 14, fill=(20, 40, 30), outline=GOLD, width=2)
    d.text((W - 88, 170), "СТАВКА", font=_font(13, True), fill=(200, 220, 205), anchor="mm")
    d.text((W - 88, 196), str(bet), font=_font(26, True), fill=GOLD, anchor="mm")
    if status:
        d.rounded_rectangle((W - 230, 300, W - 20, 372), 16, fill=(10, 20, 14), outline=col, width=3)
        d.text((W - 125, 336), status, font=_font(17, True), fill=col, anchor="mm")
    return _png(im)


# ------------------------------ краш ------------------------------
def crash_gif(crash, players, k=0.085):
    """players: [(имя, множитель забора или None)]. GIF: ракета летит по кривой и взрывается."""
    from PIL import Image, ImageDraw
    W, H = 440, 280
    Tc = math.log(max(crash, 1.0001)) / k
    top = max(2.0, crash * 1.1)
    x0, x1, y0, y1 = 36, W - 24, 30, H - 40

    def pt(t):
        m = math.exp(k * t)
        return x0 + (x1 - x0) * min(1, t / max(Tc, 0.1)) * 0.92, y1 - (y1 - y0) * min(1.0, (m - 1) / (top - 1))

    N = 22
    frames, dur = [], []
    for f in range(N + 7):
        im, d = _felt(W, H, dark=True)
        d.rounded_rectangle((5, 5, W - 6, H - 6), 16, outline=GOLD, width=2)
        for g in range(4):
            gy = y0 + (y1 - y0) * g / 3
            d.line([(x0, gy), (x1, gy)], fill=(60, 50, 90), width=1)
        k_ = min(1.0, (f + 1) / N)
        t_end = Tc * k_
        pts = [pt(Tc * i / 30) for i in range(31) if Tc * i / 30 <= t_end]
        if len(pts) >= 2:
            poly = pts + [(pts[-1][0], y1), (pts[0][0], y1)]
            d.polygon(poly, fill=(40, 70, 60))
            d.line(pts, fill=GREEN, width=4)
        px, py = pt(t_end)
        m = math.exp(k * t_end)
        if f < N:
            d.polygon([(px, py - 14), (px - 9, py + 8), (px + 9, py + 8)], fill=WHITE)
            d.polygon([(px - 5, py + 8), (px + 5, py + 8), (px, py + 20 + (f % 3) * 4)], fill=(255, 150, 40))
            d.text((W // 2, 60), f"x{m:.2f}", font=_font(54, True), fill=GREEN, anchor="mm", stroke_width=3, stroke_fill=(0, 40, 20))
        else:
            r = 14 + (f - N) * 10
            d.ellipse((px - r, py - r, px + r, py + r), fill=(255, 140, 40))
            d.ellipse((px - r * .6, py - r * .6, px + r * .6, py + r * .6), fill=(255, 230, 120))
            d.text((W // 2, 60), f"КРАШ x{crash:.2f}", font=_font(44, True), fill=RED, anchor="mm", stroke_width=3, stroke_fill=(60, 0, 0))
        d.text((W // 2, 18), "РАКЕТА", font=_font(13, True), fill=GOLD, anchor="mm")
        yy = H - 28
        if f >= N:
            txt = "  ".join(f"{_clean(n, 8)} x{c:.2f}" if c else f"{_clean(n, 8)} взрыв" for n, c in players[:4])
            d.text((W // 2, yy), txt[:60], font=_font(14, True), fill=WHITE, anchor="mm")
        frames.append(im)
        dur.append(70 if f < N else 600)
    q = [x.quantize(colors=48) for x in frames]
    buf = io.BytesIO()
    q[0].save(buf, format="GIF", save_all=True, append_images=q[1:], duration=dur, loop=0, optimize=True)
    return buf.getvalue()
