import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import Modal, TextInput
from config import TEST_GUILD_ID
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
        self.multiple_input = TextInput(  # 🆕 neue Eingabe
            label="Mehrfachantworten erlauben? (ja/nein)",
            required=True,
            placeholder="nein"
        )

        self.add_item(self.title_input)
        self.add_item(self.question_input)
        self.add_item(self.options_input)
        self.add_item(self.duration_input)
        self.add_item(self.multiple_input)  # 🆕

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

        allow_multiple = self.multiple_input.value.strip().lower() in ["ja", "yes", "true", "y"]  # 🆕

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

        # 🆕 Hinweis zur Abstimmungsart
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
            "title": self.title_input.value,
            "question": self.question_input.value,
            "options": options,
            "emojis": option_emojis,
            "end_time": end_time.isoformat(),
            "allow_multiple": allow_multiple,  # 🆕 speichern
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

    # ------------------------------------------
    # /umfrage erstellen
    # ------------------------------------------
    @app_commands.command(name="umfrage", description="Erstellt eine öffentliche Umfrage (Admin only).")
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))
    async def create_umfrage(self, interaction: discord.Interaction):
        await interaction.response.send_modal(UmfrageModal(self.bot, interaction.user))

    # ------------------------------------------
    # /umfrage stop
    # ------------------------------------------
    @app_commands.command(name="umfrage_stop", description="Beendet eine laufende Umfrage sofort (Admin only).")
    @app_commands.describe(message_id="Die Nachrichten-ID der Umfrage (Rechtsklick → Nachricht → ID kopieren)")
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))
    async def stop_umfrage(self, interaction: discord.Interaction, message_id: str):
        if not has_permission(interaction.user):
            await interaction.response.send_message("❌ Nur Administratoren dürfen Umfragen beenden.", ephemeral=True)
            return

        umfragen = load_umfragen()
        target = next((u for u in umfragen if str(u["message_id"]) == message_id), None)
        if not target:
            await interaction.response.send_message("⚠️ Keine laufende Umfrage mit dieser ID gefunden.", ephemeral=True)
            return

        channel = self.bot.get_channel(target["channel_id"])
        if not channel:
            await interaction.response.send_message("⚠️ Kanal der Umfrage konnte nicht gefunden werden.", ephemeral=True)
            return

        try:
            message = await channel.fetch_message(int(message_id))
        except discord.NotFound:
            await interaction.response.send_message("⚠️ Die Nachricht zur Umfrage existiert nicht mehr.", ephemeral=True)
            return

        await self.finish_umfrage(message, target, manuell=True)

        umfragen.remove(target)
        save_umfragen(umfragen)

        await interaction.response.send_message(f"✅ Umfrage **{target['title']}** wurde beendet und ausgewertet.", ephemeral=True)

    # ------------------------------------------
    # Ergebnisberechnung & Abschluss
    # ------------------------------------------
    async def finish_umfrage(self, message, umfrage, manuell=False):
        counts = {emoji: 0 for emoji in umfrage["emojis"]}
        for reaction in message.reactions:
            if str(reaction.emoji) in counts:
                counts[str(reaction.emoji)] = reaction.count - 1  # -1 wegen Bot

        total_votes = sum(counts.values())
        results_text = ""
        for emoji, opt in zip(umfrage["emojis"], umfrage["options"]):
            votes = counts[emoji]
            percentage = (votes / total_votes * 100) if total_votes > 0 else 0
            results_text += f"{emoji} **{opt}** — {votes} Stimmen ({percentage:.1f}%)\n"

        old_embed = message.embeds[0]
        closed_embed = discord.Embed(
            title=f"🔒 {old_embed.title} — Beendet",
            description=old_embed.description,
            color=discord.Color.dark_gray(),
        )
        for f in old_embed.fields:
            closed_embed.add_field(name=f.name, value=f.value, inline=False)
        closed_embed.set_footer(text=f"Beendet {'manuell' if manuell else 'automatisch'} am {datetime.utcnow().strftime('%d.%m.%Y um %H:%M UTC')}")

        await message.edit(embed=closed_embed)

        result_embed = discord.Embed(
            title=f"📊 Ergebnis: {umfrage['title']}",
            description=f"**{umfrage['question']}**\n\n{results_text}",
            color=discord.Color.gold(),
        )
        result_embed.set_footer(text=f"{'Manuell beendet' if manuell else 'Automatisch abgeschlossen'} am {datetime.utcnow().strftime('%d.%m.%Y um %H:%M UTC')}")
        await message.channel.send(embed=result_embed)

    # ------------------------------------------
    # Automatische Auswertung
    # ------------------------------------------
    @tasks.loop(minutes=1)
    async def umfrage_watcher(self):
        umfragen = load_umfragen()
        now = datetime.utcnow()
        updated = False

        for umfrage in list(umfragen):
            end_time = datetime.fromisoformat(umfrage["end_time"])
            if now >= end_time:
                channel = self.bot.get_channel(umfrage["channel_id"])
                if not channel:
                    continue
                try:
                    message = await channel.fetch_message(umfrage["message_id"])
                except discord.NotFound:
                    continue
                await self.finish_umfrage(message, umfrage, manuell=False)
                umfragen.remove(umfrage)
                updated = True

        if updated:
            save_umfragen(umfragen)

    # ------------------------------------------
    # 🆕 Reaktionsüberwachung (verhindert Mehrfachvoten)
    # ------------------------------------------
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return

        umfragen = load_umfragen()
        target = next((u for u in umfragen if u["message_id"] == payload.message_id), None)
        if not target:
            return

        if target.get("allow_multiple", True):
            return  # Mehrfachvoten erlaubt

        guild = self.bot.get_guild(payload.guild_id)
        channel = guild.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        user = guild.get_member(payload.user_id)

        # alle anderen Reaktionen des Users entfernen
        for reaction in message.reactions:
            if reaction.emoji != str(payload.emoji):
                async for reactor in reaction.users():
                    if reactor.id == user.id:
                        await reaction.remove(user)
                        break


async def setup(bot):
    await bot.add_cog(UmfragenSystem(bot))
