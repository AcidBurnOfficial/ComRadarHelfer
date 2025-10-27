import discord
from discord import app_commands
from discord.ext import commands
from config import TEST_GUILD_ID
from utils.permissions import restricted_command


class gluecksspiel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="gluecksspiel", description="Regel bezüglich Glückspiel.")
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))
    @restricted_command()
    async def gluecksspiel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚠️ Wichtige Regeln zur Scammerhilfe",
            description=(
                "🔸 **Jegliche Art von Glücksspiel** wird von unserem Team **ohne Ausnahme abgelehnt.**\n\n"
                "⚖️ **Allgemein gilt:** Entschädigungen durch das CommunityRadar- bzw. Scammerhilfe-Team "
                "sind **freiwillige Leistungen**. Es besteht **kein Anspruch auf eine Entschädigung.**"
            ),
            color=discord.Color.gold()
        )

        embed.set_footer(text="Bitte beachte diese Regeln.")
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(gluecksspiel(bot))
