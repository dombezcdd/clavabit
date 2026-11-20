# -*- coding: utf-8 -*-
"""Профиль пользователя и расчёт его показателей."""

from datetime import timedelta

from config import CHAT_ID, FMT
from core.logger import log
from core.ranks import rank_of_id, rank_title
from core.utils import esc, fmt_when, level_need, level_of, now, old_title, title_of, today
from database.db import db
from services.stats import month_start, week_start


async def build_profile(bot, row):
    uid = row["user_id"]
    try:
        cm = await bot.get_chat_member(CHAT_ID, uid)
        role = "Телеграм-админ этого чата" if cm.status in ("administrator", "creator") \
            else "участник"
    except Exception:
        role = "участник"
    lvl = level_of(row["xp"])
    nxt = ""
    if lvl < 100:
        nxt = f" (до {lvl + 1} ур.: {level_need(lvl + 1) - row['xp']} оп.)"
    ot, days = old_title(row["first_seen"])
    d = today()
    wk, mo = week_start(), month_start()

    def s(a, b):
        r = db.execute("SELECT COALESCE(SUM(cnt),0) c FROM daily WHERE user_id=? AND day>=? AND day<=?",
                       (uid, a, b)).fetchone()
        return r["c"]

    name = f"@{row['username']}" if row["username"] else esc(row["name"])
    tag = f"<b>{esc(row['tag'])}</b>\n" if (row["tag"] or "").strip() else ""
    st = row["streak"] if row["last_day"] in (d, (now() - timedelta(days=1)).strftime(FMT)) else 0
    ar = rank_of_id(uid)
    adm = f"🛡 {rank_title(ar)} (админ-ранг {ar})\n" if ar else ""
    extra = "".join(f"{lab}: {esc(row[col])}\n" for lab, col in (("🏷 Звание", "ztitle"), ("📝 Ник", "nick"), ("🏙 Город", "city"))
                    if row[col])
    try:
        from services.vip import is_vip
        crown = " 👑 VIP" if is_vip(uid) else ""
    except Exception:
        crown = ""
    return (
        f"👤 Это пользователь {name}{crown}\n{tag}{extra}"
        f"👨🏻‍🔧 {role}\n{adm}\n"
        f"▫️ [{lvl}] Ранг: {esc(title_of(lvl))}{nxt}\n"
        f"🕰 Олдство: {ot} ({days} дн. в чате)\n\n"
        f"Репутация: ✨ {row['rep']} | ➕ {row['rep_given']}\n\n"
        f"1. Первое появление: ❗️ {fmt_when(row['first_seen'])}\n"
        f"2. Последний актив: {fmt_when(row['last_seen'])}\n"
        f"3. Актив (д|н|м|весь): {s(d, d)} | {s(wk, d)} | {s(mo, d)} | {row['total']}\n"
        f"4. Серия дней: 🔥 {st} (рекорд {row['best_streak']})\n"
        f"5. Очки: 🧠 {row['quiz_pts']} | 🎮 {row['game_pts']} | 📜 {row['quest_pts']}"
    )


