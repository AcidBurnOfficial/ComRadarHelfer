import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
from config import (
    TICKET_CATEGORY_ID,
    SCAMMER_ADMIN_CHANNEL_ID,
    SCAMMERHILFE_ADMIN_ROLE_ID,
    TICKET_LOG_CHANNEL_ID,
    TRANSCRIPT_CHANNEL_ID,
    TEST_GUILD_ID,
    TEAMS,
)
import io
import json
import os
from datetime import datetime

COUNTER_FILE = "data/ticket_counter.json"
os.makedirs("data", exist_ok=True)


# -------------------------------------------------
# 📁 Hilfsfunktionen für Ticketnummern
# -------------------------------------------------
def load_counters():
    if not os.path.exists(COUNTER_FILE):
        return {"ComRadar": 0, "Technischer Support": 0, "DSGVO": 0}
    with open(COUNTER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_counters(data):
    with open(COUNTER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


# -------------------------------------------------
# 🎫 Ticket-Erstellung
# -------------------------------------------------
async def create_ticket_channel(interaction: discord.Interaction, ticket_type: str, team_roles, *fields):
    guild = interaction.guild
    category = guild.get_channel(TICKET_CATEGORY_ID)

    if not category:
        await interaction.response.send_message("⚠️ Ticket-Kategorie wurde nicht gefunden!", ephemeral=True)
        return

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
    }

    for role_id in (team_roles if isinstance(team_roles, list) else [team_roles]):
        role = guild.get_role(role_id)
        if role:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

    # 🔢 Ticketnummern laden
    counters = load_counters()
    if ticket_type in ["ComRadar", "Technischer Support", "DSGVO"]:
        counters[ticket_type] = counters.get(ticket_type, 0) + 1
        save_counters(counters)
        channel_name = f"{ticket_type.lower()}-{counters[ticket_type]:03d}"
    else:
        channel_name = f"{ticket_type.lower()}-{interaction.user.name}".replace(" ", "-")

    # 💬 Channel erstellen (Topic = Ersteller)
    channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites,
        topic=f"Erstellt von {interaction.user.display_name} ({interaction.user.id})"
    )

    # 🧾 Ticketdaten
    field_text = "\n".join([f"**{q}:** {a}" for q, a in fields])
    ticket_info = f"**Erstellt von:** {interaction.user.mention}\n\n{field_text}"

    embed = discord.Embed(
        title=f"🎫 Neues Ticket – {ticket_type}",
        description=ticket_info,
        color=discord.Color.blurple(),
    )
    embed.set_footer(text=f"Erstellt am {datetime.now().strftime('%d.%m.%Y um %H:%M Uhr')}")

    await channel.send(embed=embed, view=CloseTicketView(interaction.user.id))
    

    # 📘 Ticket-Log (Erstellung)
    log_channel = guild.get_channel(TICKET_LOG_CHANNEL_ID)
    if log_channel:
        log_embed = discord.Embed(
            title="🆕 Neues Ticket erstellt",
            description=f"**Typ:** {ticket_type}\n**Name:** {channel.name}\n**Ersteller:** {interaction.user.display_name}",
            color=discord.Color.green(),
            timestamp=datetime.utcnow(),
        )
        await log_channel.send(embed=log_embed)

    await interaction.response.send_message(f"✅ Ticket erstellt: {channel.mention}", ephemeral=True)

    # 👮‍♂️ Wenn Scammerhilfe: Admin-Thread erstellen & Rolle pingen
    if "scammerhilfe" in ticket_type.lower():
        await create_admin_thread(interaction, ticket_type, embed, fields, channel)


# -------------------------------------------------
# 💬 Thread im Admin-Kanal für ScammerHilfe
# -------------------------------------------------
async def create_admin_thread(interaction, ticket_type, embed, fields, ticket_channel):
    guild = interaction.guild
    admin_channel = guild.get_channel(SCAMMER_ADMIN_CHANNEL_ID)
    admin_role = guild.get_role(SCAMMERHILFE_ADMIN_ROLE_ID)

    if not admin_channel:
        await interaction.followup.send("⚠️ Admin-Channel für ScammerHilfe nicht gefunden!", ephemeral=True)
        return

    thread = await admin_channel.create_thread(name=ticket_channel.name, auto_archive_duration=10080)

    admin_embed = discord.Embed(
        title=f"💸 ScammerHilfe – {ticket_channel.name}",
        description=f"**Erstellt von:** {interaction.user.mention}\n\n"
                    + "\n".join([f"**{q}:** {a}" for q, a in fields]),
        color=discord.Color.gold(),
    )
    admin_embed.add_field(name="🔗 Ticket-Link", value=f"{ticket_channel.mention}", inline=False)
    admin_embed.add_field(name="📌 Status", value="🟢 Offen", inline=False)
    admin_embed.set_footer(text="ScammerHilfe-Thread für Teammitglieder")

    view = StatusControlView(admin_embed)
    await thread.send(content=f"{admin_role.mention}" if admin_role else None, embed=admin_embed, view=view)


