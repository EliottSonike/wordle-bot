import discord
from database import get_weekly_rows

WORDLE_GREEN = 0x538D4E


def _name(row, guild):
    if guild:
        member = guild.get_member(int(row["user_id"]))
        if member:
            return member.mention
    return f"**{row['username']}**"


def build_leaderboard(guild_id: str, week_start: str, guild: discord.Guild = None) -> discord.Embed:
    rows = get_weekly_rows(guild_id, week_start)

    embed = discord.Embed(color=WORDLE_GREEN)
    embed.set_footer(text=f"Semaine du {week_start} • Le moins de points gagne • Absent/Échec = +7")

    if not rows:
        embed.title = "🏆 Classement Wordle"
        embed.description = f"Aucun score enregistré pour la semaine du **{week_start}**."
        return embed

    total_wordles = rows[0]["total_wordles"]
    embed.title = f"🏆 Classement Wordle — semaine du {week_start}"
    embed.description = f"_{total_wordles} Wordle(s) joués cette semaine_"

    # ── Podium (3 inline fields : 2nd | 1st | 3rd) ──────────────────
    podium_order = [1, 0, 2]
    podium_icons = {0: "🥇", 1: "🥈", 2: "🥉"}
    podium_labels = {0: "1ᵉʳ", 1: "2ᵉ", 2: "3ᵉ"}

    for si in podium_order:
        if si >= len(rows):
            embed.add_field(name="​", value="​", inline=True)
            continue
        row = rows[si]
        best_str = "X" if row["best"] == 7 else str(row["best"])
        name = _name(row, guild)
        value = f"{name}\n**{row['total_points']} pts**\nmeilleur {best_str}/6"
        embed.add_field(
            name=f"{podium_icons[si]} {podium_labels[si]} place",
            value=value,
            inline=True,
        )

    # Separator
    embed.add_field(name="​", value="─" * 36, inline=False)

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
