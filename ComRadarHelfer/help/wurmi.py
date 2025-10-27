import discord
from discord import app_commands
from discord.ext import commands
from config import TEST_GUILD_ID
from utils.permissions import restricted_command


class fratz(help.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="fratz", description="fratz")
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))
    @restricted_command()
    async def fratz(self, interaction: discord.Interaction):
        await interaction.response.send_message("👣 Schick Fußbilder!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(fratz(bot))
