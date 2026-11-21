# -*- coding: utf-8 -*-
"""GIF для казино: вращение барабанов, колесо рулетки, подбрасывание монеты (всё рисуется Pillow, без эмодзи-шрифтов)."""

import io
import math
import random

from services.monopoly_board import _font

W, H = 400, 260
GOLD, RED, GREEN, WHITE = (245, 195, 70), (225, 60, 70), (70, 200, 120), (255, 255, 255)


def _bg(win=None):
    from PIL import Image, ImageDraw
    top, bot = {None: ((38, 16, 52), (14, 8, 24)), True: ((20, 62, 40), (8, 26, 16)), False: ((58, 18, 24), (22, 8, 10))}[win]
    im = Image.new("RGB", (W, H), top)
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(top[c] * (1 - t) + bot[c] * t) for c in range(3)))
    # неоновая рамка
    d.rounded_rectangle((6, 6, W - 7, H - 7), 18, outline=GOLD, width=3)
    for i in range(14):                         # лампочки
        x = 22 + i * (W - 44) / 13
        c = GOLD if i % 2 == 0 else (255, 120, 60)
        d.ellipse((x - 4, 10, x + 4, 18), fill=c)
        d.ellipse((x - 4, H - 19, x + 4, H - 11), fill=c)
    return im, d


def _sym(d, s, cx, cy, r=34):
    """Рисуем символ слота формами."""
    if s == "🍒":
        d.line((cx - 6, cy - 4, cx + 8, cy - r + 2), fill=(70, 150, 60), width=4)
        d.line((cx + 12, cy - 2, cx + 8, cy - r + 2), fill=(70, 150, 60), width=4)
        d.ellipse((cx - 22, cy - 6, cx - 2, cy + 18), fill=RED)
        d.ellipse((cx + 2, cy - 4, cx + 22, cy + 18), fill=(235, 80, 90))
    elif s == "🍋":
        d.ellipse((cx - 28, cy - 18, cx + 28, cy + 18), fill=(250, 225, 70), outline=(200, 170, 30), width=3)
        d.polygon([(cx + 24, cy - 6), (cx + 34, cy), (cx + 24, cy + 6)], fill=(250, 225, 70))
    elif s == "🔔":
        d.pieslice((cx - 24, cy - 26, cx + 24, cy + 22), 180, 360, fill=GOLD)
        d.polygon([(cx - 24, cy - 2), (cx + 24, cy - 2), (cx + 30, cy + 16), (cx - 30, cy + 16)], fill=GOLD)
        d.ellipse((cx - 6, cy + 14, cx + 6, cy + 26), fill=(200, 140, 30))
    elif s == "💎":
        d.polygon([(cx - 26, cy - 8), (cx - 12, cy - 24), (cx + 12, cy - 24), (cx + 26, cy - 8), (cx, cy + 26)], fill=(90, 210, 255), outline=WHITE)
        d.line((cx - 26, cy - 8, cx + 26, cy - 8), fill=WHITE, width=2)
        d.line((cx - 12, cy - 24, cx - 6, cy - 8, cx, cy + 26), fill=WHITE, width=1)
        d.line((cx + 12, cy - 24, cx + 6, cy - 8, cx, cy + 26), fill=WHITE, width=1)
    else:
        d.text((cx, cy), "7", font=_font(64, True), fill=RED, anchor="mm", stroke_width=3, stroke_fill=(255, 220, 220))


SYMS = ["🍒", "🍋", "🔔", "💎", "7️⃣"]


def _save(frames, durations):
    buf = io.BytesIO()
    q = [f.quantize(colors=48) for f in frames]
    q[0].save(buf, format="GIF", save_all=True, append_images=q[1:], duration=durations, loop=0, optimize=True)
    return buf.getvalue()


