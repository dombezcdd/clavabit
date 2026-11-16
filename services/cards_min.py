# -*- coding: utf-8 -*-
"""Минималистичные карточки для работы, домов и питомцев (вместо аниме-гифок)."""

from io import BytesIO

from services.monopoly_board import _font

W, H = 800, 360
# профессия: (символ, цвет)
JOB_STYLE = {
    "курьер": ("➤", (255, 140, 66)), "уборщик": ("✦", (64, 196, 170)), "продавец": ("⛁", (255, 193, 7)),
    "официант": ("☕", (233, 120, 120)), "таксист": ("➤", (250, 204, 21)), "программист": ("⌘", (99, 102, 241)),
    "врач": ("✚", (239, 83, 80)), "пилот": ("✈", (66, 165, 245)), "рыбак": ("⚓", (38, 166, 154)),
    "повар": ("♨", (255, 112, 67)), "сварщик": ("⚙", (255, 160, 0)), "машинист": ("⚑", (120, 144, 156)),
    "стюардесса": ("✈", (171, 130, 255)), "адвокат": ("⚖", (84, 110, 122)), "директор": ("♛", (212, 175, 55)),
}
DEFAULT = ("★", (99, 102, 241))
HOUSE_COLOR = (66, 135, 245)
PET_SYM = {}


def _png(im):
    b = BytesIO()
    im.convert("P", palette=1, colors=64).save(b, "PNG", optimize=True)
    b.seek(0)
    return b


def _card(symbol, title, sub, color):
    from PIL import Image, ImageDraw
    top = tuple(int(c + (255 - c) * 0.12) for c in color)
    bot = tuple(int(c * 0.62) for c in color)
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.ellipse((W - 330, -90, W + 70, 310), fill=(255, 255, 255, 34))
    od.ellipse((-110, H - 170, 190, H + 130), fill=(255, 255, 255, 24))
    od.ellipse((70, 70, 270, 270), fill=(255, 255, 255, 60))
    im = Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")
    d = ImageDraw.Draw(im)
    f = _font(110, True)
    bb = d.textbbox((0, 0), symbol, font=f)
    d.text((170 - (bb[0] + bb[2]) / 2, 170 - (bb[1] + bb[3]) / 2), symbol, font=f, fill=(255, 255, 255))
    d.text((320, 120), title, font=_font(54, True), fill=(255, 255, 255))
    d.rounded_rectangle((322, 200, 402, 206), 3, fill=(255, 255, 255))
    d.text((320, 224), sub, font=_font(28), fill=(255, 255, 255, 230))
    return _png(im)


def card_for(key):
    """key вида «раб:курьер», «проф:врач», «дом:квартира», «пет:кот». None, если карточки нет."""
    try:
        kind, _, name = key.partition(":")
        if kind in ("раб", "проф"):
            from services.jobs import JOBS
            sym, col = JOB_STYLE.get(name, DEFAULT)
            title = JOBS[name][0] if name in JOBS else name.title()
            return _card(sym, title, "Рабочая смена" if kind == "раб" else "Твоя профессия", col)
        if kind == "дом":
            from services.jobs import HOUSES
            if name in HOUSES:
                return _card("⌂", HOUSES[name][0], f"Бонус к зарплате +{HOUSES[name][2]}%", HOUSE_COLOR)
        if kind == "пет":
            from services.jobs import PETS
            if name in PETS:
                return _card("✿", PETS[name][0], "Новый питомец", (236, 112, 99))
            return _card("♥", "Питомцы", "Корм и забота", (236, 112, 99))
    except Exception:
        return None
    return None
