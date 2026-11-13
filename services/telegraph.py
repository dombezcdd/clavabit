# -*- coding: utf-8 -*-
"""Публикация статьи с командами в Telegraph."""

import json

from config import CHAT_TAG
from content.doc import DOC_SECTIONS, DOC_TITLE, DOC_VER
from database.state import state_get, state_set


def doc_nodes():
    nodes = [{"tag": "p", "children": [f"Все команды бота {CHAT_TAG}. Писать можно словами, без слеша, "
                                       "если не указано иное. «@юз» можно заменить ответом на сообщение."]}]
    for title, items in DOC_SECTIONS:
        nodes.append({"tag": "h3", "children": [title]})
        nodes.append({"tag": "ul", "children": [
            {"tag": "li", "children": [{"tag": "b", "children": [cmd]}, " — " + desc]} for cmd, desc in items]})
    nodes.append({"tag": "p", "children": [{"tag": "i", "children": ["Статья обновляется ботом автоматически."]}]})
    return nodes


async def telegraph_sync(force=False):
    """Создаёт или обновляет статью. -> ссылка или None."""
    import httpx
    if not force and state_get("tgph_ver") == DOC_VER and state_get("tgph_url"):
        return state_get("tgph_url")
    content = json.dumps(doc_nodes(), ensure_ascii=False)
    async with httpx.AsyncClient(timeout=25) as c:
        token = state_get("tgph_token")
        if not token:
            r = (await c.post("https://api.telegra.ph/createAccount", data={
                "short_name": "clavekbot", "author_name": CHAT_TAG})).json()
            if not r.get("ok"):
                raise RuntimeError(f"createAccount: {r}")
            token = r["result"]["access_token"]
            state_set("tgph_token", token)
        path = state_get("tgph_path")
        if path:
            r = (await c.post("https://api.telegra.ph/editPage", data={
                "access_token": token, "path": path, "title": DOC_TITLE, "content": content,
                "author_name": CHAT_TAG})).json()
            if not r.get("ok"):
                path = None          # статью не нашли, создадим заново
        if not path:
            r = (await c.post("https://api.telegra.ph/createPage", data={
                "access_token": token, "title": DOC_TITLE, "content": content,
                "author_name": CHAT_TAG})).json()
        if not r.get("ok"):
            raise RuntimeError(f"telegraph: {r}")
        state_set("tgph_path", r["result"]["path"])
        state_set("tgph_url", r["result"]["url"])
        state_set("tgph_ver", DOC_VER)
        return r["result"]["url"]
