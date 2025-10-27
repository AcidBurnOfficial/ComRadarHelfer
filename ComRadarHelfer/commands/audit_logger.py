import discord
from discord.ext import commands
import datetime
import io
import os

LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", 0))
JOIN_LOG_CHANNEL_ID = int(os.getenv("JOIN_LOG_CHANNEL_ID", 0))


class AuditLogger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------------------------------------------------------
    # 🪶 Embed-Erstellung mit goldenem Design
    # ---------------------------------------------------------
    def create_log_embed(self, title, description, user=None, color=0xD4AF37):
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.datetime.utcnow(),
        )
        if user:
            try:
                embed.set_author(name=f"{user} ({user.id})", icon_url=user.display_avatar.url)
            except Exception:
                embed.set_author(name=f"{user} ({user.id})")
        embed.set_footer(text="📜 ComRadar Logsystem")
        return embed

    # ---------------------------------------------------------
    # 🔔 Nachricht an richtigen Kanal schicken
    # ---------------------------------------------------------
    async def send_log(self, embed, file=None, join_log=False):
        channel_id = JOIN_LOG_CHANNEL_ID if join_log else LOG_CHANNEL_ID
        if not channel_id:
            return
        channel = self.bot.get_channel(channel_id)
        if channel:
            await channel.send(embed=embed, file=file)

    # ---------------------------------------------------------
    # 👋 MEMBER JOIN / REMOVE
    # ---------------------------------------------------------
    @commands.Cog.listener()
    async def on_member_join(self, member):
        embed = self.create_log_embed(
            "👋 Mitglied beigetreten",
            f"{member.mention} ist dem Server beigetreten.\n"
            f"Account erstellt: <t:{int(member.created_at.timestamp())}:R>",
            member,
        )
        await self.send_log(embed, join_log=True)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        embed = self.create_log_embed(
            "🚪 Mitglied hat den Server verlassen",
            f"{member.mention} hat den Server verlassen.",
            member,
        )
        await self.send_log(embed, join_log=True)

    # ---------------------------------------------------------
    # 🔄 NAMEN / ROLLENÄNDERUNG
    # ---------------------------------------------------------
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        changes = []

        # Nickname geändert
        if before.nick != after.nick:
            changes.append(f"**Nickname:** `{before.nick}` → `{after.nick}`")

        # Rollenänderung
        if before.roles != after.roles:
            before_roles = set(before.roles)
            after_roles = set(after.roles)
            added = after_roles - before_roles
            removed = before_roles - after_roles

            if added:
                added_list = ", ".join(r.mention for r in added)
                changes.append(f"**Hinzugefügt:** {added_list}")
            if removed:
                removed_list = ", ".join(r.mention for r in removed)
                changes.append(f"**Entfernt:** {removed_list}")

        if changes:
            embed = self.create_log_embed(
                "🧩 Mitglied aktualisiert",
                "\n".join(changes),
                after,
            )
            await self.send_log(embed)

    # ---------------------------------------------------------
    # 🖼️ AVATAR ÄNDERUNG
    # ---------------------------------------------------------
    @commands.Cog.listener()
    async def on_user_update(self, before, after):
        if before.avatar != after.avatar:
            embed = self.create_log_embed(
                "🖼️ Avatar geändert",
                f"{after.mention} hat seinen Avatar geändert.",
                after,
            )
            try:
                embed.set_thumbnail(url=before.display_avatar.url)
                embed.set_image(url=after.display_avatar.url)
            except Exception:
                pass
            await self.send_log(embed)

    # ---------------------------------------------------------
    # 💬 NACHRICHTEN (mit Textdatei bei langen Logs)
    # ---------------------------------------------------------
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot:
            return

        text_content = message.content or "*Keine Nachricht*"
        embed = self.create_log_embed(
            "🗑️ Nachricht gelöscht",
            f"**Autor:** {message.author.mention}\n"
            f"**Kanal:** {message.channel.mention}\n",
            message.author,
        )

        file = None
        if len(text_content) > 1000:
            log_bytes = io.BytesIO(text_content.encode("utf-8"))
            file = discord.File(log_bytes, filename=f"deleted_message_{message.id}.txt")
            embed.add_field(name="📎 Hinweis", value="Nachricht war zu lang – siehe Datei.", inline=False)
        else:
            embed.add_field(name="📝 Inhalt", value=text_content, inline=False)

        await self.send_log(embed, file=file)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if after.author.bot or before.content == after.content:
            return

        before_text = before.content or "*Leer*"
        after_text = after.content or "*Leer*"

        embed = self.create_log_embed(
            "✏️ Nachricht bearbeitet",
            f"**Autor:** {after.author.mention}\n"
            f"**Kanal:** {after.channel.mention}\n",
            after.author,
        )

        file = None
        if len(before_text + after_text) > 1000:
            combined_text = (
                "===== Vorher =====\n" + before_text +
                "\n\n===== Nachher =====\n" + after_text
            )
            log_bytes = io.BytesIO(combined_text.encode("utf-8"))
            file = discord.File(log_bytes, filename=f"edited_message_{after.id}.txt")
            embed.add_field(name="📎 Hinweis", value="Nachricht war zu lang – siehe Datei.", inline=False)
        else:
            embed.add_field(name="📝 Vorher", value=before_text, inline=False)
            embed.add_field(name="📝 Nachher", value=after_text, inline=False)

        await self.send_log(embed, file=file)

    # ---------------------------------------------------------
    # 🧱 KANÄLE
    # ---------------------------------------------------------
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        embed = self.create_log_embed(
            "➕ Kanal erstellt",
            f"**Name:** {channel.mention}\n**Typ:** {channel.type}",
        )
        await self.send_log(embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        embed = self.create_log_embed(
            "❌ Kanal gelöscht",
            f"**Name:** #{channel.name}\n**Typ:** {channel.type}",
        )
        await self.send_log(embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        if before.name != after.name:
            embed = self.create_log_embed(
                "✏️ Kanal umbenannt",
                f"**Vorher:** #{before.name}\n**Nachher:** #{after.name}",
            )
            await self.send_log(embed)


# ---------------------------------------------------------
# Setup – ohne doppelte Registrierung
# ---------------------------------------------------------
async def setup(bot):
    # Falls bereits geladen, entfernen (verhindert Reload-Fehler)
    if "AuditLogger" in bot.cogs:
        bot.remove_cog("AuditLogger")

    await bot.add_cog(AuditLogger(bot))
