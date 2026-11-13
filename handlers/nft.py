# -*- coding: utf-8 -*-
"""Просмотр NFT-подарков по ссылке: сборка гифки."""

import asyncio
import html
import os
import re

from telegram import LinkPreviewOptions

from config import BASE, CHAT_TAG, HTML
from core.antispam import cooldown
from core.utils import disp, esc, link
from services.certificate import _cert_font


NFT_RE = re.compile(r"(?:https?://)?t\.me/nft/([A-Za-z0-9]+)-(\d+)", re.I)


def _pattern_tile(card_bytes, S):
    """Берёт готовую карточку подарка (фон + узор + статичная модель), вырезает центр
    с моделью и заливает его цветом фона. Остаётся фон с узором."""
    from io import BytesIO
    from PIL import Image, ImageDraw, ImageFilter, ImageStat
    im = Image.open(BytesIO(card_bytes)).convert("RGB")
    w, h = im.size
    m = int(min(w, h) * 0.03)                      # срезаем рамку
    im = im.crop((m, m, w - m, h - m)).resize((S, S), Image.LANCZOS)
    cx = cy = S / 2
    rx, ry = S * 0.37, S * 0.35                    # зона модели
    band = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(band)
    d.ellipse((cx - rx * 1.22, cy - ry * 1.22, cx + rx * 1.22, cy + ry * 1.22), fill=255)
    d.ellipse((cx - rx * 1.02, cy - ry * 1.02, cx + rx * 1.02, cy + ry * 1.02), fill=0)
    med = tuple(int(v) for v in ImageStat.Stat(im, band).median)
    light = tuple(min(255, int(v * 1.06 + 4)) for v in med)
    fill = Image.new("RGB", (S, S), med)
    glow = Image.radial_gradient("L").resize((S, S)).point(lambda v: 255 - min(255, v * 2))
    fill = Image.composite(Image.new("RGB", (S, S), light), fill, glow.point(lambda v: v // 3))
    hole = Image.new("L", (S, S), 0)
    ImageDraw.Draw(hole).ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
    hole = hole.filter(ImageFilter.GaussianBlur(S * 0.03))
    return Image.composite(fill, im, hole)


NFT_LOCK = asyncio.Lock()


def _cards_to_gif(items, out):
    """items — список (lottie_json_str, bg). Рисует карточки как в подборках NFT:
    скруглённые плитки с мягким свечением на тёмном фоне. Одна — по центру, несколько — сеткой."""
    from PIL import Image, ImageDraw
    from rlottie_python import LottieAnimation
    k = len(items)
    anims = [LottieAnimation.from_data(it[0]) for it in items]
    totals = [max(1, a.lottie_animation_get_totalframe()) for a in anims]
    fps = anims[0].lottie_animation_get_framerate() or 30
    FOOT = 56
    if k == 1:
        S, W, H, cols, gap = 380, 800, 450, 1, 0
        H += FOOT
    else:
        S, gap, cols = 250, 16, min(3, k)
        rows = (k + cols - 1) // cols
        W, H = cols * S + (cols + 1) * gap, rows * S + (rows + 1) * gap + FOOT
    base = Image.new("RGB", (W, H), (22, 19, 21))
    try:
        bd = ImageDraw.Draw(base)
        ft = _cert_font("bold", 30)
        tw = bd.textlength(CHAT_TAG, font=ft)
        bd.text(((W - tw) / 2, H - FOOT + 10), CHAT_TAG, font=ft, fill=(235, 232, 236))
    except Exception as e:
        print("NFT: подпись не нарисована:", repr(e)[:100])
    # фон каждой плитки: радиальное свечение + скругление
    tiles = []
    rad = Image.radial_gradient("L").resize((S, S))              # 0 центр -> 255 край
    rmask = Image.new("L", (S * 3, S * 3), 0)
    ImageDraw.Draw(rmask).rounded_rectangle((0, 0, S * 3 - 1, S * 3 - 1), radius=int(S * 3 * 0.24), fill=255)
    rmask = rmask.resize((S, S), Image.LANCZOS)
    for _, bg, card in items:
        light = tuple(min(255, int(v * 1.18 + 12)) for v in bg)
        edge = tuple(int(v * 0.82) for v in bg)
        tile = Image.composite(Image.new("RGB", (S, S), edge), Image.new("RGB", (S, S), light),
                               rad.point(lambda v: int(max(0, v - 40) * 255 / 215)))
        if card:
            try:
                tile = _pattern_tile(card, S) or tile
            except Exception as e:
                print("NFT: узор не получился:", repr(e)[:150])
        tiles.append(tile)
    pos = []
    for i in range(k):
        r, c = divmod(i, cols)
        if k == 1:
            pos.append(((W - S) // 2, (H - FOOT - S) // 2))
        else:
            pos.append((gap + c * (S + gap), gap + r * (S + gap)))
    n = max(totals)
    step = max(1, n // 55)
    gs = int(S * 0.8)
    frames = []
    for i in range(0, n, step):
        canvas = base.copy()
        for j, a in enumerate(anims):
            fr = a.render_pillow_frame(frame_num=i % totals[j], width=gs, height=gs).convert("RGBA")
            t = tiles[j].convert("RGBA")
            t.alpha_composite(fr, ((S - gs) // 2, (S - gs) // 2))
            canvas.paste(t.convert("RGB"), pos[j], rmask)
        frames.append(canvas.convert("P", palette=Image.ADAPTIVE, colors=256, dither=Image.NONE))
    frames[0].save(out, save_all=True, append_images=frames[1:], loop=0,
                   duration=int(1000 / max(fps, 1) * step), disposal=2, optimize=False)


async def fetch_nft_source(name, num):
    """Возвращает ('lottie', json_str, bg) | ('file', path, None) | None."""
    import gzip
    import httpx
    slug = f"{name}-{num}".lower()
    page = f"https://t.me/nft/{name}-{num}"
    cands, bg, card = [], (45, 45, 55), None
    async with httpx.AsyncClient(timeout=25, follow_redirects=True,
                                 headers={"User-Agent": "Mozilla/5.0"}) as c:
        for suffix in (".large.jpg", ".medium.jpg", ".webp"):
            try:
                rr = await c.get(f"https://nft.fragment.com/gift/{slug}{suffix}")
                if rr.status_code == 200 and len(rr.content) > 2000:
                    card = rr.content
                    break
            except Exception:
                pass
        try:
            r = await c.get(page)
            txt = html.unescape(r.text)
            cands += re.findall(r'https?://[^\s"\'<>\\)]+\.(?:tgs|json|webm|mp4|gif)(?:\?[^\s"\'<>\\)]*)?', txt)
            mm = re.search(r'og:image"\s+content="([^"]+)"', txt)
            if mm:
                try:
                    from io import BytesIO
                    from PIL import Image
                    raw_img = (await c.get(mm.group(1))).content
                    im = Image.open(BytesIO(raw_img)).convert("RGB")
                    bg = im.getpixel((6, 6))
                    if card is None:
                        card = raw_img
                except Exception:
                    pass
        except Exception as e:
            print("NFT: страница не открылась:", e)
        cands += [f"https://nft.fragment.com/gift/{slug}.lottie.json",
                  f"https://nft.fragment.com/gift/{slug}.tgs"]
        seen = set()
        for u in cands:
            if u in seen:
                continue
            seen.add(u)
            try:
                r = await c.get(u)
                if r.status_code != 200 or not r.content:
                    continue
                path = u.split("?")[0].lower()
                if path.endswith((".mp4", ".gif")):
                    out = os.path.join(BASE, f"nft_{slug}" + path[-4:])
                    open(out, "wb").write(r.content)
                    return ("file", out, None)
                if path.endswith(".webm"):
                    continue
                raw = r.content
                if raw[:2] == b"\x1f\x8b":
                    raw = gzip.decompress(raw)
                return ("lottie", raw.decode("utf-8"), tuple(bg), card)
            except Exception as e:
                print("NFT: источник не подошёл:", u, "->", repr(e)[:200])
    return None


async def _nft_build(update, found, tmp):
    srcs = [await fetch_nft_source(n, u) for n, u in found]
    srcs = [s for s in srcs if s]
    lot = [(s[1], s[2], s[3]) for s in srcs if s[0] == "lottie"]
    files = [s[1] for s in srcs if s[0] == "file"]
    tmp += files
    if lot:
        gif = os.path.join(BASE, f"nft_{update.effective_message.message_id}.gif")
        tmp.append(gif)
        async with NFT_LOCK:
            await asyncio.to_thread(_cards_to_gif, lot, gif)
        return gif
    return files[0] if files else None


async def handle_nft(update, context, text):
    found = []
    for mm in NFT_RE.finditer(text):
        key = (mm.group(1), mm.group(2))
        if key not in found:
            found.append(key)
    found = found[:3]
    if not cooldown(("nft", update.effective_user.id), 20):
        return await update.effective_message.reply_text("Подожди немного перед следующей NFT-ссылкой ⏳")
    caps = []
    for name, num in found:
        caps.append(f"🎁 <b>{esc(re.sub(r'(?<!^)(?=[A-Z])', ' ', name))}</b> #{esc(num)}")
    caption = ("\n".join(caps) + "\n" +
               f"Запросил: {link(update.effective_user.id, disp(update.effective_user))}")
    gif, tmp = None, []
    try:
        await context.bot.send_chat_action(update.effective_chat.id, "upload_video")
        gif = await asyncio.wait_for(_nft_build(update, found, tmp), 120)
    except ImportError:
        print("NFT: не установлены rlottie-python/Pillow. Выполни: py -m pip install rlottie-python Pillow")
    except Exception as e:
        print("NFT: ошибка:", repr(e)[:200])
        gif = None
    if gif:
        try:
            with open(gif, "rb") as f:
                await update.effective_message.reply_animation(f, caption=caption, parse_mode=HTML)
            return
        except Exception as e:
            print("NFT: не удалось отправить gif:", repr(e)[:200])
        finally:
            for p in tmp:
                try:
                    os.remove(p)
                except OSError:
                    pass
    for p in tmp:
        try:
            os.remove(p)
        except OSError:
            pass
    links = "\n".join(f"<a href=\"https://t.me/nft/{n}-{u}\">Открыть NFT {esc(n)} #{esc(u)}</a>" for n, u in found)
    await update.effective_message.reply_text(
        f"{caption}\n{links}", parse_mode=HTML,
        link_preview_options=LinkPreviewOptions(
            url=f"https://t.me/nft/{found[0][0]}-{found[0][1]}", prefer_large_media=True, show_above_text=True))
