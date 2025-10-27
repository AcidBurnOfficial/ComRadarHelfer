# ==========================================
# 🗳️ ComRadar – Wahlen & Nominierungen (Button-basiert)
# ==========================================
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import os, json, csv
from datetime import datetime
from config import (
    TEST_GUILD_ID,
    COMRADAR_NOMINIERUNG_CHANNEL_ID,
    COMRADAR_WAHLEN_CHANNEL_ID,
    COMRADAR_WAHLERGEBNISSE_CHANNEL_ID,
    ADMIN_ROLE_IDS,
    DATA_PATH,
)

# ------------------------------------------
# ⚙️ Konstanten & Pfade
# ------------------------------------------
DATA_FILE = os.path.join(DATA_PATH, "comradar_wahlen.json")

# ------------------------------------------
# 📁 Datenspeicherung
# ------------------------------------------
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

        public_channel = guild.get_channel(COMRADAR_WAHLEN_CHANNEL_ID)
        result_channel = guild.get_channel(COMRADAR_WAHLERGEBNISSE_CHANNEL_ID)
        if not public_channel or not result_channel:
            return await interaction.followup.send("❌ Ein Kanal wurde nicht gefunden.", ephemeral=True)

        # Initial Embed
        embed = discord.Embed(
            title=f"Nominierung: {mc}",
            description=(
                f"**MC-Name:** `{mc}`\n"
                f"**DC-Name:** `{dc}`\n\n"
                f"**Ja:** 0\n"
                f"**Nein:** 0"
            ),
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow(),
        )
        embed.set_footer(text="Anonyme Abstimmung")

        # Buttons
        view = VotingView(self.cog)
        public_msg = await public_channel.send(embed=embed, view=view)

        # Admin-Embed
        mirror_embed = discord.Embed(
            title=f"[Admin] Nominierung: {mc}",
            description=(
                f"**MC-Name:** `{mc}`\n"
                f"**DC-Name:** `{dc}`\n"
                f"**Nominiert von:** {author.mention}\n\n"
                f"**Ja (0):** —\n**Nein (0):** —"
            ),
            color=discord.Color.gold(),
            timestamp=datetime.utcnow(),
        )
        mirror_msg = await result_channel.send(embed=mirror_embed)

        # Speichern
        data = load_data()
        data.append({
            "mc_name": mc,
            "dc_name": dc,
            "nominator_id": author.id,
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

    # --------------------------------------
    # /wahlen Command
    # --------------------------------------
    @app_commands.command(name="wahlen", description="Erstellt das Nominierungs-Panel (Admin).")
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))
    async def wahlen(self, interaction: discord.Interaction):
        if not any(r.id == ADMIN_ROLE_IDS for r in interaction.user.roles):
            return await interaction.response.send_message("❌ Nur Admins dürfen das.", ephemeral=True)
        channel = interaction.guild.get_channel(COMRADAR_NOMINIERUNG_CHANNEL_ID)
        if not channel:
            return await interaction.response.send_message("❌ Kanal nicht gefunden.", ephemeral=True)
        view = NominatePanel(self)
        await channel.send("📢 **Nominierungen** – Drücke auf **Nominieren**, um dich einzutragen:", view=view)
        await interaction.response.send_message("✅ Wahl-Panel erstellt.", ephemeral=True)

    # --------------------------------------
    # Stimmen verarbeiten
    # --------------------------------------
    async def handle_vote(self, interaction: discord.Interaction, vote_type: str):
        user_id = interaction.user.id
        data = load_data()
        for entry in data:
            if interaction.message.id == entry["public_msg_id"]:
                if vote_type == "reset":
                    entry["voters"]["yes"] = [u for u in entry["voters"]["yes"] if u != user_id]
                    entry["voters"]["no"] = [u for u in entry["voters"]["no"] if u != user_id]
                else:
                    # Alte Stimme löschen
                    for vt in ("yes", "no"):
                        if vt != vote_type and user_id in entry["voters"][vt]:
                            entry["voters"][vt].remove(user_id)
                    # Neue Stimme setzen
                    if user_id not in entry["voters"][vote_type]:
                        entry["voters"][vote_type].append(user_id)
                save_data(data)
                await self.update_votes(entry)
                await interaction.response.send_message("✅ Stimme gezählt!", ephemeral=True)
                break

    # --------------------------------------
    # Embeds aktualisieren
    # --------------------------------------
    async def update_votes(self, entry):
        public_channel = self.bot.get_channel(entry["public_channel_id"])
        mirror_channel = self.bot.get_channel(entry["mirror_channel_id"])
        public_msg = await public_channel.fetch_message(entry["public_msg_id"])
        mirror_msg = await mirror_channel.fetch_message(entry["mirror_msg_id"])

        yes_count = len(entry["voters"]["yes"])
        no_count = len(entry["voters"]["no"])

        # Public Embed
        public_embed = discord.Embed(
            title=f"Nominierung: {entry['mc_name']}",
            description=(
                f"**MC-Name:** `{entry['mc_name']}`\n"
                f"**DC-Name:** `{entry['dc_name']}`\n\n"
            ),
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow(),
        )
        public_embed.set_footer(text="Anonyme Abstimmung")
        await public_msg.edit(embed=public_embed)

        # Admin Embed
        yes_names = [ (self.bot.get_user(u) or await self.bot.fetch_user(u)).mention for u in entry["voters"]["yes"] ]
        no_names  = [ (self.bot.get_user(u) or await self.bot.fetch_user(u)).mention for u in entry["voters"]["no"] ]

        mirror_embed = discord.Embed(
            title=f"[Admin] Nominierung: {entry['mc_name']}",
            description=(
                f"**MC-Name:** `{entry['mc_name']}`\n"
                f"**DC-Name:** `{entry['dc_name']}`\n"
                f"**Nominiert von:** <@{entry['nominator_id']}>\n\n"
                f"**Ja ({yes_count}):** {', '.join(yes_names) or '—'}\n"
                f"**Nein ({no_count}):** {', '.join(no_names) or '—'}"
            ),
            color=discord.Color.gold(),
            timestamp=datetime.utcnow(),
        )
        await mirror_msg.edit(embed=mirror_embed)

    # --------------------------------------
    # CSV Export
    # --------------------------------------
    @app_commands.command(name="export_wahlen", description="Exportiert alle Wahldaten als CSV (Admin).")
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))
    async def export_wahlen(self, interaction: discord.Interaction):
        if not any(r.id == ADMIN_ROLE_IDS for r in interaction.user.roles):
            return await interaction.response.send_message("❌ Nur Admins dürfen das.", ephemeral=True)

        data = load_data()
        if not data:
            return await interaction.response.send_message("⚠️ Keine Wahldaten gefunden.", ephemeral=True)

        os.makedirs(DATA_PATH, exist_ok=True)
        csv_path = os.path.join(DATA_PATH, "comradar_wahlen.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["MC-Name", "DC-Name", "Nominator ID", "Ja-Stimmen", "Nein-Stimmen"])
            for entry in data:
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
