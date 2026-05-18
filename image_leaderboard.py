import asyncio
import io
from PIL import Image, ImageDraw, ImageFont
import aiohttp
import discord

# ── Colors ──────────────────────────────────────────────────────
BG      = (18,  18,  19)
BG_ALT  = (28,  28,  30)
HDR_BG  = (26,  26,  27)
TEXT    = (255, 255, 255)
SUB     = (129, 131, 132)
GREEN   = (83,  141, 78)
RANK_COLORS = {1: (255, 200, 0), 2: (192, 192, 192), 3: (180, 120, 60)}

# ── Layout ──────────────────────────────────────────────────────
W          = 700
AVATAR_SZ  = 46
ROW_H      = 62
HEADER_H   = 78
FOOTER_H   = 34
PAD        = 16
RANK_W     = 36
AV_GAP     = 12


def _font(size, bold=False):
    candidates = [
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",
        f"/usr/share/fonts/truetype/liberation/LiberationSans-{'Bold' if bold else 'Regular'}.ttf",
        f"/usr/share/fonts/truetype/freefont/FreeSans{'Bold' if bold else ''}.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


async def _fetch_avatar(session, url, size):
    try:
        async with session.get(url) as r:
            data = await r.read()
        img = Image.open(io.BytesIO(data)).convert("RGBA").resize((size, size), Image.LANCZOS)
    except Exception:
        img = Image.new("RGBA", (size, size), (70, 70, 70, 255))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, mask=mask)
    return out


async def build_leaderboard_image(rows, week_start: str, guild: discord.Guild) -> discord.File:
    total_wordles = rows[0]["total_wordles"] if rows else 0
    H = HEADER_H + len(rows) * ROW_H + FOOTER_H

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    f_title = _font(19, bold=True)
    f_sub   = _font(12)
    f_name  = _font(15, bold=True)
    f_stats = _font(12)
    f_rank  = _font(17, bold=True)
    f_pts   = _font(18, bold=True)

    # ── Header ──────────────────────────────────────────────────
    draw.rectangle([(0, 0), (W, HEADER_H)], fill=HDR_BG)
    draw.rectangle([(0, HEADER_H - 3), (W, HEADER_H)], fill=GREEN)
    draw.text((PAD, 15), f"Classement Wordle — {week_start}", font=f_title, fill=TEXT)
    draw.text((PAD, 46), f"{total_wordles} Wordle(s) cette semaine  ·  Le moins de points gagne  ·  Absent / Échec = +7 pts", font=f_sub, fill=SUB)

    # ── Download avatars ────────────────────────────────────────
    avatars: dict[str, Image.Image] = {}
    async with aiohttp.ClientSession() as session:
        uid_to_url = {}
        for row in rows:
            member = guild.get_member(int(row["user_id"])) if guild else None
            if member and member.display_avatar:
                uid_to_url[row["user_id"]] = str(member.display_avatar.replace(size=64).url)
        results = await asyncio.gather(
            *[_fetch_avatar(session, url, AVATAR_SZ) for url in uid_to_url.values()],
            return_exceptions=True,
        )
        for uid, result in zip(uid_to_url.keys(), results):
            if not isinstance(result, Exception):
                avatars[uid] = result

    # ── Rows ────────────────────────────────────────────────────
    for i, row in enumerate(rows):
        y    = HEADER_H + i * ROW_H
        rank = i + 1
        rc   = RANK_COLORS.get(rank, SUB)
        draw.rectangle([(0, y), (W, y + ROW_H)], fill=BG_ALT if i % 2 == 0 else BG)

        # Rank
        rank_txt = str(rank)
        bb = draw.textbbox((0, 0), rank_txt, font=f_rank)
        rw = bb[2] - bb[0]
        draw.text((PAD + (RANK_W - rw) // 2, y + (ROW_H - (bb[3] - bb[1])) // 2), rank_txt, font=f_rank, fill=rc)

        # Avatar
        av_x = PAD + RANK_W + AV_GAP
        av_y = y + (ROW_H - AVATAR_SZ) // 2
        if row["user_id"] in avatars:
            img.paste(avatars[row["user_id"]], (av_x, av_y), avatars[row["user_id"]])
        else:
            draw.ellipse([(av_x, av_y), (av_x + AVATAR_SZ, av_y + AVATAR_SZ)], fill=(70, 70, 70))

        # Name + stats
        tx = av_x + AVATAR_SZ + AV_GAP
        member = guild.get_member(int(row["user_id"])) if guild else None
        name = member.display_name if member else row["username"]
        missed = row["total_wordles"] - row["played"]
        best_str = str(row["best"]) if row["best"] < 7 else "X"
        stats = f"{row['played']}/{total_wordles} joués  ·  meilleur {best_str}/6"
        if missed:
            stats += f"  ·  {missed} absent(s)"

        draw.text((tx, y + 11), name,  font=f_name,  fill=TEXT)
        draw.text((tx, y + 34), stats, font=f_stats, fill=SUB)

        # Points (right side)
        pts_txt = f"{row['total_points']} pts"
        bb2 = draw.textbbox((0, 0), pts_txt, font=f_pts)
        pw = bb2[2] - bb2[0]
        ph = bb2[3] - bb2[1]
        draw.text((W - PAD - pw, y + (ROW_H - ph) // 2), pts_txt, font=f_pts, fill=rc)

    # ── Footer ──────────────────────────────────────────────────
    fy = HEADER_H + len(rows) * ROW_H
    draw.rectangle([(0, fy), (W, H)], fill=HDR_BG)
    draw.rectangle([(0, fy), (W, fy + 2)], fill=GREEN)
    draw.text((PAD, fy + 10), "WordleRankingBot", font=f_sub, fill=SUB)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return discord.File(buf, filename="classement.png")
