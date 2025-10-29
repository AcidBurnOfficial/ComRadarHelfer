import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import Modal, TextInput
from utils.permissions import has_permission, logger
from utils.guild_config import load_settings
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import random

# =============================================
# 📂 Einstellungen & Konstanten
# =============================================
DATA_FILE = "data/giveaways.json"
BERLIN_TZ = ZoneInfo("Europe/Berlin")  # Automatische Sommer-/Winterzeit


# =============================================
# 🔧 Hilfsfunktionen
# =============================================
def load_giveaways():
    if not os.path.exists(DATA_FILE):
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, "w") as f:
            json.dump({}, f)
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_giveaways(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


def parse_datetime(dt_str):
    """Erwartet Format TT.MM.JJJJ HH:MM"""
    try:
        dt = datetime.strptime(dt_str, "%d.%m.%Y %H:%M")
        return dt.replace(tzinfo=BERLIN_TZ)
    except ValueError:
        return None


# =============================================
# 🎉 Giveaway Modal
# =============================================
class GiveawayModal(Modal, title="🎁 Neues Giveaway erstellen"):
    preis = TextInput(label="🎁 Preis", placeholder="z.B. Discord Nitro oder Amazon-Gutschein")
    gewinner = TextInput(label="🏆 Anzahl Gewinner", placeholder="z.B. 2", default="1")
    endzeit = TextInput(label="⏰ Endzeit (TT.MM.JJJJ HH:MM)", placeholder="z.B. 15.10.2025 20:30")

    async def on_submit(self, interaction: discord.Interaction):
        if not has_permission(interaction.user):
            await interaction.response.send_message("❌ Du hast keine Berechtigung.", ephemeral=True)
            return

        end_dt = parse_datetime(self.endzeit.value)
        if not end_dt:
            await interaction.response.send_message("❌ Falsches Datumsformat. Bitte TT.MM.JJJJ HH:MM verwenden.", ephemeral=True)
            return

        # Channel dynamisch aus JSON laden
        settings = load_settings()
        guild_id = str(interaction.guild.id)
        channel_id = settings.get(guild_id, {}).get("GIVEAWAY_CHANNEL_ID")
        if not channel_id:
            await interaction.response.send_message("⚠️ Giveaway-Kanal noch nicht gesetzt. /setup ausführen.", ephemeral=True)
            return

        channel = interaction.client.get_channel(channel_id)
        if not channel:
            await interaction.response.send_message("⚠️ Giveaway-Kanal nicht gefunden.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🎉 Neues Giveaway gestartet!",
            description=(
                f"**Preis:** {self.preis.value}\n"
                f"**Gewinner:** {self.gewinner.value}\n\n"
                f"➡️ Klicke auf **Teilnehmen**, um mitzumachen!"
            ),
            color=discord.Color.gold(),
            timestamp=datetime.now(BERLIN_TZ),
        )
        embed.set_footer(text=f"Endet am {end_dt.strftime('%d.%m.%Y um %H:%M Uhr (MEZ/MESZ)')}")

        view = GiveawayView(self.preis.value, int(self.gewinner.value), end_dt)
        msg = await channel.send(embed=embed, view=view)

        data = load_giveaways()
        data[str(msg.id)] = {
            "preis": self.preis.value,
            "gewinner": int(self.gewinner.value),
            "endzeit": end_dt.isoformat(),
            "teilnehmer": [],
            "beendet": False,
            "guild_id": guild_id,  # Server speichern
        }
        save_giveaways(data)

        logger.info(f"🎉 Giveaway gestartet von {interaction.user} (Preis: {self.preis.value}) in Server {interaction.guild.name}")
        await interaction.response.send_message(f"✅ Giveaway gestartet in {channel.mention}.", ephemeral=True)


# =============================================
# 🎟️ Giveaway View
# =============================================
class GiveawayView(discord.ui.View):
    def __init__(self, preis, gewinner, end_dt):
        super().__init__(timeout=None)
        self.preis = preis
        self.gewinner = gewinner
        self.end_dt = end_dt

    @discord.ui.button(label="🎉 Teilnehmen", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_giveaways()
        giveaway = data.get(str(interaction.message.id))

        if not giveaway or giveaway.get("beendet"):
            await interaction.response.send_message("🚫 Dieses Giveaway ist bereits beendet!", ephemeral=True)
            return

        uid = interaction.user.id
        if uid in giveaway["teilnehmer"]:
            giveaway["teilnehmer"].remove(uid)
            await interaction.response.send_message("❎ Du hast deine Teilnahme zurückgezogen.", ephemeral=True)
        else:
            giveaway["teilnehmer"].append(uid)
            await interaction.response.send_message("🎟️ Du nimmst jetzt am Giveaway teil!", ephemeral=True)

        save_giveaways(data)


# =============================================
# ⚙️ Giveaway Cog
# =============================================
class GiveawayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()

    # -----------------------------------------
    # /giveaway starten
    # -----------------------------------------
    @app_commands.command(name="giveaway_start", description="🎁 Starte ein neues Giveaway (Admin/Team only)")
    async def giveaway(self, interaction: discord.Interaction):
        if not has_permission(interaction.user):
            await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)
            return
        await interaction.response.send_modal(GiveawayModal())

    # -----------------------------------------
    # /reroll
    # -----------------------------------------
    @app_commands.command(name="giveaway_reroll", description="♻️ Ziehe neue Gewinner für ein Giveaway per Nachrichten-ID.")
    @app_commands.describe(nachricht_id="Die ID der Giveaway-Nachricht", anzahl="Anzahl der neuen Gewinner")
    async def reroll(self, interaction: discord.Interaction, nachricht_id: str, anzahl: int = None):
        if not has_permission(interaction.user):
            await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)
            return

        data = load_giveaways()
        if nachricht_id not in data:
            await interaction.response.send_message("⚠️ Kein Giveaway mit dieser Nachrichten-ID gefunden.", ephemeral=True)
            return

        giveaway = data[nachricht_id]
        teilnehmer = giveaway.get("teilnehmer", [])
        if not teilnehmer:
            await interaction.response.send_message("😕 Keine Teilnehmer gefunden.", ephemeral=True)
            return

        random.shuffle(teilnehmer)
        winners = teilnehmer[:anzahl or giveaway["gewinner"]]
        mentions = ", ".join(f"<@{u}>" for u in winners)

        guild_id = giveaway["guild_id"]
        channel_id = load_settings().get(guild_id, {}).get("GIVEAWAY_CHANNEL_ID")
        channel = interaction.client.get_channel(channel_id)
        if channel:
            embed = discord.Embed(
                title="♻️ Giveaway neu ausgelost!",
                description=f"**Preis:** {giveaway['preis']}\n**Neue Gewinner:** {mentions}",
                color=discord.Color.green(),
            )
            await channel.send(embed=embed)

        await interaction.response.send_message("✅ Giveaway wurde neu ausgelost!", ephemeral=True)
        logger.info(f"♻️ {interaction.user} hat /reroll für Nachricht {nachricht_id} ausgeführt – Gewinner: {mentions}")

    # -----------------------------------------
    # /cancel
    # -----------------------------------------
    @app_commands.command(name="giveaway_cancel", description="🛑 Bricht das aktuelle Giveaway ab (per Nachrichten-ID).")
    @app_commands.describe(nachricht_id="Die ID der Giveaway-Nachricht")
    async def cancel(self, interaction: discord.Interaction, nachricht_id: str):
        if not has_permission(interaction.user):
            await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)
            return

        data = load_giveaways()
        if nachricht_id not in data:
            await interaction.response.send_message("⚠️ Kein Giveaway mit dieser ID gefunden.", ephemeral=True)
            return

        giveaway = data[nachricht_id]
        if giveaway["beendet"]:
            await interaction.response.send_message("🚫 Dieses Giveaway ist bereits beendet.", ephemeral=True)
            return

        guild_id = giveaway["guild_id"]
        channel_id = load_settings().get(guild_id, {}).get("GIVEAWAY_CHANNEL_ID")
        channel = interaction.client.get_channel(channel_id)
        if not channel:
            await interaction.response.send_message("⚠️ Kanal nicht gefunden.", ephemeral=True)
            return

        try:
            msg = await channel.fetch_message(int(nachricht_id))
        except discord.NotFound:
            await interaction.response.send_message("⚠️ Nachricht nicht gefunden.", ephemeral=True)
            return

        embed = msg.embeds[0]
        embed.color = discord.Color.red()
        embed.description = "🚫 **Dieses Giveaway wurde abgebrochen!**"
        await msg.edit(embed=embed, view=None)

        giveaway["beendet"] = True
        save_giveaways(data)
        await interaction.response.send_message("🛑 Giveaway wurde erfolgreich abgebrochen.", ephemeral=True)
        logger.warning(f"🛑 Giveaway {nachricht_id} abgebrochen durch {interaction.user}")

    # -----------------------------------------
    # ⏰ Automatische Beendigung
    # -----------------------------------------
    @tasks.loop(minutes=1)
    async def check_giveaways(self):
        data = load_giveaways()
        now = datetime.now(BERLIN_TZ)
        for msg_id, g in list(data.items()):
            if g["beendet"]:
                continue

            end_dt = datetime.fromisoformat(g["endzeit"]).astimezone(BERLIN_TZ)
            if now >= end_dt:
                guild_id = g["guild_id"]
                channel_id = load_settings().get(guild_id, {}).get("GIVEAWAY_CHANNEL_ID")
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    continue

                try:
                    msg = await channel.fetch_message(int(msg_id))
                except discord.NotFound:
                    continue

                teilnehmer = g.get("teilnehmer", [])
                embed = msg.embeds[0]

                if not teilnehmer:
                    embed.color = discord.Color.orange()
                    embed.description = "😕 Keine Teilnehmer – kein Gewinner!"
                    await msg.edit(embed=embed, view=None)
                    g["beendet"] = True
                    continue

                random.shuffle(teilnehmer)
                winners = teilnehmer[:g["gewinner"]]
                mentions = ", ".join(f"<@{u}>" for u in winners)

                embed.color = discord.Color.gold()
                embed.description = f"🎉 **Giveaway beendet!**\n\n**Gewinner:** {mentions}"
                await msg.edit(embed=embed, view=None)
                await channel.send(f"🎊 Glückwunsch an {mentions}! Ihr habt **{g['preis']}** gewonnen!")

                g["beendet"] = True
                logger.info(f"🏁 Giveaway {msg_id} beendet – Gewinner: {mentions}")

        save_giveaways(data)


# =============================================
# 🚀 Setup
# =============================================
async def setup(bot):
    await bot.add_cog(GiveawayCog(bot))
