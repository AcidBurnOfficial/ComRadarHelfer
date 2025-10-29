import discord
from discord import app_commands
from discord.ext import commands
from utils.permissions import restricted_command

# =============================================
# 📂 Mittelsmann-Regeln
# =============================================
class mm(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="mm", description="Regel bezüglich MM-Dienste.")
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))
    @restricted_command()
    async def mm(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚠️ Wichtige Regeln zur Scammerhilfe",
            description=(
                "🔸 **Jegliche Art von Mittelsmann-Diensten wird nicht entschädigt. Der Mittelsmann gewährleistet dem Spieler freiwillig einen sicheren Handel. Eine Erstattung würde hier ein falsches Signal senden. Niemand ist verpflichtet, Mittelsmann-Dienste anzubieten, und jeder sollte sich der Risiken eines Scams bewusst sein.**\n\n"
                "⚖️ **Allgemein gilt:** Entschädigungen durch das CommunityRadar- bzw. Scammerhilfe-Team "
                "sind **freiwillige Leistungen**. Es besteht **kein Anspruch auf eine Entschädigung.**"
            ),
            color=discord.Color.gold()
        )

        embed.set_footer(text="Bitte beachte diese Regeln.")
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(mm(bot))
