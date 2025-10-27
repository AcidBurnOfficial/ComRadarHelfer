import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import json
import os
import re

from config import TEST_GUILD_ID

DATA_FILE = "data/abstimmungen.json"


# ==========================================================
# 🧩 Hilfsfunktion: UUID mit Bindestrichen formatieren
# ==========================================================
def format_uuid(uuid_str: str) -> str:
    """
    Fügt Bindestriche in eine Mojang-UUID ein.
    Erwartet 32 hex-Zeichen, gibt zurück: 8-4-4-4-12
    Beispiel:
      f492d73fea394ef2bb732046a4e42859
      -> f492d73f-ea39-4ef2-bb73-2046a4e42859
    """
    if not uuid_str:
        return "❌ Keine UUID"
    clean = uuid_str.replace("-", "").strip().lower()
    if len(clean) != 32 or not re.fullmatch(r"[0-9a-f]{32}", clean):
        return uuid_str  # ungültig → keine Formatierung
    return f"{clean[0:8]}-{clean[8:12]}-{clean[12:16]}-{clean[16:20]}-{clean[20:]}"


# ==========================================================
# ⚙️ Cog: /uuid-Befehl (lokal + Griefer.info + Mojang)
# ==========================================================
class UUIDCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --------------------------------------------------
    # Lokale Suche in data/abstimmungen.json
    # --------------------------------------------------
    def fetch_from_local(self, name: str):
        """Sucht nach dem Spieler in der lokalen Datei."""
        if not os.path.exists(DATA_FILE):
            return None, None

        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            return None, None

        name_lower = name.lower()
        for eintrag in data:
            if eintrag.get("beschuldigter", "").lower() == name_lower:
                return eintrag.get("uuid"), "Lokale Datenbank"
        return None, None

    # --------------------------------------------------
    # Abfrage bei Griefer.info
    # --------------------------------------------------
    async def fetch_from_grieferinfo(self, name: str):
        """Versucht, die UUID über Griefer.info zu erhalten."""
        url = f"https://griefer.info/community-radar/uuid-by-name?name={name}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        # Griefer.info gibt oft direkt die UUID als Text zurück
                        uuid = text.strip().replace('"', '').replace("'", "")
                        if len(uuid) >= 32:
                            return uuid, "Griefer.info"
        except Exception:
            pass
        return None, None

    # --------------------------------------------------
    # Abfrage bei Mojang
    # --------------------------------------------------
    async def fetch_from_mojang(self, name: str):
        """Holt die UUID über Mojang API."""
        url = f"https://api.mojang.com/users/profiles/minecraft/{name}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if "id" in data:
                            return data["id"], "Mojang"
        except Exception:
            pass
        return None, None

    # --------------------------------------------------
    # Gesamtabfrage (lokal → Griefer → Mojang)
    # --------------------------------------------------
    async def fetch_uuid(self, name: str):
        uuid, source = self.fetch_from_local(name)
        if uuid:
            return uuid, source

        uuid, source = await self.fetch_from_grieferinfo(name)
        if uuid:
            return uuid, source

        uuid, source = await self.fetch_from_mojang(name)
        if uuid:
            return uuid, source

        return None, None

    # --------------------------------------------------
    # /uuid-Befehl
    # --------------------------------------------------
    @app_commands.command(name="uuid", description="Zeigt die UUID eines Minecraft-Spielers an (lokal, Griefer.info & Mojang).")
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))
    async def uuid(self, interaction: discord.Interaction, spielername: str):
        await interaction.response.defer(thinking=True)

        uuid_raw, source = await self.fetch_uuid(spielername)

        if not uuid_raw:
            await interaction.followup.send(f"❌ Spieler **{spielername}** wurde nicht gefunden.", ephemeral=True)
            return

        uuid_formatted = format_uuid(uuid_raw)

        embed = discord.Embed(
            title=f"🧩 UUID von {spielername}",
            description=f"`{uuid_formatted}`",
            color=discord.Color.green(),
        )
        embed.set_footer(text=f"Quelle: {source}")
        await interaction.followup.send(embed=embed)


# ==========================================================
# 🚀 Setup
# ==========================================================
async def setup(bot):
    await bot.add_cog(UUIDCommand(bot))
