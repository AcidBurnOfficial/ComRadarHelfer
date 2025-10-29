import discord
from discord import app_commands
from discord.ext import commands
from utils.guild_config import load_settings, save_settings

class Setup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="setup",
        description="⚙️ Konfiguriere die Channels und Rollen für diesen Server."
    )
    @app_commands.describe(
        giveaway_channel="Kanal für tägliche Gewinnspiele",
        quiz_channel="Kanal für Quizfragen",
        admin_role="Admin-Rolle mit Bot-Verwaltungsrechten"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_command(
        self,
        interaction: discord.Interaction,
        giveaway_channel: discord.TextChannel = None,
        quiz_channel: discord.TextChannel = None,
        admin_role: discord.Role = None,
    ):
        guild = interaction.guild
        guild_id = str(guild.id)

        settings = load_settings()
        if guild_id not in settings:
            settings[guild_id] = {
                "server_name": guild.name,
                "giveaway_channel": None,
                "quiz_channel": None,
                "admin_roles": []
            }

        # Änderungen übernehmen
        if giveaway_channel:
            settings[guild_id]["giveaway_channel"] = giveaway_channel.id
        if quiz_channel:
            settings[guild_id]["quiz_channel"] = quiz_channel.id
        if admin_role:
            if admin_role.id not in settings[guild_id]["admin_roles"]:
                settings[guild_id]["admin_roles"].append(admin_role.id)

        save_settings(settings)

        # Rückmeldung
        embed = discord.Embed(
            title=f"✅ Setup abgeschlossen für {guild.name}",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Giveaway-Channel",
            value=f"<#{settings[guild_id]['giveaway_channel']}>" if settings[guild_id]['giveaway_channel'] else "❌ Nicht gesetzt",
            inline=False
        )
        embed.add_field(
            name="Quiz-Channel",
            value=f"<#{settings[guild_id]['quiz_channel']}>" if settings[guild_id]['quiz_channel'] else "❌ Nicht gesetzt",
            inline=False
        )
        embed.add_field(
            name="Admin-Rollen",
            value=", ".join([f"<@&{r}>" for r in settings[guild_id]["admin_roles"]]) or "❌ Keine Rollen",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Optional: Befehl, um die aktuelle Konfiguration anzuzeigen
    @app_commands.command(
        name="setup_info",
        description="📋 Zeigt die aktuelle Bot-Konfiguration für diesen Server an."
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_info(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        settings = load_settings()
        guild_data = settings.get(guild_id)

        if not guild_data:
            await interaction.response.send_message(
                "❌ Dieser Server ist noch nicht konfiguriert. Verwende `/setup`, um zu starten.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"📋 Aktuelle Konfiguration – {guild_data['server_name']}",
            color=discord.Color.blurple()
        )
        embed.add_field(
            name="Giveaway-Channel",
            value=f"<#{guild_data['giveaway_channel']}>" if guild_data["giveaway_channel"] else "❌ Nicht gesetzt",
            inline=False
        )
        embed.add_field(
            name="Quiz-Channel",
            value=f"<#{guild_data['quiz_channel']}>" if guild_data["quiz_channel"] else "❌ Nicht gesetzt",
            inline=False
        )
        embed.add_field(
            name="Admin-Rollen",
            value=", ".join([f"<@&{r}>" for r in guild_data["admin_roles"]]) or "❌ Keine Rollen",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Setup(bot))
