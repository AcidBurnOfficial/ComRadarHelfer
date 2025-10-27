import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
from config import TEST_GUILD_ID
import json
import os

# Lade Umgebungsvariablen
from dotenv import load_dotenv
load_dotenv()

LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", 0))  # Logchannel ID aus .env

DATA_FILE = "data/modactions.json"

# -------------------------------------------------
# Hilfsfunktionen
# -------------------------------------------------
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    os.makedirs("data", exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def has_mod_permissions(interaction: discord.Interaction) -> bool:
    roles = [r.name.lower() for r in interaction.user.roles]
    return any(r in roles for r in ["admin", "support"])

async def log_action(guild: discord.Guild, title: str, description: str):
    if LOG_CHANNEL_ID:
        channel = guild.get_channel(LOG_CHANNEL_ID)
        if channel:
            embed = discord.Embed(title=title, description=description, color=discord.Color.gold(), timestamp=datetime.utcnow())
            await channel.send(embed=embed)

def add_modlog_entry(user_id: int, action: str, moderator_id: int, reason: str, duration: str = None):
    data = load_data()
    entry = {
        "action": action,
        "reason": reason,
        "moderator": moderator_id,
        "timestamp": datetime.utcnow().isoformat(),
        "duration": duration
    }
    data.setdefault(str(user_id), []).append(entry)
    save_data(data)

# -------------------------------------------------
# Moderations-Cog
# -------------------------------------------------
class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ----------------------------------------------
    # Timeout Command
    # ----------------------------------------------
    @app_commands.command(name="timeout", description="Setzt einen Benutzer für eine bestimmte Zeit auf Timeout.")
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, stunden: int, grund: str):
        if not has_mod_permissions(interaction):
            return await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)
        
        until = datetime.utcnow() + timedelta(hours=stunden)
        await member.timeout(until, reason=grund)
        add_modlog_entry(member.id, "Timeout", interaction.user.id, grund, f"{stunden} Stunden")

        embed = discord.Embed(title="⏱️ Timeout", color=discord.Color.orange(), timestamp=datetime.utcnow())
        embed.add_field(name="Benutzer", value=member.mention, inline=True)
        embed.add_field(name="Dauer", value=f"{stunden} Stunden", inline=True)
        embed.add_field(name="Grund", value=grund, inline=False)
        embed.set_footer(text=f"Von {interaction.user}")
        await interaction.response.send_message(embed=embed)
        await log_action(interaction.guild, "⏱️ Timeout gesetzt", f"{member.mention} wurde von {interaction.user.mention} getimeoutet.")

    # ----------------------------------------------
    # Kick Command
    # ----------------------------------------------
    @app_commands.command(name="kick", description="Kickt einen Benutzer vom Server.")
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))
    async def kick(self, interaction: discord.Interaction, member: discord.Member, grund: str):
        if not has_mod_permissions(interaction):
            return await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)

        await member.kick(reason=grund)
        add_modlog_entry(member.id, "Kick", interaction.user.id, grund)

        embed = discord.Embed(title="👢 Kick", color=discord.Color.red(), timestamp=datetime.utcnow())
        embed.add_field(name="Benutzer", value=member.mention, inline=True)
        embed.add_field(name="Grund", value=grund, inline=False)
        embed.set_footer(text=f"Von {interaction.user}")
        await interaction.response.send_message(embed=embed)
        await log_action(interaction.guild, "👢 Kick", f"{member.mention} wurde von {interaction.user.mention} gekickt.")

    # ----------------------------------------------
    # Ban Command
    # ----------------------------------------------
    @app_commands.command(name="ban", description="Bannt einen Benutzer vom Server.")
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))
    async def ban(self, interaction: discord.Interaction, member: discord.Member, grund: str):
        if not has_mod_permissions(interaction):
            return await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)

        await member.ban(reason=grund)
        add_modlog_entry(member.id, "Ban", interaction.user.id, grund)

        embed = discord.Embed(title="⛔ Ban", color=discord.Color.dark_red(), timestamp=datetime.utcnow())
        embed.add_field(name="Benutzer", value=member.mention, inline=True)
        embed.add_field(name="Grund", value=grund, inline=False)
        embed.set_footer(text=f"Von {interaction.user}")
        await interaction.response.send_message(embed=embed)
        await log_action(interaction.guild, "⛔ Ban", f"{member.mention} wurde von {interaction.user.mention} gebannt.")

    # ----------------------------------------------
    # Unban Command
    # ----------------------------------------------
    @app_commands.command(name="unban", description="Entbannt einen Benutzer anhand seiner ID.")
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))
    async def unban(self, interaction: discord.Interaction, user_id: str):
        if not has_mod_permissions(interaction):
            return await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)

        user = await self.bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        add_modlog_entry(user.id, "Unban", interaction.user.id, "Manuell entbannt")

        embed = discord.Embed(title="✅ Unban", description=f"{user.mention} wurde entbannt.", color=discord.Color.green())
        embed.timestamp = datetime.utcnow()
        embed.set_footer(text=f"Von {interaction.user}")
        await interaction.response.send_message(embed=embed)
        await log_action(interaction.guild, "✅ Unban", f"{user.mention} wurde von {interaction.user.mention} entbannt.")

    # ----------------------------------------------
    # Warnsystem
    # ----------------------------------------------
    @app_commands.command(name="warn", description="Verwarnt einen Benutzer und speichert die Verwarnung.")
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))
    async def warn(self, interaction: discord.Interaction, member: discord.Member, grund: str):
        if not has_mod_permissions(interaction):
            return await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)

        data = load_data()
        entry = {
            "action": "Warn",
            "reason": grund,
            "moderator": interaction.user.id,
            "timestamp": datetime.utcnow().isoformat()
        }
        data.setdefault(str(member.id), []).append(entry)
        save_data(data)

        warnings = len([a for a in data[str(member.id)] if a["action"] == "Warn"])

        embed = discord.Embed(
            title="⚠️ Verwarnung ausgesprochen",
            description=f"{member.mention} wurde verwarnt.\n**Grund:** {grund}\n**Verwarnungen:** {warnings}",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        await interaction.response.send_message(embed=embed)
        await log_action(interaction.guild, "⚠️ Warnung", f"{member.mention} wurde von {interaction.user.mention} verwarnt. Grund: {grund} (Insgesamt {warnings})")

        # Eskalationsstufen
        if warnings == 3:
            until = datetime.utcnow() + timedelta(hours=24)
            await member.timeout(until, reason="Automatischer 24h-Mute nach 3 Verwarnungen.")
            add_modlog_entry(member.id, "Auto-Mute (24h)", interaction.user.id, "3 Verwarnungen erreicht", "24 Stunden")
            await log_action(interaction.guild, "⏱️ Automatischer Mute", f"{member.mention} wurde automatisch für 24h gemutet (3 Verwarnungen).")
        elif warnings == 4:
            await member.kick(reason="Automatischer Kick nach 4 Verwarnungen.")
            add_modlog_entry(member.id, "Auto-Kick", interaction.user.id, "4 Verwarnungen erreicht")
            await log_action(interaction.guild, "🚫 Automatischer Kick", f"{member.mention} wurde automatisch gekickt (4 Verwarnungen).")
        elif warnings >= 5:
            await member.ban(reason="Automatischer Ban nach 5 Verwarnungen.")
            add_modlog_entry(member.id, "Auto-Ban", interaction.user.id, "5 Verwarnungen erreicht")
            await log_action(interaction.guild, "⛔ Automatischer Ban", f"{member.mention} wurde automatisch gebannt (5 Verwarnungen).")

    # ----------------------------------------------
    # Verwarnungen löschen
    # ----------------------------------------------
    @app_commands.command(name="clearwarns", description="Löscht alle Verwarnungen eines Benutzers.")
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))
    async def clearwarns(self, interaction: discord.Interaction, member: discord.Member):
        if not has_mod_permissions(interaction):
            return await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)

        data = load_data()
        if str(member.id) in data:
            before = len(data[str(member.id)])
            data[str(member.id)] = [a for a in data[str(member.id)] if a["action"] != "Warn"]
            after = len(data[str(member.id)])
            save_data(data)

            embed = discord.Embed(
                title="🧹 Verwarnungen gelöscht",
                description=f"Alle Verwarnungen von {member.mention} wurden entfernt.\n**Vorher:** {before} → **Nachher:** {after}",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            await interaction.response.send_message(embed=embed)
            await log_action(interaction.guild, "🧹 Warnungen gelöscht", f"{interaction.user.mention} hat alle Verwarnungen von {member.mention} gelöscht.")
        else:
            await interaction.response.send_message("ℹ️ Keine Verwarnungen gefunden.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Moderation(bot))
