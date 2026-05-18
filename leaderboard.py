import discord
from database import get_weekly_rows

MEDALS = ["🥇", "🥈", "🥉"]
WORDLE_GREEN = 0x538D4E


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
    embed.description = f"_{total_wordles} Wordle(s) joués cette semaine_\n​"

    lines = []
    for i, row in enumerate(rows):
        rank = MEDALS[i] if i < 3 else f"**{i + 1}.**"
        best_str = "X" if row["best"] == 7 else f"{row['best']}"
        missed = row["total_wordles"] - row["played"]

        if guild:
            member = guild.get_member(int(row["user_id"]))
            name = member.mention if member else f"**{row['username']}**"
        else:
            name = f"**{row['username']}**"

        details = f"{row['total_points']} pts · {row['played']}/{total_wordles} joués · meilleur {best_str}/6"
        if missed:
            details += f" · _{missed} absent(s)_"

        lines.append(f"{rank} {name} — {details}")

    embed.add_field(name="Classement", value="\n".join(lines), inline=False)
    return embed
