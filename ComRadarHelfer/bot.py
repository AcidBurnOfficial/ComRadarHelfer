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
from config import BOT_TOKEN, TEST_GUILD_ID

# -------------------------------------------------
# 🧠 Grundkonfiguration
# -------------------------------------------------
load_dotenv()
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
bot.remove_command("help")

# -------------------------------------------------
# 🎨 Logging aktivieren (Konsole + Datei + Discord)
# -------------------------------------------------
setup_discord_logging(bot)

# -------------------------------------------------
# ⚙️ Events
# -------------------------------------------------
@bot.event
async def on_ready():
    """Wird beim Start einmalig ausgeführt."""
    await bot.wait_until_ready()

    guild = bot.get_guild(TEST_GUILD_ID)
    if guild:
        synced = await bot.tree.sync(guild=guild)
        print(f"✅ Slash-Commands synchronisiert: {len(synced)} in {guild.name}")
    else:
        synced = await bot.tree.sync()
        print(f"🌍 Globale Slash-Commands synchronisiert: {len(synced)}")

    print(f"🤖 Bot ist online als {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(activity=discord.Game(name="ComRadarHelfer | /hilfe"))

# -------------------------------------------------
# 🔁 Reload Command (nur Admins)
# -------------------------------------------------
@bot.tree.command(name="reload", description="🔁 Lädt alle Cogs vollständig neu (inkl. Entladen).")
@app_commands.checks.has_permissions(administrator=True)
async def reload(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    print("🔁 Starte Reload-Prozess...")
    reloaded, failed = [], []

    # 1️⃣ Alle Cogs entladen
    for name in list(bot.extensions.keys()):
        try:
            await bot.unload_extension(name)
            print(f"🔻 Entladen: {name}")
        except Exception as e:
            print(f"⚠️ Fehler beim Entladen von {name}: {e}")

    # 2️⃣ Alle Cogs neu laden
    for folder in ("commands", "events"):
        if not os.path.exists(folder):
            os.makedirs(folder)
        for filename in os.listdir(folder):
            if filename.endswith(".py"):
                extension = f"{folder}.{filename[:-3]}"
                try:
                    await bot.load_extension(extension)
                    reloaded.append(extension)
                except Exception as e:
                    failed.append((extension, str(e)))

    # 3️⃣ Slash-Commands erneut synchronisieren
    guild = bot.get_guild(TEST_GUILD_ID)
    if guild:
        synced = await bot.tree.sync(guild=guild)
        print(f"✅ Slash-Commands neu synchronisiert: {len(synced)} in {guild.name}")
    else:
        synced = await bot.tree.sync()
        print(f"🌍 Globale Slash-Commands neu synchronisiert: {len(synced)}")

    # 4️⃣ Ergebnisnachricht
    summary = "✅ **Neu geladen:**\n" + "\n".join(reloaded) if reloaded else "⚠️ Keine Cogs erfolgreich neu geladen."
    if failed:
        summary += f"\n\n❌ **Fehler:**\n" + "\n".join([f"{ext}: {err}" for ext, err in failed])

    await interaction.followup.send(summary, ephemeral=True)
    print("🔁 Reload abgeschlossen.")

# -------------------------------------------------
# 🔄 Manuelles Sync-Kommando (Admin)
# -------------------------------------------------
@bot.tree.command(name="sync", description="🔄 Synchronisiert alle Slash-Commands manuell neu.")
@app_commands.checks.has_permissions(administrator=True)
async def sync_commands(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    guild = bot.get_guild(TEST_GUILD_ID)
    if guild:
        synced = await bot.tree.sync(guild=guild)
        msg = f"✅ **{len(synced)}** Commands neu synchronisiert (Guild: {guild.name})."
    else:
        synced = await bot.tree.sync()
        msg = f"🌍 **{len(synced)}** globale Commands neu synchronisiert."

    await interaction.followup.send(msg, ephemeral=True)
    print(msg)

# -------------------------------------------------
# 📦 Cogs automatisch laden
# -------------------------------------------------
async def load_extensions():
    """Lädt alle Cogs aus den angegebenen Ordnern."""
    loaded = set()
    for folder in ("commands", "events"):
        if not os.path.exists(folder):
            os.makedirs(folder)
        for filename in os.listdir(folder):
            if filename.endswith(".py"):
                extension = f"{folder}.{filename[:-3]}"
                if extension not in loaded:
                    try:
                        await bot.load_extension(extension)
                        loaded.add(extension)
                        print(f"✅ Erfolgreich geladen: {extension}")
                    except Exception as e:
                        print(f"⚠️ Fehler beim Laden von {extension}: {e}")
                else:
                    print(f"⚠️ Übersprungen (bereits geladen): {extension}")

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
