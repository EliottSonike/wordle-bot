import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

from database import init_db, insert_score, get_user_scores
from parser import is_wordle_results, parse_scores, extract_wordle_num
from leaderboard import build_leaderboard

load_dotenv()

TOKEN = os.environ["DISCORD_TOKEN"]
WORDLE_CHANNEL_ID = int(os.environ["WORDLE_CHANNEL_ID"])
LEADERBOARD_CHANNEL_ID = int(os.environ["LEADERBOARD_CHANNEL_ID"])
WORDLE_BOT_NAME = os.getenv("WORDLE_BOT_NAME", "Wordle")
# Day/hour to post the leaderboard (UTC). 0 = Monday, 8 = 08:00
LEADERBOARD_WEEKDAY = int(os.getenv("LEADERBOARD_WEEKDAY", "0"))
LEADERBOARD_HOUR = int(os.getenv("LEADERBOARD_HOUR", "8"))

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


# ── Helpers ────────────────────────────────────────────────────────────────────

def week_start(dt: datetime = None) -> str:
    """ISO date of the Monday that starts the current (or given) week."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    monday = dt - timedelta(days=dt.weekday())
    return monday.strftime("%Y-%m-%d")


def resolve_username(guild: discord.Guild, user_id: str) -> str:
    member = guild.get_member(int(user_id))
    return member.display_name if member else f"<@{user_id}>"


# ── Events ─────────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    init_db()
    await bot.tree.sync()
    weekly_leaderboard.start()
    print(f"[Wordle Bot] Connecté en tant que {bot.user} (id={bot.user.id})")


@bot.event
async def on_message(message: discord.Message):
    # Only process messages from the Wordle APP in the configured channel
    if message.channel.id != WORDLE_CHANNEL_ID:
        return
    if not message.author.bot:
        return
    if message.author.name != WORDLE_BOT_NAME:
        return
    if not is_wordle_results(message.content):
        return

    wordle_num = extract_wordle_num(message)
    ws = week_start()
    saved = 0

    for user_id, attempts in parse_scores(message.content):
        username = resolve_username(message.guild, user_id)
        if insert_score(user_id, username, wordle_num, attempts, ws):
            saved += 1

    if saved:
        await message.add_reaction("✅")


# ── Slash commands ─────────────────────────────────────────────────────────────

@bot.tree.command(name="classement", description="Affiche le classement Wordle de la semaine en cours")
async def cmd_classement(interaction: discord.Interaction):
    text = build_leaderboard(week_start())
    await interaction.response.send_message(text)


@bot.tree.command(name="classement-semaine", description="Affiche le classement d'une semaine précise (format YYYY-MM-DD)")
@app_commands.describe(date="Date du lundi de la semaine (ex: 2025-05-12)")
async def cmd_classement_semaine(interaction: discord.Interaction, date: str):
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        await interaction.response.send_message("Format invalide. Utilise YYYY-MM-DD (ex: 2025-05-12).", ephemeral=True)
        return
    text = build_leaderboard(date)
    await interaction.response.send_message(text)


@bot.tree.command(name="mon-score", description="Affiche tes scores Wordle de la semaine")
async def cmd_mon_score(interaction: discord.Interaction):
    ws = week_start()
    rows = get_user_scores(str(interaction.user.id), ws)
    if not rows:
        await interaction.response.send_message("Aucun score enregistré pour toi cette semaine.", ephemeral=True)
        return

    lines = [f"**Tes scores cette semaine ({ws}) :**"]
    for row in rows:
        score_str = "X/6 *(échec)*" if row["attempts"] == 7 else f"{row['attempts']}/6"
        lines.append(f"• Wordle #{row['wordle_num']} — {score_str}")
    await interaction.response.send_message("\n".join(lines), ephemeral=True)


# ── Scheduled task ─────────────────────────────────────────────────────────────

@tasks.loop(minutes=1)
async def weekly_leaderboard():
    now = datetime.now(timezone.utc)
    if now.weekday() != LEADERBOARD_WEEKDAY or now.hour != LEADERBOARD_HOUR or now.minute != 0:
        return

    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if not channel:
        print(f"[Wordle Bot] Canal leaderboard introuvable (id={LEADERBOARD_CHANNEL_ID})")
        return

    # Since we fire on Monday, 7 days ago is exactly last Monday
    last_monday = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    text = build_leaderboard(last_monday)
    await channel.send(text)


@weekly_leaderboard.before_loop
async def before_weekly():
    await bot.wait_until_ready()


# ── Entry point ────────────────────────────────────────────────────────────────

bot.run(TOKEN)
