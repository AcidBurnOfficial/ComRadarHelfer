import discord
from discord import app_commands
from discord.ext import commands
from config import TEST_GUILD_ID
from utils.permissions import restricted_command


class Drittplattform(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="drittplattform", description="Zeigt die Regel bezüglich Drittplattformen an.")
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))
    @restricted_command()
    async def drittplattform(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚠️ Wichtige Regeln zur Scammerhilfe",
            description=(
                "🔸 **Solltest du über Drittplattformen gescammt worden sein, wird auch hier nichts entschädigt.**\n"
                "Unser Team kümmert sich ausschließlich um Fälle, die **auf der Cloud oder 1.8.9** stattgefunden haben, "
                "und bei denen **Ingame-Werte gegen Ingame-Gelder** getauscht wurden.\n\n"
                "⚖️ **Allgemein gilt:** Entschädigungen durch das CommunityRadar- bzw. Scammerhilfe-Team "
                "sind **freiwillige Leistungen**. Es besteht **kein Anspruch auf eine Entschädigung.**"
            ),
            color=discord.Color.gold()
        )

        embed.set_author(name="ComRadar Regelwerk")
        embed.set_footer(text="📜 Bitte beachte diese Richtlinie.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Drittplattform(bot))