# -------------------------------------------------
# ❌ Ticket schließen & Transkript speichern
# -------------------------------------------------
class CloseTicketView(View):
    def __init__(self, author_id: int):
        super().__init__(timeout=None)
        self.author_id = author_id

    @discord.ui.button(label="✅ Ticket schließen", style=discord.ButtonStyle.danger)
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id and not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ Du darfst dieses Ticket nicht schließen.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        # 📜 Nachrichtenverlauf sammeln
        messages = []
        async for m in interaction.channel.history(limit=None, oldest_first=True):
            if m.author.bot and not m.content.startswith("📋"):
                continue
            ts = m.created_at.strftime("%d.%m.%Y %H:%M:%S")
            if m.content:
                messages.append(f"**[{ts}] {m.author.display_name}:** {m.content}")

        log_text = "\n".join(messages)
        if not log_text.strip():
            log_text = "*Keine Nachrichten gefunden.*"

        # 🧾 Transkript-Datei
        transcript_content = (
            f"# 🎫 Transkript: {interaction.channel.name}\n"
            f"**Erstellt von:** {interaction.channel.topic or 'Unbekannt'}\n"
            f"**Geschlossen von:** {interaction.user.display_name}\n"
            f"**Zeitpunkt:** {datetime.now().strftime('%d.%m.%Y um %H:%M Uhr')}\n\n"
            f"---\n{log_text}"
        )

        transcript_file = io.BytesIO(transcript_content.encode("utf-8"))
        transcript = discord.File(transcript_file, filename=f"{interaction.channel.name}.md")

        # 💾 In Transcript-Channel speichern
        transcript_channel = guild.get_channel(TRANSCRIPT_CHANNEL_ID)
        if transcript_channel:
            await transcript_channel.send(file=transcript)

        # 🪵 Log in TicketLog-Channel
        log_channel = guild.get_channel(TICKET_LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title="📁 Ticket geschlossen",
                description=f"**Ticket:** {interaction.channel.name}\n**Geschlossen von:** {interaction.user.display_name}",
                color=discord.Color.red(),
                timestamp=datetime.utcnow(),
            )
            await log_channel.send(embed=embed)

        # 📬 DM an Ersteller mit Transkript
        creator = guild.get_member(self.author_id)
        if creator:
            try:
                await creator.send(
                    embed=discord.Embed(
                        title="📁 Dein Ticket wurde geschlossen",
                        description=f"Hier ist dein Ticket-Transkript **{interaction.channel.name}**.",
                        color=discord.Color.orange(),
                    ),
                    file=discord.File(io.BytesIO(transcript_content.encode("utf-8")), filename=f"{interaction.channel.name}.md")
                )
            except discord.Forbidden:
                if log_channel:
                    await log_channel.send(f"⚠️ Konnte {creator.mention} keine DM senden.")

        await interaction.channel.delete()


# -------------------------------------------------
# 🔄 Status-Buttons für ScammerHilfe-Threads
# -------------------------------------------------
class StatusControlView(View):
    def __init__(self, embed: discord.Embed):
        super().__init__(timeout=None)
        self.embed = embed

    async def update_status(self, interaction, text, color):
        self.embed.set_field_at(1, name="📌 Status", value=text, inline=False)
        self.embed.color = color
        await interaction.response.edit_message(embed=self.embed, view=self)

    @discord.ui.button(label="🟢 Offen", style=discord.ButtonStyle.secondary)
    async def open_status(self, interaction, button):
        await self.update_status(interaction, "🟢 Offen", discord.Color.green())

    @discord.ui.button(label="💰 Entschädigt", style=discord.ButtonStyle.success)
    async def refunded_status(self, interaction, button):
        await self.update_status(interaction, "💰 Entschädigt", discord.Color.teal())

    @discord.ui.button(label="❌ Abgelehnt", style=discord.ButtonStyle.danger)
    async def denied_status(self, interaction, button):
        await self.update_status(interaction, "❌ Abgelehnt", discord.Color.red())

    @discord.ui.button(label="⏰ Keine Rückmeldung", style=discord.ButtonStyle.primary)
    async def no_response_status(self, interaction, button):
        await self.update_status(interaction, "⏰ Keine Rückmeldung", discord.Color.orange())


