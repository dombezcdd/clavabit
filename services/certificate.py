# -*- coding: utf-8 -*-
"""Генерация картинки-свидетельства."""

import asyncio
import os
from datetime import datetime, timedelta, timezone

from telegram import ReplyParameters

from config import BASE, CHAT_TAG, HTML, TZ_HOURS
from core.utils import link
from services.relations import uname


# ============================ СВИДЕТЕЛЬСТВО (картинка) ============================
CERT_W, CERT_H = 1600, 1130


CERT_TEXT_REL = ("Этот документ подтверждает искренность чувств прекрасной пары. "
                 "Пусть любовь крепнет с каждым днём.")


CERT_TEXT_MARRY = ("Этот документ подтверждает, что эти двое стали семьёй. "
                   "Пусть в доме всегда будет тепло.")


def _cert_font(kind, size):
    from PIL import ImageFont
    names = ["cert_bold.otf", "cert_bold.ttf"] if kind == "bold" else ["cert_text.otf", "cert_text.ttf"]
    cands = [os.path.join(BASE, n) for n in names]
    cands += ["C:/Windows/Fonts/segoeuib.ttf" if kind == "bold" else "C:/Windows/Fonts/segoeui.ttf",
              "C:/Windows/Fonts/arialbd.ttf" if kind == "bold" else "C:/Windows/Fonts/arial.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if kind == "bold"
              else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    for p in cands:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default(size)


def _heart_points(cx, cy, size):
    import math
    pts = []
    for i in range(0, 360, 4):
        t = math.radians(i)
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * size / 17, cy - y * size / 17))
    return pts


