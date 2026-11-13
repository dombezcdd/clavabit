# -*- coding: utf-8 -*-
"""Картинки и гифки для rp и событий: БД, локальные файлы, Giphy, nekos."""

import os
import random

from telegram import ReplyParameters

from config import BASE, HTML, NOPREV, RP_DIR
from database.db import db


_rp_cats = None


RP_UA = {"User-Agent": "clavekbot/1.0 (telegram chat bot)"}


async def rp_gif_url(category):
    """Случайная гифка категории с nekos.best или None."""
    import httpx
    global _rp_cats
    try:
        async with httpx.AsyncClient(timeout=10, headers=RP_UA) as c:
            if _rp_cats is None:
                r = await c.get("https://nekos.best/api/v2/endpoints")
                data = r.json()
                _rp_cats = data if isinstance(data, dict) else {}
            if _rp_cats:
                info = _rp_cats.get(category)
                if info is None:
                    return None
                if isinstance(info, dict) and info.get("format") not in (None, "gif"):
                    return None
            r = await c.get(f"https://nekos.best/api/v2/{category}")
            return r.json()["results"][0]["url"]
    except Exception as e:
        print("RP: не удалось получить гифку:", repr(e)[:150])
        return None


def local_rp_files(action):
    """Свои файлы из папки rp: «обнять.gif», «обнять_2.jpg», «отн_поцелуй_1.mp4»."""
    stem = action.replace(":", "_")
    out = []
    for folder in (os.path.join(BASE, RP_DIR), BASE):     # папка rp или рядом с bot.py
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        for fn in names:
            base, ext = os.path.splitext(fn)
            if ext.lower() not in (".gif", ".mp4", ".jpg", ".jpeg", ".png", ".webp"):
                continue
            if base == stem or base.startswith(stem + "_"):
                out.append(os.path.join(folder, fn))
    random.shuffle(out)
    return out


async def send_with_pic(bot, chat_id, text, actions, reply_to=None, api_cat=None,
                        markup=None, gif_query=None):
    """Картинка к сообщению. Порядок: свои картинки из базы -> файлы из папки rp ->
    гифка с nekos.best -> просто текст."""
    rp = ReplyParameters(message_id=reply_to, allow_sending_without_reply=True) if reply_to else None

    async def send(kind, media):
        kw = dict(caption=text, parse_mode=HTML, reply_parameters=rp, reply_markup=markup)
        if kind == "animation":
            return await bot.send_animation(chat_id, media, **kw)
        if kind == "video":
            return await bot.send_video(chat_id, media, **kw)
        if kind == "photo":
            return await bot.send_photo(chat_id, media, **kw)
        return await bot.send_document(chat_id, media, **kw)

    for action in actions:
        rows = db.execute("SELECT kind, file_id FROM rp_media WHERE action=?", (action,)).fetchall()
        if rows:
            r = random.choice(rows)
            try:
                return await send(r["kind"], r["file_id"])
            except Exception as e:
                print("Картинка из базы не отправилась:", repr(e)[:150])
    for action in actions:
        for p in local_rp_files(action):
            ext = os.path.splitext(p)[1].lower()
            try:
                with open(p, "rb") as f:
                    return await send("animation" if ext in (".gif", ".mp4") else "photo", f)
            except Exception as e:
                print("Файл из rp не отправился:", p, repr(e)[:150])
    if gif_query:
        url = await giphy_url(gif_query)
        if url:
            try:
                return await send("animation", url)
            except Exception as e:
                print("Giphy: гифка не ушла:", repr(e)[:150])
    if api_cat:
        url = await rp_gif_url(api_cat)
        if url:
            try:
                return await send("animation", url)
            except Exception as e:
                print("RP: гифка по ссылке не ушла:", repr(e)[:150])
                try:
                    import httpx
                    from io import BytesIO
                    async with httpx.AsyncClient(timeout=20, headers=RP_UA) as c:
                        data = (await c.get(url)).content
                    return await send("animation", BytesIO(data))
                except Exception as e2:
                    print("RP: и файлом не ушла:", repr(e2)[:150])
    return await bot.send_message(chat_id, text, parse_mode=HTML, reply_markup=markup,
                                  link_preview_options=NOPREV, reply_parameters=rp)


# ---------- мини-игры на работах ----------
GIPHY_KEY = os.environ.get("GIPHY_KEY", "")      # бесплатный ключ: developers.giphy.com


async def giphy_url(q):
    if not GIPHY_KEY:
        return None
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get("https://api.giphy.com/v1/gifs/search",
                            params={"api_key": GIPHY_KEY, "q": q, "limit": 25, "rating": "g"})
        data = r.json().get("data") or []
        if data:
            im = random.choice(data)["images"]
            return (im.get("downsized_medium") or im.get("original") or {}).get("url")
    except Exception as e:
        print("Giphy:", repr(e)[:120])
    return None
