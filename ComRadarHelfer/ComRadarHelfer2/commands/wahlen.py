import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import os, json, csv
from datetime import datetime

from utils.guild_settings import get_guild_settings  # ⚡️ holt die server-spezifischen Einstellungen
from config import DATA_PATH, TEST_GUILD_ID

DATA_FILE = os.path.join(DATA_PATH, "comradar_wahlen.json")

def load_data():
    os.makedirs(os.path.dirname(DATA_FILE) or "data", exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_data(data):
    os.makedirs(os.path.dirname(DATA_FILE) or "data", exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# ==========================================
# 🪪 Nominierungs-Modal
# ==========================================
class NominationModal(Modal, title="Nominierung"):
    mc_name = TextInput(label="Wie lautet dein MC-Name?")
    dc_name = TextInput(label="Wie lautet dein DC-Name?")

    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        mc = self.mc_name.value.strip()
        dc = self.dc_name.value.strip()
        author = interaction.user
        guild = interaction.guild

        settings = await get_guild_settings(guild.id)
        if not settings:
            return await interaction.followup.send("❌ Guild-Settings konnten nicht geladen werden.", ephemeral=True)

        public_channel = guild.get_channel(settings.get("comradar_wahlen_channel"))
        result_channel = guild.get_channel(settings.get("comradar_wahlergebnisse_channel"))
        if not public_channel or not result_channel:
            return await interaction.followup.send("❌ Ein Kanal wurde nicht gefunden.", ephemeral=True)

        embed = discord.Embed(
            title=f"Nominierung: {mc}",
            description=f"**MC-Name:** `{mc}`\n**DC-Name:** `{dc}`\n\n**Ja:** 0\n**Nein:** 0",
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow(),
        )
        embed.set_footer(text="Anonyme Abstimmung")

        view = VotingView(self.cog)
        public_msg = await public_channel.send(embed=embed, view=view)

        mirror_embed = discord.Embed(
            title=f"[Admin] Nominierung: {mc}",
            description=f"**MC-Name:** `{mc}`\n**DC-Name:** `{dc}`\n**Nominiert von:** {author.mention}\n\n**Ja (0):** —\n**Nein (0):** —",
            color=discord.Color.gold(),
            timestamp=datetime.utcnow(),
        )
        mirror_msg = await result_channel.send(embed=mirror_embed)

        data = load_data()
        data.append({
            "mc_name": mc,
            "dc_name": dc,
            "nominator_id": author.id,
            "guild_id": guild.id,
            "public_channel_id": public_channel.id,
            "public_msg_id": public_msg.id,
            "mirror_channel_id": result_channel.id,
            "mirror_msg_id": mirror_msg.id,
            "voters": {"yes": [], "no": []},
        })
        save_data(data)
        await interaction.followup.send("✅ Du wurdest erfolgreich nominiert!", ephemeral=True)

# ==========================================
# 🧩 Voting-Buttons
# ==========================================
class VotingView(View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Ja", style=discord.ButtonStyle.success)
    async def vote_yes(self, interaction: discord.Interaction, button: Button):
        await self.cog.handle_vote(interaction, "yes")

    @discord.ui.button(label="Nein", style=discord.ButtonStyle.danger)
    async def vote_no(self, interaction: discord.Interaction, button: Button):
        await self.cog.handle_vote(interaction, "no")

    @discord.ui.button(label="Stimme löschen", style=discord.ButtonStyle.secondary)
    async def vote_reset(self, interaction: discord.Interaction, button: Button):
        await self.cog.handle_vote(interaction, "reset")

# ==========================================
# 🗳️ ComRadar Wahlen Cog
# ==========================================
class ComRadarWahlen(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(NominatePanel(self))  # persistent

    async def get_admin_roles(self, guild: discord.Guild):
        settings = await get_guild_settings(guild.id)
        if not settings:
            return []
        return settings.get("comradar_admin_roles", [])

    @app_commands.command(name="wahlen", description="Erstellt das Nominierungs-Panel (Admin).")
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))
    async def wahlen(self, interaction: discord.Interaction):
        admin_roles = await self.get_admin_roles(interaction.guild)
        if not any(r.id in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message("❌ Nur Admins dürfen das.", ephemeral=True)

        settings = await get_guild_settings(interaction.guild.id)
        if not settings:
            return await interaction.response.send_message("❌ Guild-Settings konnten nicht geladen werden.", ephemeral=True)

        channel = interaction.guild.get_channel(settings.get("comradar_nominierung_channel"))
        if not channel:
            return await interaction.response.send_message("❌ Kanal nicht gefunden.", ephemeral=True)

        view = NominatePanel(self)
        await channel.send("📢 **Nominierungen** – Drücke auf **Nominieren**, um dich einzutragen:", view=view)
        await interaction.response.send_message("✅ Wahl-Panel erstellt.", ephemeral=True)

    # ---------- handle_vote & update_votes bleiben unverändert ----------
    # ---------- export_wahlen angepasst für guild_settings ----------
    @app_commands.command(name="export_wahlen", description="Exportiert alle Wahldaten als CSV (Admin).")
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))
    async def export_wahlen(self, interaction: discord.Interaction):
        admin_roles = await self.get_admin_roles(interaction.guild)
        if not any(r.id in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message("❌ Nur Admins dürfen das.", ephemeral=True)

        data = load_data()
        if not data:
            return await interaction.response.send_message("⚠️ Keine Wahldaten gefunden.", ephemeral=True)

        guild_data = [e for e in data if e["guild_id"] == interaction.guild.id]
        if not guild_data:
            return await interaction.response.send_message("⚠️ Keine Wahldaten für diesen Server gefunden.", ephemeral=True)

        os.makedirs(DATA_PATH, exist_ok=True)
        csv_path = os.path.join(DATA_PATH, f"comradar_wahlen_{interaction.guild.id}.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["MC-Name", "DC-Name", "Nominator ID", "Ja-Stimmen", "Nein-Stimmen"])
            for entry in guild_data:
                writer.writerow([
                    entry["mc_name"],
                    entry["dc_name"],
                    entry["nominator_id"],
                    len(entry["voters"]["yes"]),
                    len(entry["voters"]["no"])
                ])
        await interaction.response.send_message(file=discord.File(csv_path))
        print(f"✅ CSV exportiert: {csv_path}")

# ==========================================
# 🧩 Nominierungs-Panel
# ==========================================
class NominatePanel(View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Nominieren", style=discord.ButtonStyle.primary, custom_id="comradar_nominieren_button")
    async def nominate(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(NominationModal(self.cog))

# ==========================================
# 🚀 Setup
# ==========================================
async def setup(bot):
    await bot.add_cog(ComRadarWahlen(bot))