def _circle_avatar(raw, d, name):
    from PIL import Image, ImageDraw
    from io import BytesIO
    if raw:
        try:
            im = Image.open(BytesIO(bytes(raw))).convert("RGB")
            s = min(im.size)
            im = im.crop(((im.width - s) // 2, (im.height - s) // 2,
                          (im.width + s) // 2, (im.height + s) // 2)).resize((d, d), Image.LANCZOS)
        except Exception:
            im = None
    else:
        im = None
    if im is None:
        colors = [(232, 102, 52), (44, 110, 150), (110, 170, 110), (170, 100, 190), (230, 160, 40)]
        im = Image.new("RGB", (d, d), colors[sum(map(ord, name)) % len(colors)])
        dr = ImageDraw.Draw(im)
        f = _cert_font("bold", int(d * 0.5))
        ch = (name.strip()[:1] or "?").upper()
        dr.text((d / 2, d / 2), ch, fill="white", font=f, anchor="mm")
    big = Image.new("L", (d * 3, d * 3), 0)
    ImageDraw.Draw(big).ellipse((0, 0, d * 3 - 1, d * 3 - 1), fill=255)
    mask = big.resize((d, d), Image.LANCZOS)
    out = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out


def _fit(draw, text, kind, max_w, start):
    size = start
    while size > 20:
        f = _cert_font(kind, size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 2
    return _cert_font(kind, 20)


def _wrap(draw, text, font, max_w):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def make_certificate(name_a, name_b, av_a, av_b, date_str, married):
    """Рисует свидетельство. Возвращает BytesIO с JPEG."""
    import math
    from io import BytesIO
    from PIL import Image, ImageDraw, ImageChops
    W, H = CERT_W, CERT_H
    navy, orange, yellow = (44, 72, 98), (232, 102, 52), (245, 176, 40)
    pink, red = (250, 130, 160), (225, 60, 85)
    img = Image.new("RGB", (W, H), (252, 248, 241))
    d = ImageDraw.Draw(img)
    # геометрия по углам (верх справа и низ слева)
    d.rectangle((W - 300, 0, W, 150), fill=navy)
    d.pieslice((W - 420, -150, W - 120, 150), 90, 180, fill=orange)
    d.rectangle((W - 150, 150, W, 300), fill=yellow)
    d.pieslice((W - 300, 150, W, 450), 270, 360, fill=orange)
    d.ellipse((W - 560, 40, W - 500, 100), fill=navy)
    d.rectangle((0, H - 110, 210, H), fill=navy)
    d.pieslice((100, H - 110, 320, H + 110), 270, 360, fill=orange)
    d.rectangle((0, H - 220, 110, H - 110), fill=yellow)
    d.pieslice((-110, H - 330, 110, H - 110), 0, 90, fill=orange)
    for i in range(3):
        for j in range(3):
            d.ellipse((60 + i * 34, 90 + j * 34, 72 + i * 34, 102 + j * 34), fill=navy)
            d.ellipse((W - 150 + i * 34, 540 + j * 34, W - 138 + i * 34, 552 + j * 34), fill=navy)
    # заголовок
    t1 = "СВИДЕТЕЛЬСТВО О БРАКЕ" if married else "СВИДЕТЕЛЬСТВО ОБ ОТНОШЕНИЯХ"
    ft = _fit(d, t1, "bold", W - 640, 92)
    for dx, dy, col in ((5, 6, (170, 185, 200)), (0, 0, navy)):
        d.text((W / 2 + dx, 165 + dy), t1, font=ft, fill=col, anchor="mm")
    sub = "чат " + CHAT_TAG
    d.text((W / 2, 255), sub, font=_cert_font("text", 38), fill=(110, 120, 135), anchor="mm")
    # аватарки с венком
    for cx, av, nm in ((380, av_a, name_a), (1220, av_b, name_b)):
        cy, r = 470, 120
        for k in range(30):
            a = 2 * math.pi * k / 30
            col = [(240, 190, 205), (200, 190, 235), (250, 215, 170)][k % 3]
            x, y = cx + math.cos(a) * (r + 28), cy + math.sin(a) * (r + 28)
            d.ellipse((x - 17, y - 17, x + 17, y + 17), fill=col)
        d.ellipse((cx - r - 8, cy - r - 8, cx + r + 8, cy + r + 8), fill=(255, 255, 255))
        img.paste(_circle_avatar(av, r * 2, nm), (cx - r, cy - r), _circle_avatar(av, r * 2, nm))
        fn = _fit(d, nm[:28], "bold", 520, 52)
        d.text((cx, 665), nm[:28], font=fn, fill=navy, anchor="mm")
    # сердца посередине
    d.polygon(_heart_points(752, 475, 105), fill=pink)
    d.polygon(_heart_points(852, 467, 105), fill=red)
    for a, (x0, y0, x1, y1) in enumerate(((665, 385, 640, 360), (940, 385, 965, 360), (800, 360, 800, 325))):
        d.line((x0, y0, x1, y1), fill=navy, width=6)
    # линия сердцебиения
    y0 = 760
    d.line((100, y0, 700, y0), fill=(235, 120, 120), width=5)
    d.line((900, y0, 1500, y0), fill=(235, 120, 120), width=5)
    d.line((700, y0, 740, y0 - 25, 770, y0 + 20, 800, y0 - 60, 830, y0 + 35, 860, y0 - 15, 900, y0),
           fill=(235, 120, 120), width=5, joint="curve")
    # текст
    fb = _cert_font("text", 36)
    body = CERT_TEXT_MARRY if married else CERT_TEXT_REL
    y = 835
    for ln in _wrap(d, body, fb, W - 380):
        d.text((W / 2, y), ln, font=fb, fill=navy, anchor="mm")
        y += 52
    # дата, кольца, подпись
    d.text((560, 1005), date_str, font=_cert_font("bold", 44), fill=navy, anchor="mm")
    d.line((360, 1040, 760, 1040), fill=(235, 120, 120), width=4)
    d.text((560, 1080), "ДАТА", font=_cert_font("bold", 36), fill=navy, anchor="mm")
    if married:
        d.ellipse((930, 970, 1000, 1040), outline=(222, 170, 40), width=10)
        d.ellipse((970, 970, 1040, 1040), outline=(235, 195, 80), width=10)
    else:
        d.polygon(_heart_points(985, 1005, 70), fill=red)
    sig = Image.new("RGBA", (440, 120), (0, 0, 0, 0))
    ImageDraw.Draw(sig).text((20, 30), "Clavek", font=_cert_font("bold", 70), fill=navy)
    sig = sig.transform(sig.size, Image.AFFINE, (1, 0.45, -20, 0, 1, 0), Image.BICUBIC)
    img.paste(sig, (1180, 935), sig)
    d.line((1140, 1040, 1500, 1040), fill=(235, 120, 120), width=4)
    d.text((1320, 1080), "ПОДПИСЬ", font=_cert_font("bold", 36), fill=navy, anchor="mm")
    out = BytesIO()
    img.save(out, "JPEG", quality=90)
    out.seek(0)
    return out


async def _avatar_bytes(bot, uid):
    try:
        ph = await bot.get_user_profile_photos(uid, limit=1)
        if ph.total_count:
            f = await bot.get_file(ph.photos[0][-1].file_id)
            return bytes(await f.download_as_bytearray())
    except Exception as e:
        print("Аватарка недоступна:", repr(e)[:100])
    return None


async def send_certificate(bot, chat_id, row, married, reply_to=None, caption=None):
    """Свидетельство одним сообщением вместе с текстом (caption). True, если отправилось."""
    try:
        a, b = row["a"], row["b"]
        ts = row["married_at"] if married and row["married_at"] else row["since"]
        date_str = datetime.fromtimestamp(ts, timezone(timedelta(hours=TZ_HOURS))).strftime("%d.%m.%Y %H:%M")
        av_a, av_b = await _avatar_bytes(bot, a), await _avatar_bytes(bot, b)
        buf = await asyncio.to_thread(make_certificate, uname(a), uname(b), av_a, av_b, date_str, married)
        rp = ReplyParameters(message_id=reply_to, allow_sending_without_reply=True) if reply_to else None
        await bot.send_photo(chat_id, buf, reply_parameters=rp, parse_mode=HTML,
                             caption=caption or f"📜 {link(a, uname(a))} и {link(b, uname(b))}")
        return True
    except Exception as e:
        print("Свидетельство не отправилось:", repr(e)[:200])
        return False
