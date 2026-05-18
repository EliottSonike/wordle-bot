from database import get_weekly_rows

MEDALS = ["🥇", "🥈", "🥉"]


def build_leaderboard(guild_id: str, week_start: str) -> str:
    rows = get_weekly_rows(guild_id, week_start)
    if not rows:
        return f"Aucun score enregistré pour la semaine du **{week_start}**."

    total_wordles = rows[0]["total_wordles"]
    lines = [f"🏆 **Classement Wordle — semaine du {week_start}** ({total_wordles} partie(s))\n"]
    for i, row in enumerate(rows):
        rank = MEDALS[i] if i < 3 else f"`{i + 1}.`"
        best_str = "X" if row["best"] == 7 else str(row["best"])
        missed = row["total_wordles"] - row["played"]
        missed_note = f" *(+7 pour {missed} absent{'s' if missed > 1 else ''})*" if missed > 0 else ""
        lines.append(
            f"{rank} **{row['username']}** — {row['total_points']} pts · meilleur {best_str}/6 · {row['played']}/{total_wordles} joué(s){missed_note}"
        )
    return "\n".join(lines)
