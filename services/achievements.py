# -*- coding: utf-8 -*-
"""Достижения: проверяются по уже накопленной статистике, награда небольшая."""

import io
import time

from database.db import db

db.executescript("""
CREATE TABLE IF NOT EXISTS ach(user_id INTEGER, key TEXT, ts REAL, PRIMARY KEY(user_id, key));
""")
db.commit()

ACH_XP = 20
ACH_PASS = 10

# ключ: (иконка, название, описание, функция(строка users, строка casino) -> bool)
ACHS = {
    "msg100": ("✉", "Болтун", "100 сообщений", lambda u, c: (u["total"] or 0) >= 100),
    "msg1000": ("✉", "Душа чата", "1000 сообщений", lambda u, c: (u["total"] or 0) >= 1000),
    "msg5000": ("✉", "Легенда чата", "5000 сообщений", lambda u, c: (u["total"] or 0) >= 5000),
    "job10": ("⚒", "Трудяга", "10 смен", lambda u, c: (u["job_shifts"] or 0) >= 10),
    "job100": ("⚒", "Работяга", "100 смен", lambda u, c: (u["job_shifts"] or 0) >= 100),
    "job200": ("⚒", "Ветеран труда", "200 смен", lambda u, c: (u["job_shifts"] or 0) >= 200),
    "duel1": ("⚔", "Первая кровь", "выиграть дуэль", lambda u, c: (u["duel_w"] or 0) >= 1),
    "duel10": ("⚔", "Дуэлянт", "10 побед в дуэлях", lambda u, c: (u["duel_w"] or 0) >= 10),
    "duel50": ("⚔", "Гроза чата", "50 побед в дуэлях", lambda u, c: (u["duel_w"] or 0) >= 50),
    "cas3000": ("♠", "Азартный", "3000 фишек", lambda u, c: c is not None and (c["best"] or 0) >= 3000),
    "cas15000": ("♠", "Король казино", "15000 фишек", lambda u, c: c is not None and (c["best"] or 0) >= 15000),
    "streak7": ("☀", "Неделя подряд", "7 дней активности", lambda u, c: (u["best_streak"] or 0) >= 7),
    "streak30": ("☀", "Месяц подряд", "30 дней активности", lambda u, c: (u["best_streak"] or 0) >= 30),
    "xp1000": ("★", "Опытный", "1000 опыта", lambda u, c: (u["xp"] or 0) >= 1000),
    "xp10000": ("★", "Мастер", "10000 опыта", lambda u, c: (u["xp"] or 0) >= 10000),
    "coin500": ("$", "Накопитель", "500 славКоин", lambda u, c: (u["coins"] or 0) >= 500),
    "coin5000": ("$", "Богач", "5000 славКоин", lambda u, c: (u["coins"] or 0) >= 5000),
    "house": ("⌂", "Домовладелец", "купить дом", lambda u, c: bool(u["house"])),
    "clan": ("⚑", "Свой в клане", "вступить в клан", lambda u, c: bool(u["clan_id"])),
    "vip": ("♛", "VIP", "активный VIP", lambda u, c: (u["vip_until"] or 0) > time.time()),
}

_last = {}


def have(uid):
    return {r["key"] for r in db.execute("SELECT key FROM ach WHERE user_id=?", (uid,))}


def check(uid, force=False):
    """Выдаёт новые достижения -> список (ключ, иконка, название)."""
    if not force and time.time() - _last.get(uid, 0) < 60:
        return []
    _last[uid] = time.time()
    u = db.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
    if not u:
        return []
    c = db.execute("SELECT * FROM casino WHERE user_id=?", (uid,)).fetchone()
    got, new = have(uid), []
    for k, (ic, name, desc, fn) in ACHS.items():
        if k in got:
            continue
        try:
            ok = fn(u, c)
        except Exception:
            ok = False
        if ok:
            db.execute("INSERT OR IGNORE INTO ach VALUES(?,?,?)", (uid, k, time.time()))
            new.append((k, ic, name))
    if new:
        db.commit()
        try:
            from services.battlepass import pass_add
            pass_add(uid, ACH_PASS * len(new))
        except Exception:
            pass
    return new


def showcase(name, uid):
    from PIL import Image, ImageDraw
    from services.monopoly_board import _font
    got = have(uid)
    keys = list(ACHS)
    cols = 3
    rows = (len(keys) + cols - 1) // cols
    W, H = 800, 150 + rows * 118
    im = Image.new("RGB", (W, H), (20, 22, 38))
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(30 - 14 * t), int(26 - 10 * t), int(56 - 24 * t)))
    d.rectangle((0, 0, W, 8), fill=(245, 195, 70))
    nm = "".join(ch for ch in (name or "") if ord(ch) < 0x2E80 and ch.isprintable())[:20].strip() or "Игрок"
    d.text((30, 26), "ДОСТИЖЕНИЯ", font=_font(36, True), fill=(255, 255, 255))
    d.text((30, 78), f"{nm}  ·  открыто {len(got)} из {len(keys)}", font=_font(20), fill=(190, 195, 215))
    d.rounded_rectangle((30, 112, W - 30, 124), 6, fill=(50, 54, 80))
    if got:
        d.rounded_rectangle((30, 112, 30 + max(12, int((W - 60) * len(got) / len(keys))), 124), 6, fill=(245, 195, 70))
    cw = (W - 60 - (cols - 1) * 12) // cols
    for i, k in enumerate(keys):
        r, c = divmod(i, cols)
        x, y = 30 + c * (cw + 12), 144 + r * 118
        ic, title, desc, _ = ACHS[k]
        on = k in got
        d.rounded_rectangle((x, y, x + cw, y + 106), 14, fill=(44, 40, 20) if on else (30, 33, 52),
                            outline=(245, 195, 70) if on else (62, 68, 100), width=2)
        d.ellipse((x + 10, y + 14, x + 70, y + 74), fill=(245, 195, 70) if on else (52, 56, 84))
        d.text((x + 40, y + 44), ic, font=_font(32, True), fill=(60, 40, 0) if on else (110, 116, 150), anchor="mm")
        d.text((x + 80, y + 30), title[:16], font=_font(17, True), fill=(255, 255, 255) if on else (140, 146, 170), anchor="lm")
        d.text((x + 80, y + 54), desc[:20], font=_font(12), fill=(210, 200, 150) if on else (110, 116, 150), anchor="lm")
        d.text((x + 80, y + 82), "получено" if on else "закрыто", font=_font(12, True), fill=(120, 220, 150) if on else (110, 116, 150), anchor="lm")
    buf = io.BytesIO()
    im.quantize(colors=64).save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
