# -*- coding: utf-8 -*-
"""Премиум-эмодзи: при запуске читаем наборы и подменяем обычные эмодзи в исходящих HTML-сообщениях на
<tg-emoji>. Premium-пользователи видят анимированные, остальные — обычные. Если Telegram не принял — шлём как было."""

import logging
import re

from telegram import Bot
from telegram.error import BadRequest

log = logging.getLogger("premoji")
SETS = ["CuteBigPack", "whiteblackcore", "gay_nastyaa_emoji_4"]
MAP = {}                       # эмодзи -> custom_emoji_id
MAX_REPL = 80
# игровые поля, где значки несут смысл (жизни, патроны): там оставляем обычные эмодзи
SKIP = ("Дуэль на выстрелах", "Камень-ножницы-бумага", "Дуэль ·")
_TAG = re.compile(r"(<[^>]*>)")
_orig = {}


def _wrap(text):
    if not MAP or not text or "<tg-emoji" in text or any(m in text for m in SKIP):
        return text
    n = [0]

    def sub(seg):
        out = []
        i = 0
        while i < len(seg):
            ch = seg[i]
            nxt = seg[i + 1] if i + 1 < len(seg) else ""
            key = ch + nxt if nxt == "️" else ch
            cid = MAP.get(key) or MAP.get(ch)
            if cid and n[0] < MAX_REPL:
                n[0] += 1
                out.append(f'<tg-emoji emoji-id="{cid}">{key}</tg-emoji>')
                i += len(key)
            else:
                out.append(ch)
                i += 1
        return "".join(out)

    return "".join(p if p.startswith("<") else sub(p) for p in _TAG.split(text))


def _patch(name, field):
    fn = getattr(Bot, name)
    _orig[name] = fn

    async def wrapper(self, *a, **kw):
        if MAP and str(kw.get("parse_mode", "")).upper() == "HTML" and kw.get(field):
            new = dict(kw, **{field: _wrap(kw[field])})
            try:
                return await fn(self, *a, **new)
            except BadRequest as ex:
                log.warning("премиум-эмодзи не приняты (%s): %r", name, ex)
        return await fn(self, *a, **kw)

    wrapper.__name__ = name
    setattr(Bot, name, wrapper)


async def setup(bot):
    for s in SETS:
        try:
            st = await bot.get_sticker_set(s)
            for x in st.stickers:
                if x.emoji and x.custom_emoji_id:
                    MAP.setdefault(x.emoji, x.custom_emoji_id)
        except Exception as ex:
            log.warning("набор %s не прочитан: %r", s, ex)
    log.info("премиум-эмодзи: загружено %d", len(MAP))
    if MAP and not _orig:
        for name, field in (("send_message", "text"), ("edit_message_text", "text"), ("send_photo", "caption"),
                            ("send_animation", "caption"), ("edit_message_caption", "caption")):
            _patch(name, field)