def _banner(d, text, col, y=H - 46):
    d.text((W // 2, y), text, font=_font(24, True), fill=col, anchor="mm", stroke_width=2, stroke_fill=(0, 0, 0))


def slots_gif(reels, mult, bet):
    stops = [12, 18, 24]
    total = 30
    frames, dur = [], []
    rng = random.Random(sum(map(ord, "".join(reels))) + bet)
    strips = [[rng.choice(SYMS) for _ in range(40)] for _ in range(3)]
    for f in range(total):
        win = None if f < total - 4 else (mult > 1 or None) if mult else False
        im, d = _bg(win if f >= total - 4 else None)
        d.text((W // 2, 40), "СЛОТЫ", font=_font(26, True), fill=GOLD, anchor="mm")
        for i in range(3):
            x0 = 40 + i * 112
            d.rounded_rectangle((x0, 66, x0 + 100, 190), 14, fill=(250, 248, 240), outline=GOLD, width=3)
            cx = x0 + 50
            if f >= stops[i]:
                _sym(d, reels[i], cx, 128)
            else:
                off = (f * 41 + i * 13) % 82
                for k in (-1, 0, 1, 2):
                    y = 128 + k * 82 - off + 41
                    s = strips[i][(f + k + i) % 40]
                    if 70 < y < 186:
                        _sym(d, s, cx, int(y), 26)
                d.rectangle((x0 + 3, 69, x0 + 97, 90), fill=(250, 248, 240))
                d.rectangle((x0 + 3, 166, x0 + 97, 187), fill=(250, 248, 240))
        if f >= total - 4:
            if mult == 0:
                _banner(d, f"МИМО  −{bet}", (255, 150, 150))
            elif mult == 1:
                _banner(d, "СТАВКА ВЕРНУЛАСЬ", WHITE)
            else:
                _banner(d, ("ДЖЕКПОТ! " if mult >= 50 else "ВЫИГРЫШ ") + f"+{bet * mult - bet}", (150, 255, 180))
        frames.append(im)
        dur.append(60 if f < total - 4 else 700)
    return _save(frames, dur)


def _wheel_pos(n):
    from services.casino import WHEEL
    return WHEEL.index(n if n == "00" else int(n))


def roulette_gif(num, color, kind_text, mult, bet):
    from PIL import Image, ImageDraw
    from services.casino import WHEEL, REDS
    N = len(WHEEL)
    cx, cy, R = 200, 130, 86
    total = 28
    target = _wheel_pos(num)
    frames, dur = [], []
    for f in range(total):
        t = min(1.0, f / (total - 6))
        ease = 1 - (1 - t) ** 3
        rot = (1 - ease) * 540                     # колесо замедляется
        im, d = _bg()
        for i, v in enumerate(WHEEL):
            a0 = (i * 360 / N + rot) - 90
            col = (30, 150, 70) if v in (0, "00") else (RED if v in REDS else (30, 30, 38))
            d.pieslice((cx - R, cy - R, cx + R, cy + R), a0, a0 + 360 / N, fill=col, outline=(200, 170, 80))
        d.ellipse((cx - 38, cy - 38, cx + 38, cy + 38), fill=(60, 40, 20), outline=GOLD, width=3)
        # шарик по кругу, в конце садится в нужный сектор
        ang_final = math.radians(target * 360 / N + 180 / N - 90)
        ang = ang_final + (1 - ease) * 11 + (0 if f >= total - 6 else 0)
        rad = R - 12 - (1 - ease) * 0
        bx, by = cx + rad * math.cos(ang - 0), cy + rad * math.sin(ang)
        d.ellipse((bx - 7, by - 7, bx + 7, by + 7), fill=WHITE, outline=(120, 120, 120))
        if f >= total - 5:
            c = GREEN if color == "зелёное" else (RED if color == "красное" else (50, 50, 60))
            d.ellipse((cx - 30, cy - 30, cx + 30, cy + 30), fill=c, outline=WHITE, width=3)
            d.text((cx, cy), str(num), font=_font(30, True), fill=WHITE, anchor="mm")
            if mult == 0:
                _banner(d, f"МИМО  −{bet}", (255, 150, 150))
            else:
                _banner(d, f"ВЫИГРЫШ +{bet * mult - bet}", (150, 255, 180))
        d.text((W // 2, 22), kind_text[:30], font=_font(16, True), fill=GOLD, anchor="mm")
        frames.append(im)
        dur.append(70 if f < total - 5 else 700)
    return _save(frames, dur)


def coin_gif(side, bet_side, mult, bet):
    total = 22
    frames, dur = [], []
    for f in range(total):
        im, d = _bg(None if f < total - 3 else bool(mult))
        t = min(1.0, f / (total - 4))
        rise = math.sin(t * math.pi) * 60
        cy = 130 - rise
        k = abs(math.cos(f * 0.9)) if f < total - 4 else 1.0
        rw = max(5, int(54 * k))
        d.ellipse((200 - rw, cy - 54, 200 + rw, cy + 54), fill=(240, 190, 60), outline=(255, 235, 150), width=4)
        if rw > 30:
            face = side if f >= total - 4 else ("орёл" if f % 2 else "решка")
            d.text((200, cy), "О" if face == "орёл" else "Р", font=_font(52, True), fill=(130, 85, 10), anchor="mm")
        if f >= total - 3:
            _banner(d, (f"ВЫПАЛ {side.upper()}  ·  +{bet * mult - bet}" if mult else f"ВЫПАЛ {side.upper()}  ·  −{bet}"),
                    (150, 255, 180) if mult else (255, 150, 150))
        d.text((W // 2, 22), f"МОНЕТКА · ставка на {bet_side}", font=_font(16, True), fill=GOLD, anchor="mm")
        frames.append(im)
        dur.append(70 if f < total - 3 else 800)
    return _save(frames, dur)
