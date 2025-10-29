import discord
from discord import app_commands
from discord.ext import commands
from utils.permissions import restricted_command

# =============================================
# 📂 Leihgabe-Regeln
# =============================================
class leihgabe(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="leihgabe", description="Regel bezüglich Leihgaben.")
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))
    @restricted_command()
    async def leihgabe(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚠️ Wichtige Regeln zur Scammerhilfe",
            description=(
                "🔸 **Jegliche Art von Leihgaben sieht unser Team als Eigenverschulden an und wird ausnahmslos abgelehnt.**\n\n"
                "⚖️ **Allgemein gilt:** Entschädigungen durch das CommunityRadar- bzw. Scammerhilfe-Team "
                "sind **freiwillige Leistungen**. Es besteht **kein Anspruch auf eine Entschädigung.**"
            ),
            color=discord.Color.gold()
        )

        embed.set_footer(text="Bitte beachte diese Regeln.")
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(leihgabe(bot))
