# ==========================================
# 🤖 ComRadarHelfer – Haupt-Botdatei
# ==========================================

import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import asyncio
from utils.permissions import setup_discord_logging
from utils.guild_config import load_settings, save_settings

# -------------------------------------------------
# ⚙️ Lade Umgebungsvariablen
# -------------------------------------------------
load_dotenv()
BOT_TOKEN = os.getenv("DISCORD_TOKEN")
TEST_GUILD_ID = int(os.getenv("TEST_GUILD_ID", 0)) or None

# -------------------------------------------------
# 🧠 Grundkonfiguration
# -------------------------------------------------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
bot.remove_command("help")

# -------------------------------------------------
# 🎨 Logging aktivieren
# -------------------------------------------------
setup_discord_logging(bot)
os.makedirs("data", exist_ok=True)

# -------------------------------------------------
# ⚙️ Helper für Command-Sync
# -------------------------------------------------
async def sync_commands(guild_id=None):
    if guild_id:
        guild = bot.get_guild(guild_id)
        if guild:
            synced = await bot.tree.sync(guild=guild)
            print(f"✅ Commands synchronisiert ({len(synced)}) in {guild.name}")
            return synced
    synced = await bot.tree.sync()
    print(f"🌍 Globale Commands synchronisiert ({len(synced)})")
    return synced

# -------------------------------------------------
# ⚙️ Events
# -------------------------------------------------
@bot.event
async def on_ready():
    await bot.wait_until_ready()
    if TEST_GUILD_ID:
        await sync_commands(TEST_GUILD_ID)
    else:
        await sync_commands()
    print(f"🤖 Bot online als {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(activity=discord.Game(name="ComRadarHelfer | /hilfe"))

@bot.event
async def on_guild_join(guild):
    settings = load_settings()
    guild_id = str(guild.id)
    if guild_id not in settings:
        settings[guild_id] = {
            "server_name": guild.name,
            "roles": {"admin": [], "support": []},
            "channels": {"giveaway": None, "quiz": None, "tickets": None},
            "tags": {}
        }
        save_settings(settings)
        print(f"🆕 Neuer Server hinzugefügt: {guild.name} ({guild.id})")
        try:
            if guild.text_channels:
                await guild.text_channels[0].send(
                    f"👋 Hallo **{guild.name}**! Ich wurde hinzugefügt."
                )
        except Exception as e:
            print(f"⚠️ Begrüßung fehlgeschlagen: {e}")
    else:
        if settings[guild_id]["server_name"] != guild.name:
            settings[guild_id]["server_name"] = guild.name
            save_settings(settings)
            print(f"🔄 Servername aktualisiert: {guild.name}")

# -------------------------------------------------
# 🔁 Reload Command
# -------------------------------------------------
@bot.tree.command(name="reload", description="🔁 Lädt alle Cogs neu (Admin).")
@app_commands.checks.has_permissions(administrator=True)
async def reload(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    reloaded, failed = [], []

    for name in list(bot.extensions.keys()):
        try:
            await bot.unload_extension(name)
            print(f"🔻 Entladen: {name}")
        except Exception as e:
            print(f"⚠️ Fehler beim Entladen von {name}: {e}")

    for folder in ("commands", "events"):
        if not os.path.exists(folder):
            os.makedirs(folder)
        for filename in os.listdir(folder):
            if filename.endswith(".py"):
                ext = f"{folder}.{filename[:-3]}"
                try:
                    await bot.load_extension(ext)
                    reloaded.append(ext)
                except Exception as e:
                    failed.append((ext, str(e)))

    if TEST_GUILD_ID:
        await sync_commands(TEST_GUILD_ID)
    else:
        await sync_commands()

    summary = "✅ **Neu geladen:**\n" + "\n".join(reloaded) if reloaded else "⚠️ Keine Cogs geladen."
    if failed:
        summary += "\n\n❌ **Fehler:**\n" + "\n".join([f"{ext}: {err}" for ext, err in failed])
    await interaction.followup.send(summary, ephemeral=True)

# -------------------------------------------------
# 🔄 Sync Command
# -------------------------------------------------
@bot.tree.command(name="sync", description="🔄 Synchronisiert alle Slash-Commands manuell.")
@app_commands.checks.has_permissions(administrator=True)
async def sync_commands_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    synced = await sync_commands(TEST_GUILD_ID if TEST_GUILD_ID else None)
    await interaction.followup.send(f"✅ **{len(synced)}** Commands synchronisiert.", ephemeral=True)

# -------------------------------------------------
# 🆕 Global aktivieren Command
# -------------------------------------------------
@bot.tree.command(name="aktivieren", description="🌍 Aktiviert die Commands global (Admin).")
@app_commands.checks.has_permissions(administrator=True)
async def activate_global(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    synced = await sync_commands()  # ohne guild_id → global
    await interaction.followup.send(f"🌍 Commands jetzt global aktiv!", ephemeral=True)

# -------------------------------------------------
# 📦 Cogs automatisch laden
# -------------------------------------------------
async def load_extensions():
    loaded = set()
    for folder in ("commands", "events"):
        if not os.path.exists(folder):
            os.makedirs(folder)
        for filename in os.listdir(folder):
            if filename.endswith(".py"):
                ext = f"{folder}.{filename[:-3]}"
                if ext not in loaded:
                    try:
                        await bot.load_extension(ext)
                        loaded.add(ext)
                        print(f"✅ Erfolgreich geladen: {ext}")
                    except Exception as e:
                        print(f"⚠️ Fehler beim Laden von {ext}: {e}")

# -------------------------------------------------
# 🚀 Start des Bots
# -------------------------------------------------
async def main():
    async with bot:
        await load_extensions()
        await bot.start(BOT_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Bot manuell gestoppt.")
