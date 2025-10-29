import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import Modal, TextInput
from config import TEST_GUILD_ID  # optional, kann auch entfernt werden
import asyncio
import json
import os
from datetime import datetime, timedelta
from utils.permissions import has_permission

DATA_FILE = "data/umfragen.json"

os.makedirs("data", exist_ok=True)
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump([], f, indent=4)


def load_umfragen():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_umfragen(umfragen):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(umfragen, f, indent=4)


# -------------------------------------------------
# Modal zum Erstellen einer Umfrage
# -------------------------------------------------
class UmfrageModal(Modal, title="📊 Neue Umfrage erstellen"):
    def __init__(self, bot, interaction_user):
        super().__init__()
        self.bot = bot
        self.user = interaction_user

        self.title_input = TextInput(label="Titel der Umfrage", required=True, max_length=100)
        self.question_input = TextInput(label="Frage oder Beschreibung", style=discord.TextStyle.paragraph, required=True)
        self.options_input = TextInput(label="Antwortoptionen (durch Kommas getrennt)", required=True, placeholder="z.B. Ja, Nein, Vielleicht")
        self.duration_input = TextInput(label="Laufzeit (z.B. 1h, 2d6h, 30m)", required=True, placeholder="1h")
        self.multiple_input = TextInput(
            label="Mehrfachantworten erlauben? (ja/nein)",
            required=True,
            placeholder="nein"
        )

        self.add_item(self.title_input)
        self.add_item(self.question_input)
        self.add_item(self.options_input)
        self.add_item(self.duration_input)
        self.add_item(self.multiple_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not has_permission(interaction.user):
            await interaction.response.send_message("❌ Nur Administratoren dürfen Umfragen erstellen.", ephemeral=True)
            return

        options = [o.strip() for o in self.options_input.value.split(",") if o.strip()]
        if len(options) < 2:
            await interaction.response.send_message("⚠️ Du musst mindestens **zwei Antwortoptionen** angeben.", ephemeral=True)
            return

        duration = self.parse_duration(self.duration_input.value)
        if not duration:
            await interaction.response.send_message("⚠️ Ungültiges Zeitformat. Beispiele: `1h`, `2d6h`, `30m`", ephemeral=True)
            return

        allow_multiple = self.multiple_input.value.strip().lower() in ["ja", "yes", "true", "y"]

        end_time = datetime.utcnow() + duration
        embed = discord.Embed(
            title=f"📊 {self.title_input.value}",
            description=self.question_input.value,
            color=discord.Color.gold(),
            timestamp=end_time
        )
        embed.set_footer(text=f"Endet am {end_time.strftime('%d.%m.%Y um %H:%M Uhr UTC')}")

        emoji_list = ["🅰️", "🅱️", "🇨", "🇩", "🇪", "🇫", "🇬"]
        option_emojis = emoji_list[:len(options)]

        for emoji, option in zip(option_emojis, options):
            embed.add_field(name=f"{emoji} {option}", value="\u200b", inline=False)

        embed.add_field(
            name="🗳️ Abstimmungsart",
            value="Mehrfachantworten erlaubt ✅" if allow_multiple else "Nur eine Antwort erlaubt ❌",
            inline=False
        )

        message = await interaction.channel.send(embed=embed)
        for emoji in option_emojis:
            await message.add_reaction(emoji)

        umfragen = load_umfragen()
        umfragen.append({
            "message_id": message.id,
            "channel_id": message.channel.id,
            "creator_id": interaction.user.id,
            "guild_id": interaction.guild.id,
            "title": self.title_input.value,
            "question": self.question_input.value,
            "options": options,
            "emojis": option_emojis,
            "end_time": end_time.isoformat(),
            "allow_multiple": allow_multiple,
        })
        save_umfragen(umfragen)

        await interaction.response.send_message(f"✅ Umfrage **{self.title_input.value}** gestartet!", ephemeral=True)

    def parse_duration(self, duration_str):
        try:
            days = hours = minutes = 0
            tmp = duration_str
            if "d" in tmp:
                days = int(tmp.split("d")[0])
                tmp = tmp.split("d")[1]
            if "h" in tmp:
                hours = int(tmp.split("h")[0])
                tmp = tmp.split("h")[1]
            if "m" in tmp:
                minutes = int(tmp.split("m")[0])
            return timedelta(days=days, hours=hours, minutes=minutes)
        except Exception:
            return None


# -------------------------------------------------
# Cog: Umfragen-System
# -------------------------------------------------
class UmfragenSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.umfrage_watcher.start()

    def cog_unload(self):
        self.umfrage_watcher.cancel()

    @app_comman_
