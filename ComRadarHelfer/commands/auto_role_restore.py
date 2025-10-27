import discord
from discord.ext import commands
import json
import os
from datetime import datetime

from config import LOG_CHANNEL_ID, JOIN_LOG_CHANNEL_ID

BACKUP_FILE = "data/roles_backup.json"  # Datei zum Speichern der Rollen


# -------------------------------------------------
# Hilfsfunktionen für JSON-Handling
# -------------------------------------------------
def load_backups():
    """Lädt gespeicherte Rollen-Backups aus JSON."""
    if not os.path.exists(BACKUP_FILE):
        return {}
    try:
        with open(BACKUP_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        print("[WARNUNG] roles_backup.json war beschädigt – neue Datei wird erstellt.")
        return {}


def save_backups(data):
    """Speichert Rollen-Backups als JSON."""
    os.makedirs("data", exist_ok=True)
    with open(BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# -------------------------------------------------
# Cog: Auto Role Restore
# -------------------------------------------------
class AutoRoleRestore(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # -------------------------------------------------
    # Hilfsfunktion: Goldenes Log-Embed
    # -------------------------------------------------
    def create_embed(self, title, description, color, member, field_name=None, field_value=None):
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.utcnow()
        )
        embed.set_author(name=f"{member} ({member.id})", icon_url=member.display_avatar.url)
        embed.set_footer(text="📜 ComRadar AutoRoleRestore")
        if field_name and field_value:
            embed.add_field(name=field_name, value=field_value, inline=False)
        return embed

    async def send_log(self, embed, join_log=False):
        """Sendet das Embed in den passenden Log-Kanal."""
        channel_id = JOIN_LOG_CHANNEL_ID if join_log else LOG_CHANNEL_ID
        if not channel_id:
            return
        channel = self.bot.get_channel(channel_id)
        if channel:
            await channel.send(embed=embed)

    # -------------------------------------------------
    # 📤 Member verlässt den Server
    # -------------------------------------------------
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.bot:
            return

        backups = load_backups()
        role_ids = [role.id for role in member.roles if role.name != "@everyone"]

        if role_ids:
            backups[str(member.id)] = {
                "roles": role_ids,
                "timestamp": datetime.utcnow().isoformat()
            }
            save_backups(backups)

            # Logging im JOIN_LOG_CHANNEL
            roles_text = ", ".join([r.name for r in member.roles if r.name != "@everyone"]) or "Keine Rollen"
            embed = self.create_embed(
                "📤 Mitglied hat den Server verlassen",
                f"{member.mention} (`{member.id}`)",
                discord.Color.orange(),
                member,
                field_name="Gespeicherte Rollen",
                field_value=roles_text
            )
            await self.send_log(embed, join_log=True)

    # -------------------------------------------------
    # 🔁 Member tritt erneut bei
    # -------------------------------------------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return

        backups = load_backups()
        data = backups.get(str(member.id))

        if not data:
            return

        restored = []
        for role_id in data.get("roles", []):
            role = member.guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role, reason="Rollen automatisch wiederhergestellt")
                    restored.append(role.name)
                except discord.Forbidden:
                    continue

        if restored:
            embed = self.create_embed(
                "🔁 Mitglied ist zurückgekehrt",
                f"{member.mention} (`{member.id}`)",
                discord.Color.green(),
                member,
                field_name="Wiederhergestellte Rollen",
                field_value=", ".join(restored)
            )
            await self.send_log(embed, join_log=True)

        # Eintrag löschen, um doppelte Wiederherstellung zu vermeiden
        backups.pop(str(member.id), None)
        save_backups(backups)


# -------------------------------------------------
# Setup-Funktion für das Cog
# -------------------------------------------------
async def setup(bot):
    await bot.add_cog(AutoRoleRestore(bot))
