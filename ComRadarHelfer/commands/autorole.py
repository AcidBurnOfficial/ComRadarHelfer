import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from config import AUTO_ROLE_IDS, ADMIN_ROLE_IDS, SUPPORT_ROLE_IDS, LOG_CHANNEL_ID, JOIN_LOG_CHANNEL_ID


class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # -------------------------------------------------
    # 🔆 Einheitliches goldenes Log-Embed
    # -------------------------------------------------
    def create_embed(self, title, description, color, user=None, field_name=None, field_value=None):
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.utcnow()
        )
        if user:
            embed.set_author(name=f"{user} ({user.id})", icon_url=user.display_avatar.url)
        embed.set_footer(text="📜 ComRadar AutoRole")
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
    # 🪪 Automatische Rollenvergabe beim Beitritt
    # -------------------------------------------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot or not AUTO_ROLE_IDS:
            return

        roles = [member.guild.get_role(rid) for rid in AUTO_ROLE_IDS]
        roles = [r for r in roles if r is not None]

        if not roles:
            return

        try:
            await member.add_roles(*roles, reason="Automatische Rollenvergabe beim Beitritt")
            role_names = ", ".join([r.name for r in roles])
            embed = self.create_embed(
                "🆕 Neuer Beitritt – Rollen vergeben",
                f"{member.mention} hat automatisch folgende Rollen erhalten:",
                discord.Color.gold(),
                member,
                field_name="Vergebene Rollen",
                field_value=role_names
            )
            await self.send_log(embed, join_log=True)
            print(f"✅ {member} hat automatisch Rollen erhalten: {role_names}")
        except discord.Forbidden:
            print(f"⚠️ Keine Berechtigung, um Rollen an {member} zu vergeben.")

    # -------------------------------------------------
    # 🛡️ Prüfen ob Admin oder Support
    # -------------------------------------------------
    def is_team_member(self, member: discord.Member):
        team_roles = set(ADMIN_ROLE_IDS + SUPPORT_ROLE_IDS)
        return any(role.id in team_roles for role in member.roles) or member.guild_permissions.administrator

    # -------------------------------------------------
    # ➕ Slash Command: Rolle hinzufügen
    # -------------------------------------------------
    @app_commands.command(name="role_add", description="Fügt einem Mitglied eine Rolle hinzu (Admin/Support).")
    async def role_add(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        if not self.is_team_member(interaction.user):
            await interaction.response.send_message("❌ Du hast keine Berechtigung für diesen Befehl.", ephemeral=True)
            return

        try:
            await member.add_roles(role, reason=f"Manuell von {interaction.user}")
            embed = self.create_embed(
                "✅ Rolle hinzugefügt",
                f"{member.mention} hat nun die Rolle **{role.name}**.",
                discord.Color.gold(),
                interaction.user
            )
            await interaction.response.send_message(embed=embed)

            log_embed = self.create_embed(
                "📋 Rollenänderung (Hinzufügen)",
                f"**Rolle:** {role.mention}\n**Benutzer:** {member.mention}\n**Durchgeführt von:** {interaction.user.mention}",
                discord.Color.gold(),
                interaction.user
            )
            await self.send_log(log_embed)

        except discord.Forbidden:
            await interaction.response.send_message("⚠️ Ich habe keine Berechtigung, um diese Rolle zu vergeben.", ephemeral=True)

    # -------------------------------------------------
    # ➖ Slash Command: Rolle entfernen
    # -------------------------------------------------
    @app_commands.command(name="role_remove", description="Entfernt eine Rolle von einem Mitglied (Admin/Support).")
    async def role_remove(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        if not self.is_team_member(interaction.user):
            await interaction.response.send_message("❌ Du hast keine Berechtigung für diesen Befehl.", ephemeral=True)
            return

        try:
            await member.remove_roles(role, reason=f"Manuell von {interaction.user}")
            embed = self.create_embed(
                "🧹 Rolle entfernt",
                f"Die Rolle **{role.name}** wurde von {member.mention} entfernt.",
                discord.Color.red(),
                interaction.user
            )
            await interaction.response.send_message(embed=embed)

            log_embed = self.create_embed(
                "📋 Rollenänderung (Entfernt)",
                f"**Rolle:** {role.mention}\n**Benutzer:** {member.mention}\n**Entfernt von:** {interaction.user.mention}",
                discord.Color.red(),
                interaction.user
            )
            await self.send_log(log_embed)

        except discord.Forbidden:
            await interaction.response.send_message("⚠️ Ich habe keine Berechtigung, um diese Rolle zu entfernen.", ephemeral=True)


# -------------------------------------------------
# Setup-Funktion für das Cog
# -------------------------------------------------
async def setup(bot):
    await bot.add_cog(AutoRole(bot))
