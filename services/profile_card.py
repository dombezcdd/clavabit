# -*- coding: utf-8 -*-
"""Карточка профиля: минималистичная картинка + аккуратная подпись."""

import colorsys
from io import BytesIO

from core.utils import esc, level_need, level_of, title_of
from services.monopoly_board import _font

W, H = 900, 520
BG, PANEL, TXT, SUB = (22, 24, 33), (33, 36, 49), (240, 242, 248), (150, 156, 175)


def _clean(text):
    """Оставляем только символы, которые умеет рисовать шрифт карточки (латиница, кириллица, цифры, знаки)."""
    import unicodedata
    out = []
    for ch in unicodedata.normalize("NFKC", text or ""):
        o = ord(ch)
        if ch.isalnum() and (o < 0x0250 or 0x0400 <= o <= 0x04FF) or ch in " .,-_'!?@#&()+·:":
            out.append(ch)
    return " ".join("".join(out).split())


def _accent(uid):
    h = (uid * 2654435761 % 360) / 360
    r, g, b = colorsys.hsv_to_rgb(h, 0.55, 0.95)
    return int(r * 255), int(g * 255), int(b * 255)


def _fit(d, text, font_fn, size, maxw, bold=True):
    while size > 18 and d.textlength(text, font=font_fn(size, bold)) > maxw:
        size -= 2
    return font_fn(size, bold)


def profile_card(info, avatar=None):
    """info: dict(uid, name, sub, level, title, xp_pct, xp_left, tiles[(подпись, значение)], foot[...])"""
    from PIL import Image, ImageDraw, ImageOps
    acc = info["accent"] = _accent(info["uid"])
    info["name"] = _clean(info["name"]) or "Игрок"
    info["sub"] = _clean(info["sub"]) or "участник"
    info["title"] = _clean(info["title"]) or ""
    info["foot"] = [_clean(x) for x in info["foot"]]
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 10), fill=acc)
    d.rounded_rectangle((24, 34, W - 24, H - 24), 26, fill=PANEL)
    if info.get("vip"):
        gold = (240, 190, 60)
        d.rounded_rectangle((24, 34, W - 24, H - 24), 26, outline=gold, width=5)
        d.rounded_rectangle((34, 44, W - 34, H - 34), 20, outline=(150, 115, 35), width=2)
        d.rectangle((0, 0, W, 10), fill=gold)
    # аватар
    cx, cy, R = 120, 150, 70
    if avatar:
        try:
            a = ImageOps.fit(Image.open(BytesIO(avatar)).convert("RGB"), (R * 2, R * 2))
            m = Image.new("L", (R * 2, R * 2), 0)
            ImageDraw.Draw(m).ellipse((0, 0, R * 2 - 1, R * 2 - 1), fill=255)
            im.paste(a, (cx - R, cy - R), m)
        except Exception:
            avatar = None
    if not avatar:
        d.ellipse((cx - R, cy - R, cx + R, cy + R), fill=acc)
        f = _font(74, True)
        ch = (info["name"] or "?")[:1].upper()
        bb = d.textbbox((0, 0), ch, font=f)
        d.text((cx - (bb[0] + bb[2]) / 2, cy - (bb[1] + bb[3]) / 2), ch, font=f, fill=(255, 255, 255))
    d.ellipse((cx - R - 4, cy - R - 4, cx + R + 4, cy + R + 4), outline=acc, width=4)
    # имя
    x0 = 220
    d.text((x0, 84), info["name"], font=_fit(d, info["name"], _font, 46, W - x0 - 60), fill=TXT)
    d.text((x0, 144), info["sub"], font=_fit(d, info["sub"], _font, 26, W - x0 - 60, False), fill=SUB)
    if info.get("vip"):
        bw = d.textlength("VIP", font=_font(22, True))
        d.rounded_rectangle((W - 60 - bw - 28, 40, W - 40, 76), 10, fill=(240, 190, 60))
        d.text((W - 60 - bw - 14, 44), "VIP", font=_font(22, True), fill=(40, 30, 5))
    # уровень
    d.text((x0, 188), f"Уровень {info['level']} · {info['title']}", font=_fit(d, info["title"], _font, 26, W - x0 - 60), fill=acc)
    bx0, bx1, by = x0, W - 60, 232
    d.rounded_rectangle((bx0, by, bx1, by + 16), 8, fill=(52, 56, 74))
    fill_w = max(16, int((bx1 - bx0) * info["xp_pct"]))
    d.rounded_rectangle((bx0, by, bx0 + fill_w, by + 16), 8, fill=acc)
    d.text((x0, by + 24), info["xp_left"], font=_font(20), fill=SUB)
    # плитки
    tiles = info["tiles"]
    tw, gap, ty = (W - 48 - 40 - gap_total(len(tiles))) // len(tiles), 14, 312
    for i, (lab, val) in enumerate(tiles):
        x = 44 + i * (tw + gap)
        d.rounded_rectangle((x, ty, x + tw, ty + 96), 16, fill=(44, 48, 64))
        d.text((x + 16, ty + 12), lab, font=_font(19), fill=SUB)
        d.text((x + 16, ty + 42), str(val), font=_fit(d, str(val), _font, 34, tw - 28), fill=TXT)
    # нижняя строка
    fy = 432
    parts = [p for p in info["foot"] if p]
    d.text((52, fy), "  ·  ".join(parts) if parts else "Без работы, клана и пары", font=_fit(d, "  ·  ".join(parts), _font, 24, W - 104, False), fill=TXT)
    out = BytesIO()
    im.save(out, "JPEG", quality=86, optimize=True)
    out.seek(0)
    return out


def gap_total(n):
    return 14 * (n - 1)
