import asyncio
import io
from PIL import Image, ImageDraw, ImageFont
import aiohttp
import discord

# ── Colors ────────────────────────────────────────────────────────
BG       = (43,  45,  49)
BG_ALT   = (50,  53,  58)
TEXT     = (220, 221, 222)
SUB      = (148, 155, 164)
GREEN    = (83,  141, 78)
GOLD     = (255, 200,  0)
SILVER   = (192, 192, 192)
BRONZE   = (180, 120,  60)
DARK     = (30,  31,  34)

RANK_CLR = {1: GOLD, 2: SILVER, 3: BRONZE}

# ── Layout ────────────────────────────────────────────────────────
W          = 860
HEADER_H   = 70
PODIUM_H   = 260
DIVIDER_H  = 2
ROW_H      = 65
FOOTER_H   = 36
PAD        = 22
LEFT_BAR   = 5


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


def _centered_text(draw, cx, y, text, font, color):
    bb = draw.textbbox((0, 0), text, font=font)
    draw.text((cx - (bb[2] - bb[0]) // 2, y), text, font=font, fill=color)


async def build_leaderboard_image(rows, week_start: str, bot: discord.Client) -> discord.File:
    total_wordles = rows[0]["total_wordles"] if rows else 0
    n_rows = len(rows)
    H = HEADER_H + PODIUM_H + DIVIDER_H + n_rows * ROW_H + FOOTER_H

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    f_h1    = _font(20, bold=True)
    f_sub   = _font(13)
    f_name  = _font(15, bold=True)
    f_stats = _font(13)
    f_rank  = _font(32, bold=True)
    f_pts   = _font(15, bold=True)
    f_small = _font(13)

    # ── Green left bar ────────────────────────────────────────────
    draw.rectangle([(0, 0), (LEFT_BAR, H)], fill=GREEN)

    # ── Header ────────────────────────────────────────────────────
    draw.text((PAD + LEFT_BAR, 15), f"🏆  Classement Wordle — semaine du {week_start}", font=f_h1, fill=TEXT)
    draw.text((PAD + LEFT_BAR, 46), f"{total_wordles} Wordle(s) cette semaine  ·  Le moins de points gagne  ·  Absent / Échec = +7 pts", font=f_sub, fill=SUB)
    draw.line([(LEFT_BAR, HEADER_H - 1), (W, HEADER_H - 1)], fill=(60, 62, 67), width=1)

    # ── Fetch user info ────────────────────────────────────────────
    user_info: dict[str, tuple[str, str | None]] = {}
    for row in rows:
        try:
            user = await bot.fetch_user(int(row["user_id"]))
            av_url = str(user.display_avatar.replace(size=128).url) if user.display_avatar else None
            user_info[row["user_id"]] = (user.display_name, av_url)
        except Exception:
            user_info[row["user_id"]] = (row["username"], None)

    async with aiohttp.ClientSession() as session:
        tasks_lg = {}   # large avatars for podium
        tasks_sm = {}   # small avatars for list
        for row in rows[:3]:
            uid = row["user_id"]
            url = user_info[uid][1]
            if url:
                tasks_lg[uid] = _circle(session, url, 72)
        for row in rows:
            uid = row["user_id"]
            url = user_info[uid][1]
            if url:
                tasks_sm[uid] = _circle(session, url, 42)

        av_lg = {}
        res_lg = await asyncio.gather(*tasks_lg.values(), return_exceptions=True)
        for uid, r in zip(tasks_lg.keys(), res_lg):
            if not isinstance(r, Exception):
                av_lg[uid] = r

        av_sm = {}
        res_sm = await asyncio.gather(*tasks_sm.values(), return_exceptions=True)
        for uid, r in zip(tasks_sm.keys(), res_sm):
            if not isinstance(r, Exception):
                av_sm[uid] = r

    # ── Podium ────────────────────────────────────────────────────
    podium_top = HEADER_H
    # Order: 2nd (left), 1st (center), 3rd (right)
    podium_order = [1, 0, 2] if len(rows) >= 3 else list(range(len(rows)))
    block_heights = {0: 110, 1: 80, 2: 60}   # 1st tallest
    av_sizes      = {0: 72,  1: 60, 2: 56}
    slot_w = (W - LEFT_BAR) // 3
    slot_labels = {0: "1er", 1: "2ème", 2: "3ème"}

    for slot_pos, row_idx in enumerate(podium_order):
        if row_idx >= len(rows):
            continue
        row = rows[row_idx]
        uid  = row["user_id"]
        rc   = RANK_CLR.get(row_idx + 1, SUB)
        bh   = block_heights[slot_pos]
        avs  = av_sizes[slot_pos]
        cx   = LEFT_BAR + slot_w * slot_pos + slot_w // 2

        # Block at the bottom of podium area
        block_y = podium_top + PODIUM_H - bh
        draw.rectangle([(LEFT_BAR + slot_w * slot_pos + 10, block_y),
                         (LEFT_BAR + slot_w * (slot_pos + 1) - 10, podium_top + PODIUM_H)],
                        fill=(*rc, 40) if False else tuple(max(c - 160, 0) for c in rc) + (255,))
        # Block border
        draw.rectangle([(LEFT_BAR + slot_w * slot_pos + 10, block_y),
                         (LEFT_BAR + slot_w * (slot_pos + 1) - 10, podium_top + PODIUM_H)],
                        outline=rc, width=2)

        # Rank number inside block
        _centered_text(draw, cx, block_y + 8, slot_labels[slot_pos], f_small, rc)

        # Avatar above block
        av_x = cx - avs // 2
        av_y = block_y - avs - 8
        src  = av_lg.get(uid) or av_sm.get(uid)
        if src:
            src_resized = src.resize((avs, avs), Image.LANCZOS)
            img.paste(src_resized, (av_x, av_y), src_resized)
        else:
            draw.ellipse([(av_x, av_y), (av_x + avs, av_y + avs)], fill=(80, 80, 80))

        # Name
        name = user_info.get(uid, (row["username"], None))[0]
        bb = draw.textbbox((0, 0), name, font=f_name)
        nw = bb[2] - bb[0]
        max_w = slot_w - 20
        display_name = name
        while draw.textbbox((0, 0), display_name, font=f_name)[2] - draw.textbbox((0, 0), display_name, font=f_name)[0] > max_w and len(display_name) > 3:
            display_name = display_name[:-1]
        if display_name != name:
            display_name += "…"
        _centered_text(draw, cx, av_y - 22, display_name, f_name, TEXT)

        # Points
        pts_str = f"{row['total_points']} pts"
        _centered_text(draw, cx, av_y - 44, pts_str, f_pts, rc)

    # Divider between podium and list
    div_y = HEADER_H + PODIUM_H
    draw.line([(LEFT_BAR, div_y), (W, div_y)], fill=GREEN, width=DIVIDER_H)

    # ── Full ranked list ──────────────────────────────────────────
    for i, row in enumerate(rows):
        y   = div_y + DIVIDER_H + i * ROW_H
        uid = row["user_id"]
        rc  = RANK_CLR.get(i + 1, SUB)

        if i % 2 == 1:
            draw.rectangle([(LEFT_BAR, y), (W, y + ROW_H)], fill=BG_ALT)

        x = PAD + LEFT_BAR

        # Rank
        medals = {0: "🥇", 1: "🥈", 2: "🥉"}
        rank_txt = medals.get(i, f"{i + 1}.")
        bb = draw.textbbox((0, 0), rank_txt, font=f_stats)
        draw.text((x, y + (ROW_H - (bb[3] - bb[1])) // 2), rank_txt, font=f_stats, fill=rc)
        x += 36

        # Avatar
        av_y2 = y + (ROW_H - 42) // 2
        if uid in av_sm:
            img.paste(av_sm[uid], (x, av_y2), av_sm[uid])
        else:
            draw.ellipse([(x, av_y2), (x + 42, av_y2 + 42)], fill=(80, 80, 80))
        x += 52

        # Name + stats
        name = user_info.get(uid, (row["username"], None))[0]
        draw.text((x, y + 10), name, font=f_name, fill=TEXT)
        best_str = str(row["best"]) if row["best"] < 7 else "X"
        missed   = row["total_wordles"] - row["played"]
        stats    = f"{row['total_points']} pts  ·  {row['played']}/{total_wordles} joués  ·  meilleur {best_str}/6"
        if missed:
            stats += f"  ·  {missed} absent(s)"
        draw.text((x, y + 35), stats, font=f_stats, fill=SUB)

        # Points right
        pts_txt = f"{row['total_points']}"
        bb2 = draw.textbbox((0, 0), pts_txt, font=f_pts)
        draw.text((W - PAD - (bb2[2] - bb2[0]), y + (ROW_H - (bb2[3] - bb2[1])) // 2), pts_txt, font=f_pts, fill=rc)

    # ── Footer ────────────────────────────────────────────────────
    fy = div_y + DIVIDER_H + n_rows * ROW_H
    draw.line([(LEFT_BAR, fy), (W, fy)], fill=(60, 62, 67), width=1)
    draw.text((PAD + LEFT_BAR, fy + 10), "WordleRankingBot", font=f_sub, fill=SUB)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return discord.File(buf, filename="classement.png")
