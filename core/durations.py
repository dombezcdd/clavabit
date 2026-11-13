# -*- coding: utf-8 -*-
"""Разбор и вывод длительностей (мут и т.п.)."""

import re


UNITS = {"м": 1, "мин": 1, "минут": 1, "минуту": 1, "минуты": 1, "m": 1, "min": 1, "mins": 1,
         "ч": 60, "час": 60, "часа": 60, "часов": 60, "h": 60, "hour": 60, "hours": 60,
         "д": 1440, "дн": 1440, "день": 1440, "дня": 1440, "дней": 1440,
         "d": 1440, "day": 1440, "days": 1440}


def parse_duration(args):
    """('30','мин') / ('2ч') / ('10','min') -> (минуты, сколько слов съели) или (None, 0)."""
    if not args:
        return None, 0
    m = re.fullmatch(r"(\d{1,6})([a-zа-я]*)", args[0].lower())
    if not m:
        return None, 0
    n, unit, used = int(m.group(1)), m.group(2), 1
    if not unit and len(args) > 1 and args[1].lower() in UNITS:
        unit, used = args[1].lower(), 2
    if unit and unit not in UNITS:
        return None, 0
    return n * (UNITS[unit] if unit else 1), used


def fmt_minutes(m):
    m = max(int(m), 0)
    d, rem = divmod(m, 1440)
    h, mi = divmod(rem, 60)
    parts = []
    if d:
        parts.append(f"{d} д.")
    if h:
        parts.append(f"{h} ч.")
    if mi or not parts:
        parts.append(f"{mi} мин.")
    return " ".join(parts)