async def profile_score(bot, row):
    uid = row["user_id"]
    parts = {}
    try:
        ph = await bot.get_user_profile_photos(uid, limit=1)
        parts["аватарка"] = 20 if ph.total_count > 0 else 0
    except Exception:
        parts["аватарка"] = 0
    bio = ""
    try:
        ch = await bot.get_chat(uid)
        bio = (getattr(ch, "bio", "") or "").strip()
    except Exception:
        pass
    parts["описание"] = 15 if len(bio) >= 10 else (5 if bio else 0)
    parts["юзернейм"] = 10 if row["username"] else 0
    parts["уровень"] = round(level_of(row["xp"]) * 0.5)
    parts["репутация"] = min(row["rep"] * 2, 30)
    parts["олдство"] = min(old_title(row["first_seen"])[1] // 15, 24)
    parts["тег"] = 10 if (row["tag"] or "").strip() else 0
    nft, regular = await count_gifts(bot, uid)
    parts["NFT-подарки"] = min(nft * 4, 40)
    parts["подарки"] = min(regular, 10)
    return parts


async def count_gifts(bot, uid):
    """(уникальные NFT, обычные) среди подарков, которые человек показывает в профиле.
    Если у человека подарки скрыты или метод недоступен — (0, 0)."""
    fn = getattr(bot, "get_user_gifts", None)
    if fn is None:
        return 0, 0
    try:
        res = await fn(user_id=uid, limit=100)
    except Exception as e:
        log.warning("get_user_gifts: %s", e)
        return 0, 0
    nft = regular = 0
    for g in getattr(res, "gifts", None) or []:
        if getattr(g, "type", "") == "unique" or hasattr(g, "gift") and hasattr(g.gift, "model"):
            nft += 1
        else:
            regular += 1
    total = getattr(res, "total_count", 0) or 0
    if total > nft + regular:      # список обрезан лимитом, остальное считаем обычными
        regular += total - nft - regular
    return nft, regular


def _col(row, name):
    try:
        return row[name]
    except (IndexError, KeyError):
        return ""


async def profile_view(bot, row):
    """-> (карточка BytesIO или None, подпись HTML)"""
    import asyncio

    from services.clans import clan_of
    from services.economy import coins_of
    from services.jobs import JOBS, career_title
    from services.profile_card import profile_card
    from services.relations import is_married, pair_of, partner_of, uname

    uid = row["user_id"]
    d = today()
    wk, mo = week_start(), month_start()

    def s(a, b):
        r = db.execute("SELECT COALESCE(SUM(cnt),0) c FROM daily WHERE user_id=? AND day>=? AND day<=?", (uid, a, b)).fetchone()
        return r["c"]

    lvl = level_of(row["xp"])
    ot, days = old_title(row["first_seen"])
    st = row["streak"] if row["last_day"] in (d, (now() - timedelta(days=1)).strftime(FMT)) else 0
    ar = rank_of_id(uid)
    try:
        cm = await bot.get_chat_member(CHAT_ID, uid)
        role = "админ чата" if cm.status in ("administrator", "creator") else "участник"
    except Exception:
        role = "участник"
    if ar:
        role = f"{rank_title(ar)} (ранг {ar})"
    pct, left = 1.0, "максимальный уровень"
    if lvl < 100:
        a, b = level_need(lvl), level_need(lvl + 1)
        pct = max(0.0, min(1.0, (row["xp"] - a) / max(1, b - a)))
        left = f"до {lvl + 1} уровня ещё {b - row['xp']} опыта"
    name = row["name"] or (("@" + row["username"]) if row["username"] else str(uid))
    sub = " · ".join(x for x in (("@" + row["username"]) if row["username"] else "", _col(row, "ztitle"), role) if x)
    job = ""
    if row["job"] in JOBS:
        job = f"{JOBS[row['job']][0]}, {career_title(row['job_shifts'] or 0)}"
    cl = clan_of(uid)
    pr = pair_of(uid)
    love = ""
    if pr and is_married(pr):
        love = "в браке: " + uname(partner_of(pr, uid))
    elif pr:
        love = "пара: " + uname(partner_of(pr, uid))
    foot = [job, ("клан " + cl["name"]) if cl else "", love]
    card = None
    try:
        av = None
        try:
            ph = await asyncio.wait_for(bot.get_user_profile_photos(uid, limit=1), 4)
            if ph.total_count:
                f = await asyncio.wait_for(ph.photos[0][0].get_file(), 4)
                av = bytes(await asyncio.wait_for(f.download_as_bytearray(), 6))
        except Exception:
            av = None
        from services.vip import is_vip
        card = profile_card(dict(vip=is_vip(uid), uid=uid, name=name, sub=sub or "участник", level=lvl, title=title_of(lvl), xp_pct=pct,
                                 xp_left=left, tiles=[("славКоин", coins_of(uid)), ("Репутация", row["rep"]),
                                                      ("Серия дней", st), ("В чате", f"{days} дн.")], foot=foot), av)
    except Exception:
        log.exception("profile_card")
    return card, await build_profile(bot, row)
