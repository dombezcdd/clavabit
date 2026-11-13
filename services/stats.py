# -*- coding: utf-8 -*-
"""Топы за день, неделю и месяц."""

from datetime import timedelta

from config import FMT
from core.utils import esc, now
from database.db import db


# ============================ ТОПЫ ============================
def top_rows(start, end, limit=10):
    return db.execute(
        "SELECT d.user_id AS uid, u.name AS name, u.tag AS tag, SUM(d.cnt) AS c "
        "FROM daily d JOIN users u ON u.user_id=d.user_id "
        "WHERE d.day>=? AND d.day<=? GROUP BY d.user_id HAVING c>0 "
        "ORDER BY c DESC LIMIT ?", (start, end, limit)).fetchall()


def fmt_top(rows):
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, r in enumerate(rows):
        m = medals[i] if i < 3 else f"{i + 1}."
        t = f"<b>{esc(r['tag'])}</b> " if r["tag"] else ""
        lines.append(f"{m} {t}{esc(r['name'])} — {r['c']}")
    return "\n".join(lines)


def week_start():
    return (now() - timedelta(days=6)).strftime(FMT)


def month_start():
    return now().replace(day=1).strftime(FMT)
