# -*- coding: utf-8 -*-
"""Пасс сезона: 30 дней, 30 уровней, очки за квесты. Пасс личный (у каждого свой прогресс)."""

import io
import time

from database.db import db

SEASON_DAYS = 30
LEVELS = 30
PTS_PER_LEVEL = 100
PTS_QUEST, PTS_ALL, PTS_VIP_QUEST = 20, 40, 30

db.executescript("""
CREATE TABLE IF NOT EXISTS bpass(
  user_id INTEGER, season INTEGER, pts INTEGER DEFAULT 0, claimed INTEGER DEFAULT 0,
  PRIMARY KEY(user_id, season));
""")
db.commit()


def season_id(ts=None):
    return int((ts or time.time()) // 86400) // SEASON_DAYS


def season_left_days():
    end = (season_id() + 1) * SEASON_DAYS * 86400
    return max(0, int((end - time.time()) // 86400))


def reward(lvl):
    """-> (тип, число, подпись)"""
    if lvl == 30:
        return ("vip", 3, "👑 VIP на 3 дня")
    if lvl % 10 == 0:
        return ("chips", 1000, "💵 1000 славБакс")
    if lvl % 5 == 0:
        return ("coins", 3, "💰 3 славКоин")
    if lvl % 3 == 0:
        return ("chips", 250, "💵 250 славБакс")
    if lvl % 2 == 0:
        return ("xp", 40, "✨ 40 опыта")
    return ("coins", 1, "💰 1 славКоин")


def _row(uid):
    s = season_id()
    r = db.execute("SELECT * FROM bpass WHERE user_id=? AND season=?", (uid, s)).fetchone()
    if not r:
        db.execute("INSERT OR IGNORE INTO bpass(user_id,season) VALUES(?,?)", (uid, s))
        db.commit()
        r = db.execute("SELECT * FROM bpass WHERE user_id=? AND season=?", (uid, s)).fetchone()
    return r


def pass_add(uid, pts):
    r = _row(uid)
    db.execute("UPDATE bpass SET pts=pts+? WHERE user_id=? AND season=?", (pts, uid, r["season"]))
    db.commit()


def state(uid):
    """-> (очки, уровень, набор полученных уровней)"""
    r = _row(uid)
    lvl = min(LEVELS, r["pts"] // PTS_PER_LEVEL)
    got = {i for i in range(1, LEVELS + 1) if r["claimed"] >> (i - 1) & 1}
    return r["pts"], lvl, got


def claim_all(uid):
    """Выдать все доступные награды -> список подписей"""
    from services.economy import give_coins
    from services.xp import give_xp
    from services.casino import chips_add
    pts, lvl, got = state(uid)
    s = season_id()
    out, mask = [], 0
    for i in range(1, lvl + 1):
        if i in got:
            continue
        kind, n, label = reward(i)
        if kind == "coins":
            give_coins(uid, n)
        elif kind == "chips":
            chips_add(uid, n)
        elif kind == "xp":
            give_xp(uid, n)
        elif kind == "vip":
            base = max(db.execute("SELECT COALESCE(vip_until,0) v FROM users WHERE user_id=?", (uid,)).fetchone()["v"], time.time())
            db.execute("UPDATE users SET vip_until=? WHERE user_id=?", (base + n * 86400, uid))
            db.commit()
        mask |= 1 << (i - 1)
        out.append(f"ур. {i}: {label}")
    if mask:
        db.execute("UPDATE bpass SET claimed=claimed|? WHERE user_id=? AND season=?", (mask, uid, s))
        db.commit()
    return out


def pass_card(name, uid):
    from PIL import Image, ImageDraw
    from services.monopoly_board import _font
    pts, lvl, got = state(uid)
    W, H = 900, 560
    im = Image.new("RGB", (W, H), (18, 20, 32))
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(30 - 12 * t), int(26 - 8 * t), int(58 - 20 * t)))
    d.rectangle((0, 0, W, 10), fill=(240, 190, 60))
    d.text((36, 26), "ПАСС СЕЗОНА", font=_font(40, True), fill=(255, 255, 255))
    nm = (name or "Игрок")[:24]
    d.text((36, 76), f"{nm}  ·  до конца сезона {season_left_days()} дн.", font=_font(20), fill=(190, 195, 215))
    # общий прогресс
    pct = min(1.0, pts / (LEVELS * PTS_PER_LEVEL))
    d.rounded_rectangle((36, 118, W - 36, 140), 11, fill=(50, 54, 80))
    if pct > 0:
        d.rounded_rectangle((36, 118, 36 + max(22, int((W - 72) * pct)), 140), 11, fill=(240, 190, 60))
    nxt = "все уровни пройдены" if lvl >= LEVELS else f"до {lvl + 1} уровня ещё {(lvl + 1) * PTS_PER_LEVEL - pts} очков"
    d.text((36, 148), f"Уровень {lvl} из {LEVELS}  ·  {pts} очков  ·  {nxt}", font=_font(20, True), fill=(255, 255, 255))
    # сетка уровней 10 x 3
    cw, ch = 82, 98
    x0, y0 = 36, 196
    for i in range(1, LEVELS + 1):
        r_, c_ = divmod(i - 1, 10)
        x, y = x0 + c_ * (cw + 4), y0 + r_ * (ch + 14)
        if i in got:
            fill, ol, tc = (36, 110, 70), (80, 200, 130), (255, 255, 255)
        elif i <= lvl:
            fill, ol, tc = (120, 90, 20), (240, 190, 60), (255, 255, 255)
        else:
            fill, ol, tc = (38, 42, 64), (70, 76, 108), (140, 146, 170)
        d.rounded_rectangle((x, y, x + cw, y + ch), 12, fill=fill, outline=ol, width=2)
        d.text((x + 8, y + 6), str(i), font=_font(22, True), fill=tc)
        kind, n, _ = reward(i)
        short = {"coins": f"{n} кн", "chips": f"{n} фш", "xp": f"{n} оп", "vip": "VIP"}[kind]
        d.text((x + 8, y + 40), short, font=_font(15, True), fill=tc)
        mark = "✓" if i in got else ("!" if i <= lvl else "")
        if mark:
            d.text((x + cw - 22, y + 6), mark, font=_font(20, True), fill=ol)
    d.text((36, H - 44), "Очки: квест +20, все квесты дня +40, VIP-квест +30. 100 очков = уровень", font=_font(17), fill=(170, 175, 200))
    buf = io.BytesIO()
    im.quantize(colors=64).save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
