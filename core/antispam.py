# -*- coding: utf-8 -*-
"""Защита от накрутки: проверка осмысленности сообщения, кулдауны."""

import re
import time

from config import MIN_LETTERS
from content.data import KEYBOARD_ROWS


# ============================ ЗАЩИТА ОТ НАКРУТКИ ============================
def is_meaningful(text):
    """Отсеивает набор букв вроде «ададад», «дадвдвд», «fafafa», «asdfgh»."""
    t = text.lower().replace("ё", "е")
    letters = re.sub(r"[^a-zа-я]", "", t)
    if len(letters) < MIN_LETTERS:
        return False
    if len(set(letters)) < 4:
        return False
    for p in (1, 2, 3):                       # повтор одного куска: адад, абвабв
        if letters == (letters[:p] * (len(letters) // p + 1))[:len(letters)]:
            return False
    for word in re.findall(r"[a-zа-я]+", t):
        if len(word) >= 7 and len(set(word)) / len(word) < 0.45:
            return False
    for row in KEYBOARD_ROWS:                 # «фывап», «asdfg», «ghjkl»
        for i in range(len(row) - 4):
            chunk = row[i:i + 5]
            if chunk in letters or chunk[::-1] in letters:
                return False
    if len(letters) >= 6:
        vowels = sum(letters.count(v) for v in "аеёиоуыэюяaeiouy")
        ratio = vowels / len(letters)
        if ratio < 0.15 or ratio > 0.75:
            return False
    return True


last_ts = {}


last_texts = {}


cooldowns = {}


def cooldown(key, sec):
    t = time.time()
    if t - cooldowns.get(key, 0) < sec:
        return False
    cooldowns[key] = t
    return True
