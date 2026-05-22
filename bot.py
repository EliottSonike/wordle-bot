import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

from database import init_db, insert_score, get_user_scores, get_user_id_by_name, upsert_username
import re as _re
from parser import is_wordle_results, parse_scores, extract_wordle_num
from leaderboard import build_leaderboard
from image_leaderboard import build_podium_image

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


def resolve_plain_mentions(content: str, guild_id: str, known_ids: set) -> list:
    """Try to resolve plain-text @Name mentions to (user_id, attempts) pairs."""
    results = []
    for line in content.splitlines():
        m = _re.search(r"(\d|X)/6\*?\s*:", line, _re.IGNORECASE)
        if not m:
            continue
        attempts = 7 if m.group(1).upper() == "X" else int(m.group(1))
        rest = _re.sub(r"<@!?\d+>", "", line[m.end():])
        for raw in rest.split("@"):
            name = raw.strip().replace("\\", "")
            if not name:
                continue
            uid = get_user_id_by_name(guild_id, name)
            if uid and uid not in known_ids:
                results.append((uid, attempts))
                known_ids.add(uid)
    return results


def resolve_username(guild: discord.Guild, user_id: str) -> str:
    member = guild.get_member(int(user_id))
    return member.display_name if member else f"<@{user_id}>"


# ── Events ─────────────────────────────────────────────────────────────────────

GUILD_ID = int(os.getenv("GUILD_ID", "0"))

@bot.event
async def on_ready():
    init_db()
    if GUILD_ID:
        guild = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
    else:
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
    if wordle_num == 0:
        print(f"[Wordle Bot] Numéro Wordle introuvable dans le message {message.id}")
        await message.add_reaction("⚠️")
        return

    ws = week_start()
    saved = 0

    guild_id = str(message.guild.id)
    id_scores = parse_scores(message.content)
    known_ids = {uid for uid, _ in id_scores}
    plain_scores = resolve_plain_mentions(message.content, guild_id, known_ids)
    for user_id, attempts in id_scores + plain_scores:
        username = resolve_username(message.guild, user_id)
        upsert_username(guild_id, user_id, username)
        if insert_score(guild_id, user_id, username, wordle_num, attempts, ws):
            saved += 1

    if saved:
        await message.add_reaction("✅")


# ── Slash commands ─────────────────────────────────────────────────────────────

async def _send_leaderboard(interaction: discord.Interaction, ws: str):
    from database import get_weekly_rows
    rows = get_weekly_rows(str(interaction.guild_id), ws)
    if not rows:
        await interaction.followup.send(f"Aucun score enregistré pour la semaine du **{ws}**.")
        return
    podium     = await build_podium_image(rows, ws, bot)
    embed_top  = discord.Embed(color=0x538D4E)
    embed_top.set_image(url="attachment://podium.png")
    embed_list = build_leaderboard(str(interaction.guild_id), ws, interaction.guild)
    await interaction.followup.send(file=podium, embeds=[embed_top, embed_list])


@bot.tree.command(name="classement", description="Affiche le classement Wordle de la semaine en cours")
async def cmd_classement(interaction: discord.Interaction):
    await interaction.response.defer()
    await _send_leaderboard(interaction, week_start())


@bot.tree.command(name="classement-semaine", description="Affiche le classement d'une semaine précise (format YYYY-MM-DD)")
@app_commands.describe(date="Date du lundi de la semaine (ex: 2025-05-12)")
async def cmd_classement_semaine(interaction: discord.Interaction, date: str):
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        await interaction.response.send_message("Format invalide. Utilise YYYY-MM-DD (ex: 2025-05-12).", ephemeral=True)
        return
    await interaction.response.defer()
    await _send_leaderboard(interaction, date)


