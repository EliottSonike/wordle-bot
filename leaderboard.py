from database import get_weekly_rows

MEDALS = ["🥇", "🥈", "🥉"]


def build_leaderboard(week_start: str) -> str:
    rows = get_weekly_rows(week_start)
    if not rows:
        return f"Aucun score enregistré pour la semaine du **{week_start}**."

    lines = [f"🏆 **Classement Wordle — semaine du {week_start}**\n"]
    for i, row in enumerate(rows):
        rank = MEDALS[i] if i < 3 else f"`{i + 1}.`"
        avg = row["avg_attempts"]
        avg_str = "échec" if avg >= 7 else f"{avg:.2f}/6"
        failed_note = f" *(dont {row['failed']} échec{'s' if row['failed'] > 1 else ''})*" if row["failed"] > 0 else ""
        best = row["best"]
        best_str = "X" if best == 7 else str(best)
        lines.append(
            f"{rank} **{row['username']}** — moy. {avg_str} · meilleur {best_str}/6 · {row['games']} partie(s){failed_note}"
        )
    return "\n".join(lines)
