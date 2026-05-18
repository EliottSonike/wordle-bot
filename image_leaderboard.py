import asyncio
import io
from PIL import Image, ImageDraw, ImageFont
import aiohttp
import discord

# ── Colors ────────────────────────────────────────────────────────
BG       = (43,  45,  49)
BG_ALT   = (52,  55,  60)
TEXT     = (220, 221, 222)
SUB      = (148, 155, 164)
GREEN    = (83,  141, 78)
GOLD     = (255, 200,   0)
SILVER   = (192, 192, 192)
BRONZE   = (180, 120,  60)
RANK_CLR = {1: GOLD, 2: SILVER, 3: BRONZE}

# ── Layout ────────────────────────────────────────────────────────
W         = 480
LEFT_BAR  = 5
PAD       = 16
HEADER_H  = 68
PODIUM_H  = 230
ROW_H     = 66
FOOTER_H  = 32


def _font(size, bold=False):
    for path in [
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",
        f"/usr/share/fonts/truetype/liberation/LiberationSans-{'Bold' if bold else 'Regular'}.ttf",
        f"/usr/share/fonts/truetype/freefont/FreeSans{'Bold' if bold else ''}.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


async def _circle(session, url, size):
    try:
        async with session.get(url) as r:
            data = await r.read()
        av = Image.open(io.BytesIO(data)).convert("RGBA").resize((size, size), Image.LANCZOS)
    except Exception:
        av = Image.new("RGBA", (size, size), (80, 80, 80, 255))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(av, mask=mask)
    return out


def _cx_text(draw, cx, y, text, font, color):
    bb = draw.textbbox((0, 0), text, font=font)
    draw.text((cx - (bb[2] - bb[0]) // 2, y), text, font=font, fill=color)


def _truncate(draw, text, font, max_w):
    while draw.textbbox((0, 0), text, font=font)[2] > max_w and len(text) > 2:
        text = text[:-1]
    return text if draw.textbbox((0, 0), text, font=font)[2] <= max_w else text + "…"


async def build_leaderboard_image(rows, week_start: str, bot: discord.Client) -> discord.File:
    total_wordles = rows[0]["total_wordles"] if rows else 0
    H = HEADER_H + PODIUM_H + 2 + len(rows) * ROW_H + FOOTER_H

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    fT  = _font(17, bold=True)   # title
    fS  = _font(11)              # subtitle
    fN  = _font(15, bold=True)   # player name
    fSt = _font(12)              # stats
    fR  = _font(22, bold=True)   # rank big
    fP  = _font(14, bold=True)   # points label
    fBl = _font(13, bold=True)   # podium block label

    # ── Left green bar ─────────────────────────────────────────────
    draw.rectangle([(0, 0), (LEFT_BAR, H)], fill=GREEN)

    # ── Header ─────────────────────────────────────────────────────
    draw.text((PAD + LEFT_BAR, 13), f"Classement Wordle — {week_start}", font=fT, fill=TEXT)
    draw.text((PAD + LEFT_BAR, 42), f"{total_wordles} Wordle(s) · Moins de points = meilleur · Absent/Échec = +7", font=fS, fill=SUB)
    draw.line([(LEFT_BAR, HEADER_H - 1), (W, HEADER_H - 1)], fill=(60, 62, 67))

    # ── Fetch users ─────────────────────────────────────────────────
    uinfo: dict[str, tuple[str, str | None]] = {}
    for row in rows:
        try:
            u = await bot.fetch_user(int(row["user_id"]))
            url = str(u.display_avatar.replace(size=128).url) if u.display_avatar else None
            uinfo[row["user_id"]] = (u.display_name, url)
        except Exception:
            uinfo[row["user_id"]] = (row["username"], None)

    async with aiohttp.ClientSession() as session:
        av64: dict[str, Image.Image] = {}
        av40: dict[str, Image.Image] = {}
        lg_tasks = {uid: _circle(session, info[1], 64) for uid, info in uinfo.items() if info[1]}
        sm_tasks = {uid: _circle(session, info[1], 40) for uid, info in uinfo.items() if info[1]}
        for uid, r in zip(lg_tasks, await asyncio.gather(*lg_tasks.values(), return_exceptions=True)):
            if not isinstance(r, Exception):
                av64[uid] = r
        for uid, r in zip(sm_tasks, await asyncio.gather(*sm_tasks.values(), return_exceptions=True)):
            if not isinstance(r, Exception):
                av40[uid] = r

    # ── Podium (2nd left · 1st center · 3rd right) ─────────────────
    PT = HEADER_H
    slot_w = (W - LEFT_BAR) // 3
    order = [1, 0, 2]        # 2nd, 1st, 3rd
    blk_h = {0: 100, 1: 75, 2: 55}   # block heights (slot index)
    av_sz = {0: 64, 1: 56, 2: 48}

    for si, ri in enumerate(order):
        if ri >= len(rows):
            continue
        row = rows[ri]
        uid = row["user_id"]
        rc  = RANK_CLR.get(ri + 1, SUB)
        bh  = blk_h[si]
        avs = av_sz[si]
        cx  = LEFT_BAR + slot_w * si + slot_w // 2

        # Block
        bx0 = LEFT_BAR + slot_w * si + 8
        bx1 = LEFT_BAR + slot_w * (si + 1) - 8
        by0 = PT + PODIUM_H - bh
        draw.rectangle([(bx0, by0), (bx1, PT + PODIUM_H)], fill=tuple(max(c - 170, 0) for c in rc))
        draw.rectangle([(bx0, by0), (bx1, PT + PODIUM_H)], outline=rc, width=2)
        _cx_text(draw, cx, by0 + 6, f"{ri + 1}{'er' if ri == 0 else 'ème'}", fBl, rc)

        # Avatar
        av_y = by0 - avs - 6
        av_x = cx - avs // 2
        src  = (av64.get(uid) or av40.get(uid))
        if src:
            src_r = src.resize((avs, avs), Image.LANCZOS)
            img.paste(src_r, (av_x, av_y), src_r)
        else:
            draw.ellipse([(av_x, av_y), (av_x + avs, av_y + avs)], fill=(80, 80, 80))

        # Name
        name = uinfo.get(uid, (row["username"], None))[0]
        name = _truncate(draw, name, fP, slot_w - 12)
        _cx_text(draw, cx, av_y - 22, name, fP, TEXT)

        # Points
        _cx_text(draw, cx, av_y - 42, f"{row['total_points']} pts", fBl, rc)

    # Divider
    dy = PT + PODIUM_H
    draw.line([(LEFT_BAR, dy), (W, dy)], fill=GREEN, width=2)

    # ── Ranked list ─────────────────────────────────────────────────
    medals = {0: "1.", 1: "2.", 2: "3."}
    for i, row in enumerate(rows):
        y   = dy + 2 + i * ROW_H
        uid = row["user_id"]
        rc  = RANK_CLR.get(i + 1, SUB)

        if i % 2 == 1:
            draw.rectangle([(LEFT_BAR, y), (W, y + ROW_H)], fill=BG_ALT)

        x = PAD + LEFT_BAR

        # Rank
        rt = medals.get(i, f"{i + 1}.")
        bb = draw.textbbox((0, 0), rt, font=fSt)
        draw.text((x, y + (ROW_H - (bb[3] - bb[1])) // 2), rt, font=fSt, fill=rc)
        x += 30

        # Avatar 40px
        av_y2 = y + (ROW_H - 40) // 2
        if uid in av40:
            img.paste(av40[uid], (x, av_y2), av40[uid])
        else:
            draw.ellipse([(x, av_y2), (x + 40, av_y2 + 40)], fill=(80, 80, 80))
        x += 48

        # Name
        name = uinfo.get(uid, (row["username"], None))[0]
        draw.text((x, y + 9), name, font=fN, fill=TEXT)

        # Stats
        best = str(row["best"]) if row["best"] < 7 else "X"
        missed = row["total_wordles"] - row["played"]
        stats = f"{row['total_points']} pts · {row['played']}/{total_wordles} · meilleur {best}/6"
        if missed:
            stats += f" · {missed} absent(s)"
        draw.text((x, y + 34), stats, font=fSt, fill=SUB)

        # Points right
        pts = f"{row['total_points']}"
        bb2 = draw.textbbox((0, 0), pts, font=fR)
        draw.text((W - PAD - (bb2[2] - bb2[0]), y + (ROW_H - (bb2[3] - bb2[1])) // 2), pts, font=fR, fill=rc)

    # ── Footer ─────────────────────────────────────────────────────
    fy = dy + 2 + len(rows) * ROW_H
    draw.line([(LEFT_BAR, fy), (W, fy)], fill=(60, 62, 67))
    draw.text((PAD + LEFT_BAR, fy + 9), "WordleRankingBot", font=fS, fill=SUB)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return discord.File(buf, filename="classement.png")
