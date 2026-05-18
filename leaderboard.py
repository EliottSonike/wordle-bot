import discord
from database import get_weekly_rows

WORDLE_GREEN = 0x538D4E


def _name(row, guild):
    if guild:
        member = guild.get_member(int(row["user_id"]))
        if member:
            return member.mention
    return f"**{row['username']}**"


def _display_name(row, guild):
    if guild:
        m = guild.get_member(int(row["user_id"]))
        if m:
            return m.display_name
    return row["username"]


def _podium(rows, guild):
    """Draws an ASCII podium for the top 3."""
    order  = [1, 0, 2]   # 2nd  1st  3rd (left, center, right)
    labels = ["2ème", "1er", "3ème"]
    inner  = [3, 5, 2]   # inner height of each block

    names = []
    pts   = []
    for ri in order:
        if ri < len(rows):
            n = _display_name(rows[ri], guild)
            names.append(n[:14])
            pts.append(f"{rows[ri]['total_points']} pts")
        else:
            names.append("—")
            pts.append("")

    cw = max(max(len(n) for n in names), max(len(p) for p in pts),
             max(len(l) for l in labels)) + 2

    def box(label, p, h):
        b  = ["┌" + "─" * cw + "┐"]
        b += ["│" + label.center(cw) + "│"]
        b += ["│" + " " * cw + "│"] * (h - 1)
        b += ["│" + p.center(cw) + "│"]
        b += ["└" + "─" * cw + "┘"]
        return b

    cols = [box(l, p, h) for l, p, h in zip(labels, pts, inner)]
    bh   = [len(c) for c in cols]
    top  = max(bh)

    padded = []
    for i, (col, h) in enumerate(zip(cols, bh)):
        pad = top - h
        empty = " " * (cw + 2)
        above = [empty] * pad
        if pad:
            above[-1] = names[i].center(cw + 2)
        padded.append(above + col)

    # add name row above tallest column too
    for i, p in enumerate(padded):
        if len(p) == top:
            padded[i] = [names[i].center(cw + 2)] + p

    max_h = max(len(p) for p in padded)
    for p in padded:
        while len(p) < max_h:
            p.insert(0, " " * (cw + 2))

    lines = [" ".join(col[r] for col in padded) for r in range(max_h)]
    return "```\n" + "\n".join(lines) + "\n```"


def build_leaderboard(guild_id: str, week_start: str, guild: discord.Guild = None) -> discord.Embed:
    rows = get_weekly_rows(guild_id, week_start)

    embed = discord.Embed(color=WORDLE_GREEN)
    embed.set_footer(text=f"Semaine du {week_start} • Absent/Échec = +7 pts")

    if not rows:
        embed.title = "🏆 Classement Wordle"
        embed.description = f"Aucun score enregistré pour la semaine du **{week_start}**."
        return embed

    total_wordles = rows[0]["total_wordles"]
    embed.title = f"🏆 Classement Wordle — semaine du {week_start}"
    embed.description = f"_{total_wordles} Wordle(s) joués cette semaine_"

    # ── Full list ────────────────────────────────────────────────────
    lines = []
    for i, row in enumerate(rows):
        rank = ["🥇", "🥈", "🥉"][i] if i < 3 else f"`{i + 1}.`"
        best_str = "X" if row["best"] == 7 else str(row["best"])
        missed = row["total_wordles"] - row["played"]
        name = _name(row, guild)
        details = f"{row['total_points']} pts · {row['played']}/{total_wordles} · meilleur {best_str}/6"
        if missed:
            details += f" · _{missed} absent(s)_"
        lines.append(f"{rank} {name} — {details}")

    embed.add_field(name="Classement complet", value="\n".join(lines), inline=False)
    return embed
