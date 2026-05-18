import asyncio
import io
from PIL import Image, ImageDraw, ImageFont
import aiohttp
import discord

# ── Colors ────────────────────────────────────────────────────────
BG       = (22,  22,  26)
BLOCK    = (32,  32,  38)
BLOCK_S  = (26,  26,  30)   # slightly darker for side shadow
GOLD     = (255, 196,  0)
SILVER   = (210, 210, 210)
BRONZE   = (188, 120,  50)
WHITE    = (240, 240, 240)
GRAY     = (160, 160, 165)
RANK_CLR = {0: GOLD, 1: SILVER, 2: BRONZE}

W, H = 620, 420


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
        av = Image.new("RGBA", (size, size), (70, 70, 75, 255))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    ring = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ring.paste(av, mask=mask)
    return ring


def _cx(draw, cx, y, text, font, color):
    bb = draw.textbbox((0, 0), text, font=font)
    draw.text((cx - (bb[2] - bb[0]) // 2, y), text, font=font, fill=color)


async def build_podium_image(rows, week_start: str, bot: discord.Client) -> discord.File:
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)

    fTitle  = _font(16)
    fName   = _font(17, bold=True)
    fPts    = _font(14)
    fRank   = _font(52, bold=True)

    # Title
    title = f"Classement Wordle — {week_start}"
    _cx(d, W // 2, 14, title, fTitle, GRAY)

    # Slot order: 2nd (left), 1st (center), 3rd (right)
    order = [1, 0, 2]

    # Block geometry
    BW     = 170           # block width
    GAP    = 12            # gap between blocks
    BOTTOM = H - 30        # bottom of all blocks
    BH     = [180, 230, 140]   # block heights: 2nd, 1st, 3rd
    AV_SZ  = 82
    AV_GAP = 12

    start_x = (W - 3 * BW - 2 * GAP) // 2

    # Fetch user info
    uinfo: dict[str, tuple[str, str | None]] = {}
    for row in rows[:3]:
        try:
            u = await bot.fetch_user(int(row["user_id"]))
            url = str(u.display_avatar.replace(size=128).url) if u.display_avatar else None
            uinfo[row["user_id"]] = (u.display_name, url)
        except Exception:
            uinfo[row["user_id"]] = (row["username"], None)

    async with aiohttp.ClientSession() as session:
        av_tasks = {}
        for row in rows[:3]:
            uid = row["user_id"]
            if uid in uinfo and uinfo[uid][1]:
                av_tasks[uid] = _circle(session, uinfo[uid][1], AV_SZ)
        results = await asyncio.gather(*av_tasks.values(), return_exceptions=True)
        avatars = {}
        for uid, r in zip(av_tasks.keys(), results):
            if not isinstance(r, Exception):
                avatars[uid] = r

    for slot, ri in enumerate(order):
        if ri >= len(rows):
            continue

        row = rows[ri]
        uid = row["user_id"]
        rc  = RANK_CLR[ri]
        bh  = BH[slot]
        bx  = start_x + slot * (BW + GAP)
        by  = BOTTOM - bh
        cx  = bx + BW // 2

        # ── Block body ────────────────────────────────────────────
        d.rectangle([(bx, by), (bx + BW, BOTTOM)], fill=BLOCK)

        # Gold/silver/bronze top cap (thick line + slight 3D)
        cap_h = 10
        d.rectangle([(bx, by), (bx + BW, by + cap_h)], fill=rc)
        # Side shadow (right side darker)
        d.rectangle([(bx + BW - 5, by + cap_h), (bx + BW, BOTTOM)], fill=BLOCK_S)

        # Rank number inside block
        _cx(d, cx - 3, by + bh // 2 - 35, str(ri + 1), fRank, rc)

        # Points inside block
        pts_str = f"{row['total_points']} pts"
        _cx(d, cx, by + bh // 2 + 22, pts_str, fPts, GRAY)

        # ── Avatar above block ─────────────────────────────────────
        av_top = by - AV_GAP - AV_SZ
        av_left = cx - AV_SZ // 2

        # Avatar ring
        ring_sz = AV_SZ + 6
        ring_img = Image.new("RGBA", (ring_sz, ring_sz), (0, 0, 0, 0))
        ImageDraw.Draw(ring_img).ellipse((0, 0, ring_sz - 1, ring_sz - 1), fill=(*rc, 255))
        img.paste(ring_img, (av_left - 3, av_top - 3),
                  ring_img.split()[3] if ring_img.mode == "RGBA" else None)

        if uid in avatars:
            img.paste(avatars[uid], (av_left, av_top), avatars[uid])
        else:
            d.ellipse([(av_left, av_top), (av_left + AV_SZ, av_top + AV_SZ)], fill=(70, 70, 75))

        # ── Name above avatar ─────────────────────────────────────
        name = uinfo.get(uid, (row["username"], None))[0]
        if len(name) > 16:
            name = name[:15] + "…"
        name_y = av_top - 30
        _cx(d, cx, name_y, name, fName, WHITE)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return discord.File(buf, filename="podium.png")
