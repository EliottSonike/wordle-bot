import asyncio
import io
from PIL import Image, ImageDraw, ImageFont
import aiohttp
import discord

# ── Colors (Discord dark mode) ───────────────────────────────────
BG        = (43,  45,  49)
ROW_ALT   = (50,  53,  58)
TEXT      = (220, 221, 222)
SUB       = (148, 155, 164)
GREEN     = (83,  141, 78)
GOLD      = (255, 200, 0)
SILVER    = (192, 192, 192)
BRONZE    = (180, 120, 60)

RANK_COLORS = {1: GOLD, 2: SILVER, 3: BRONZE}

MEDALS = {1: "1.", 2: "2.", 3: "3."}

# ── Layout ───────────────────────────────────────────────────────
W         = 680
AV        = 32          # avatar diameter
ROW_H     = 52
HEADER_H  = 70
FOOTER_H  = 30
PAD       = 18
LEFT_BAR  = 4           # green left border like Discord embeds


def _font(size, bold=False):
    candidates = [
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",
        f"/usr/share/fonts/truetype/liberation/LiberationSans-{'Bold' if bold else 'Regular'}.ttf",
        f"/usr/share/fonts/truetype/freefont/FreeSans{'Bold' if bold else ''}.ttf",
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


async def _circle_avatar(session, url, size):
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


async def build_leaderboard_image(rows, week_start: str, bot: discord.Client) -> discord.File:
    total_wordles = rows[0]["total_wordles"] if rows else 0
    H = HEADER_H + len(rows) * ROW_H + FOOTER_H

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    f_title = _font(17, bold=True)
    f_sub   = _font(12)
    f_name  = _font(14, bold=True)
    f_stats = _font(13)

    # ── Green left bar (like Discord embed) ──────────────────────
    draw.rectangle([(0, 0), (LEFT_BAR, H)], fill=GREEN)

    # ── Header ───────────────────────────────────────────────────
    draw.text((PAD + LEFT_BAR, 14), f"🏆 Classement Wordle — semaine du {week_start}", font=f_title, fill=TEXT)
    draw.text((PAD + LEFT_BAR, 42), f"{total_wordles} Wordle(s) cette semaine  ·  Le moins de points gagne  ·  Absent / Échec = +7 pts", font=f_sub, fill=SUB)
    draw.line([(LEFT_BAR, HEADER_H - 1), (W, HEADER_H - 1)], fill=(60, 62, 67), width=1)

    # ── Fetch avatars + usernames ─────────────────────────────────
    user_info: dict[str, tuple[str, str | None]] = {}  # uid -> (display_name, avatar_url)
    for row in rows:
        try:
            user = await bot.fetch_user(int(row["user_id"]))
            av_url = str(user.display_avatar.replace(size=64).url) if user.display_avatar else None
            user_info[row["user_id"]] = (user.display_name, av_url)
        except Exception:
            user_info[row["user_id"]] = (row["username"], None)

    avatars: dict[str, Image.Image] = {}
    async with aiohttp.ClientSession() as session:
        tasks = {uid: _circle_avatar(session, info[1], AV) for uid, info in user_info.items() if info[1]}
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for uid, result in zip(tasks.keys(), results):
            if not isinstance(result, Exception):
                avatars[uid] = result

    # ── Rows ──────────────────────────────────────────────────────
    medals = ["🥇", "🥈", "🥉"]
    for i, row in enumerate(rows):
        y    = HEADER_H + i * ROW_H
        rank = i + 1
        rc   = RANK_COLORS.get(rank, SUB)

        if i % 2 == 1:
            draw.rectangle([(LEFT_BAR, y), (W, y + ROW_H)], fill=ROW_ALT)

        x = PAD + LEFT_BAR

        # Rank label
        rank_label = medals[i] if i < 3 else f"{rank}."
        bb = draw.textbbox((0, 0), rank_label, font=f_stats)
        rw = bb[2] - bb[0]
        draw.text((x, y + (ROW_H - (bb[3] - bb[1])) // 2), rank_label, font=f_stats, fill=rc)
        x += max(rw, 28) + 8

        # Avatar
        av_y = y + (ROW_H - AV) // 2
        if row["user_id"] in avatars:
            img.paste(avatars[row["user_id"]], (x, av_y), avatars[row["user_id"]])
        else:
            draw.ellipse([(x, av_y), (x + AV, av_y + AV)], fill=(80, 80, 80))
        x += AV + 10

        # Name
        name = user_info.get(row["user_id"], (row["username"], None))[0]
        draw.text((x, y + 9), name, font=f_name, fill=TEXT)

        # Stats (below name)
        best_str = str(row["best"]) if row["best"] < 7 else "X"
        missed   = row["total_wordles"] - row["played"]
        stats    = f"{row['total_points']} pts  ·  {row['played']}/{total_wordles} joués  ·  meilleur {best_str}/6"
        if missed:
            stats += f"  ·  {missed} absent(s)"
        draw.text((x, y + 30), stats, font=f_stats, fill=SUB)

    # ── Footer ────────────────────────────────────────────────────
    fy = HEADER_H + len(rows) * ROW_H
    draw.line([(LEFT_BAR, fy), (W, fy)], fill=(60, 62, 67), width=1)
    draw.text((PAD + LEFT_BAR, fy + 9), "WordleRankingBot", font=f_sub, fill=SUB)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return discord.File(buf, filename="classement.png")