@bot.tree.command(name="mon-score", description="Affiche tes scores Wordle de la semaine")
async def cmd_mon_score(interaction: discord.Interaction):
    ws = week_start()
    rows = get_user_scores(str(interaction.guild_id), str(interaction.user.id), ws)
    if not rows:
        await interaction.response.send_message("Aucun score enregistré pour toi cette semaine.", ephemeral=True)
        return

    total = sum(r["attempts"] for r in rows)
    lines = [f"**Tes scores cette semaine ({ws}) — {total} pts :**"]
    for row in rows:
        score_str = "X/6 *(+7)*" if row["attempts"] == 7 else f"{row['attempts']}/6"
        lines.append(f"• Wordle #{row['wordle_num']} — {score_str}")
    await interaction.response.send_message("\n".join(lines), ephemeral=True)


@bot.tree.command(name="backfill", description="[Admin] Retraite les N derniers messages du salon Wordle (défaut: 50)")
@app_commands.describe(limit="Nombre de messages à relire (1-2000)")
@app_commands.default_permissions(administrator=True)
async def cmd_backfill(interaction: discord.Interaction, limit: int = 200):
    if not 1 <= limit <= 2000:
        await interaction.response.send_message("Le nombre de messages doit être entre 1 et 200.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    channel = bot.get_channel(WORDLE_CHANNEL_ID)
    if not channel:
        await interaction.followup.send("Canal Wordle introuvable.", ephemeral=True)
        return

    guild_id = str(interaction.guild_id)
    inserted = 0
    skipped = 0

    async for msg in channel.history(limit=limit):
        if not msg.author.bot or msg.author.name != WORDLE_BOT_NAME:
            continue
        if not is_wordle_results(msg.content):
            continue
        wordle_num = extract_wordle_num(msg)
        if wordle_num == 0:
            continue
        ws = week_start(msg.created_at)
        id_scores = parse_scores(msg.content)
        known_ids = {uid for uid, _ in id_scores}
        plain_scores = resolve_plain_mentions(msg.content, guild_id, known_ids)
        for user_id, attempts in id_scores + plain_scores:
            username = resolve_username(interaction.guild, user_id)
            upsert_username(guild_id, user_id, username)
            if insert_score(guild_id, user_id, username, wordle_num, attempts, ws):
                inserted += 1
            else:
                skipped += 1

    await interaction.followup.send(
        f"Backfill terminé : **{inserted}** score(s) ajouté(s), {skipped} déjà existant(s).",
        ephemeral=True,
    )


@bot.tree.command(name="forcer-classement", description="[Admin] Poste le classement de la semaine en cours dans le salon leaderboard")
@app_commands.default_permissions(administrator=True)
async def cmd_forcer_classement(interaction: discord.Interaction):
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if not channel:
        await interaction.response.send_message("Canal leaderboard introuvable.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    from database import get_weekly_rows
    rows = get_weekly_rows(str(interaction.guild_id), week_start())
    if rows:
        podium     = await build_podium_image(rows, week_start(), bot)
        embed_top  = discord.Embed(color=0x538D4E)
        embed_top.set_image(url="attachment://podium.png")
        embed_list = build_leaderboard(str(interaction.guild_id), week_start(), interaction.guild)
        await channel.send(file=podium, embeds=[embed_top, embed_list])
    await interaction.followup.send("Classement posté.", ephemeral=True)


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
    from database import get_weekly_rows
    rows = get_weekly_rows(str(channel.guild.id), last_monday)
    if rows:
        podium     = await build_podium_image(rows, last_monday, bot)
        embed_top  = discord.Embed(color=0x538D4E)
        embed_top.set_image(url="attachment://podium.png")
        embed_list = build_leaderboard(str(channel.guild.id), last_monday, channel.guild)
        await channel.send(file=podium, embeds=[embed_top, embed_list])


@weekly_leaderboard.before_loop
async def before_weekly():
    await bot.wait_until_ready()


# ── Entry point ────────────────────────────────────────────────────────────────

bot.run(TOKEN)
