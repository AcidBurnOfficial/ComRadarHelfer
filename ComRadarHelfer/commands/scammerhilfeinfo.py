import discord
from discord import app_commands
from discord.ext import commands
from config import TEST_GUILD_ID
from utils.permissions import restricted_command


class scammerhilfeinfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="scammerhilfeinfo", description="Zeigt wichtige Regeln zur Scammerhilfe.")
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))
    @restricted_command()
    async def scammerhilfeinfo(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚠️ Wichtige Regeln zur Scammerhilfe",
            description=(
                "Bitte **lies dir diese Regeln sorgfältig durch**, bevor du dich an das Team wendest.\n\n"
                "🔸 **Jegliche Art von Glücksspiel** wird von unserem Team **ohne Ausnahme abgelehnt.**\n\n"
                "🔸 **Leihgaben** gelten als **Eigenverschulden** und werden **nicht entschädigt.**\n\n"
                "🔸 **Scams über Drittplattformen** (z. B. Discord, Telegram, etc.) "
                "werden **nicht bearbeitet**, da unser Team **nur Scams auf der Cloud oder 1.8.9** behandelt, "
                "bei denen es um **Ingame-Werte gegen Ingame-Geld** ging.\n\n"
                "🔸 **Mittelsmann-Dienste** werden **nicht entschädigt.** "
                "Ein Mittelsmann handelt freiwillig und trägt das Risiko selbst. "
                "Eine Erstattung würde hier ein falsches Signal senden.\n\n"
                "⚖️ **Allgemein gilt:** Entschädigungen durch das CommunityRadar- bzw. Scammerhilfe-Team "
                "sind **freiwillige Leistungen**. Es besteht **kein Anspruch auf eine Entschädigung.**"
            ),
            color=discord.Color.gold()
        )

        embed.set_footer(text="Bitte beachte diese Regeln.")
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(scammerhilfeinfo(bot))