# -------------------------------------------------
# 🧩 Cog Registrierung
# -------------------------------------------------
class TicketSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ticketpanel", description="Zeigt das Ticket-Erstellungs-Panel.")
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))
    async def ticket_panel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎟 Ticket-System",
            description="Wähle eine Kategorie, um ein Ticket zu eröffnen:",
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed, view=TicketSelectView(interaction.guild))


# -------------------------------------------------
# 🎛 Auswahlmenü für Ticket-Kategorien
# -------------------------------------------------
class TicketSelectView(View):
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=None)
        for team_name, role_ids in TEAMS.items():
            button = Button(label=team_name, style=discord.ButtonStyle.primary)

            async def callback(interaction, name=team_name, roles=role_ids):
                if name == "ScammerHilfe":
                    await interaction.response.send_modal(ScammerHelpModal(roles))
                elif name == "ComRadar":
                    await interaction.response.send_modal(ComRadarModal(roles))
                elif name == "Technischer Support":
                    await interaction.response.send_modal(TechSupportModal(roles))
                elif name == "DSGVO":
                    await interaction.response.send_modal(DSGVOModal(roles))
                elif name == "GU":
                    await interaction.response.send_modal(GUModal(roles))
                else:
                    await interaction.response.send_message("❌ Keine Kategorie definiert.", ephemeral=True)

            button.callback = callback
            self.add_item(button)


# -------------------------------------------------
# 📋 Modal-Formulare
# -------------------------------------------------
class ScammerHelpModal(Modal, title="💸 ScammerHilfe"):
    def __init__(self, roles): super().__init__(); self.roles = roles
    name = TextInput(label="Dein Minecraft-Name", required=True)
    scammer = TextInput(label="Von wem wurdest du gescammt?", required=True)
    betrag = TextInput(label="Um welchen Betrag wurdest du gescammt?", required=True)
    details = TextInput(label="Was genau ist passiert?", style=discord.TextStyle.paragraph, required=True)
    async def on_submit(self, i): await create_ticket_channel(i, "ScammerHilfe", self.roles,
        ("Minecraft-Name", self.name.value), ("Scammer", self.scammer.value), ("Betrag", self.betrag.value), ("Details", self.details.value))


class ComRadarModal(Modal, title="📡 ComRadar"):
    def __init__(self, roles): super().__init__(); self.roles = roles
    topic = TextInput(label="Worum geht es bei deiner Anfrage?", required=True)
    details = TextInput(label="Beschreibe dein Anliegen genauer:", style=discord.TextStyle.paragraph, required=True)
    async def on_submit(self, i): await create_ticket_channel(i, "ComRadar", self.roles,
        ("Thema", self.topic.value), ("Beschreibung", self.details.value))


class TechSupportModal(Modal, title="🧑‍💻 Technischer Support"):
    def __init__(self, roles): super().__init__(); self.roles = roles
    issue = TextInput(label="Was funktioniert nicht?", required=True)
    details = TextInput(label="Beschreibe dein technisches Problem:", style=discord.TextStyle.paragraph, required=True)
    async def on_submit(self, i): await create_ticket_channel(i, "Technischer Support", self.roles,
        ("Problem", self.issue.value), ("Details", self.details.value))


class DSGVOModal(Modal, title="🧾 DSGVO-Anfrage"):
    def __init__(self, roles): super().__init__(); self.roles = roles
    request = TextInput(label="Welche Datenanfrage möchtest du stellen?", required=True)
    details = TextInput(label="Beschreibe dein Anliegen:", style=discord.TextStyle.paragraph, required=True)
    async def on_submit(self, i): await create_ticket_channel(i, "DSGVO", self.roles,
        ("Anfrage", self.request.value), ("Details", self.details.value))


class GUModal(Modal, title="🧾 GrieferUnze-Anfrage"):
    def __init__(self, roles): super().__init__(); self.roles = roles
    request = TextInput(label="Um welches Netzwerk handelt es sich?", required=True)
    details = TextInput(label="Beschreibe dein Anliegen:", style=discord.TextStyle.paragraph, required=True)
    async def on_submit(self, i): await create_ticket_channel(i, "GU", self.roles,
        ("Anfrage", self.request.value), ("Details", self.details.value))

# -------------------------------------------------
# ⚙️ Setup für load_extension
# -------------------------------------------------
async def setup(bot):
    await bot.add_cog(TicketSystem(bot))
