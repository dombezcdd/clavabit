# -*- coding: utf-8 -*-
"""Короткая GIF-анимация: график акции рисуется и она взлетает (зелёный) или падает (красный)."""

import io

from services.monopoly_board import _font

W, H = 360, 240
FR = 16


def make_gif(sym, name, pts, price, change):
    """pts: последние цены; change: % изменения. Возвращает bytes GIF или None."""
    from PIL import Image, ImageDraw
    pts = [float(x) for x in pts][-36:]
    if len(pts) < 2:
        return None
    up = change >= 0
    col = (46, 204, 113) if up else (231, 76, 60)
    bg1, bg2 = ((12, 38, 26), (6, 18, 12)) if up else ((44, 14, 14), (20, 6, 6))
    lo, hi = min(pts), max(pts)
    span = max(1e-9, hi - lo)
    x0, x1, y0, y1 = 20, W - 20, 78, H - 26

    def xy(i, v):
        return x0 + (x1 - x0) * i / (len(pts) - 1), y1 - (y1 - y0) * (v - lo) / span

    coords = [xy(i, v) for i, v in enumerate(pts)]
    frames = []
    for f in range(FR):
        k = (f + 1) / FR
        im = Image.new("RGB", (W, H), bg1)
        d = ImageDraw.Draw(im)
        for y in range(H):                       # вертикальный градиент
            t = y / H
            d.line([(0, y), (W, y)], fill=tuple(int(bg1[c] * (1 - t) + bg2[c] * t) for c in range(3)))
        for g in range(4):
            gy = y0 + (y1 - y0) * g / 3
            d.line([(x0, gy), (x1, gy)], fill=(255, 255, 255, 30) if False else (60, 70, 66), width=1)
        n = max(2, int(len(coords) * k))
        part = coords[:n]
        poly = part + [(part[-1][0], y1), (part[0][0], y1)]
        shade = Image.new("RGB", (W, H), bg1)
        ImageDraw.Draw(shade).polygon(poly, fill=tuple(int(col[c] * 0.30 + bg1[c] * 0.7) for c in range(3)))
        im = Image.blend(im, shade, 0.55)
        d = ImageDraw.Draw(im)
        d.line(part, fill=col, width=4, joint="curve")
        px, py = part[-1]
        r = 6 + (f % 4)
        d.ellipse([px - r, py - r, px + r, py + r], outline=col, width=2)
        d.ellipse([px - 4, py - 4, px + 4, py + 4], fill=(255, 255, 255))
        # стрелка-«ракета» вверх или вниз, смещается по кадрам
        ay = 22 + (-1 if up else 1) * int(6 * ((f % 8) / 8))
        tri = [(W - 44, ay + 10), (W - 24, ay + 10), (W - 34, ay - 8)] if up else [(W - 44, ay - 8), (W - 24, ay - 8), (W - 34, ay + 10)]
        d.polygon(tri, fill=col)
        d.text((16, 12), sym, font=_font(26, True), fill=(255, 255, 255))
        d.text((16, 44), (name or "")[:22], font=_font(13), fill=(190, 200, 195))
        cur = pts[0] + (pts[-1] - pts[0]) * k
        d.text((W - 150, 44), f"{cur:.2f}  {'+' if change >= 0 else ''}{change:.1f}%", font=_font(16, True), fill=col)
        d.text((W // 2 - 45, 6), "ВЗЛЁТ" if up else "ПАДЕНИЕ", font=_font(12, True), fill=col)
        frames.append(im.quantize(colors=48))
    buf = io.BytesIO()
    frames[0].save(buf, format="GIF", save_all=True, append_images=frames[1:] + [frames[-1]] * 6,
                   duration=[70] * FR + [140] * 6, loop=0, optimize=True)
    return buf.getvalue()
