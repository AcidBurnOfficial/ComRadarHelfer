# =============================================
# 📂 Einstellungen & Konstanten
# =============================================
import discord
from discord.ext import commands
import datetime
import io
import os
import json

GUILD_SETTINGS_FILE = "data/guild_settings.json"
os.makedirs("data", exist_ok=True)

# -------------------------
# JSON Load/Save helper
# -------------------------
def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    os.makedirs(os.path.dirname(path) or "data", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# =============================================
# 📝 AuditLogger Cog
# =============================================
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
    # 🔔 Nachricht an richtigen Kanal schicken (pro Guild)
    # ---------------------------------------------------------
    async def send_log(self, guild_id: int, embed, file=None, join_log=False):
        guild_settings = load_json(GUILD_SETTINGS_FILE).get(str(guild_id), {})
        channel_id = guild_settings.get("JOIN_LOG_CHANNEL_ID" if join_log else "LOG_CHANNEL_ID")
        if not channel_id:
            return
        channel = self.bot.get_guild(guild_id).get_channel(channel_id)
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
        await self.send_log(member.guild.id, embed, join_log=True)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        embed = self.create_log_embed(
            "🚪 Mitglied hat den Server verlassen",
            f"{member.mention} hat den Server verlassen.",
            member,
        )
        await self.send_log(member.guild.id, embed, join_log=True)

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
            await self.send_log(after.guild.id, embed)

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
            # Warnung: Benutzer kann in mehreren Guilds sein, hier pro Guild loggen
            for guild in self.bot.guilds:
                if guild.get_member(after.id):
                    await self.send_log(guild.id, embed)

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
            f"**Autor:** {message.author.mention}\n**Kanal:** {message.channel.mention}",
            message.author,
        )
        file = None
        if len(text_content) > 1000:
            log_bytes = io.BytesIO(text_content.encode("utf-8"))
            file = discord.File(log_bytes, filename=f"deleted_message_{message.id}.txt")
            embed.add_field(name="📎 Hinweis", value="Nachricht war zu lang – siehe Datei.", inline=False)
        else:
            embed.add_field(name="📝 Inhalt", value=text_content, inline=False)
        await self.send_log(message.guild.id, embed, file=file)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if after.author.bot or before.content == after.content:
            return
        before_text = before.content or "*Leer*"
        after_text = after.content or "*Leer*"
        embed = self.create_log_embed(
            "✏️ Nachricht bearbeitet",
            f"**Autor:** {after.author.mention}\n**Kanal:** {after.channel.mention}",
            after.author,
        )
        file = None
        if len(before_text + after_text) > 1000:
            combined_text = "===== Vorher =====\n" + before_text + "\n\n===== Nachher =====\n" + after_text
            log_bytes = io.BytesIO(combined_text.encode("utf-8"))
            file = discord.File(log_bytes, filename=f"edited_message_{after.id}.txt")
            embed.add_field(name="📎 Hinweis", value="Nachricht war zu lang – siehe Datei.", inline=False)
        else:
            embed.add_field(name="📝 Vorher", value=before_text, inline=False)
            embed.add_field(name="📝 Nachher", value=after_text, inline=False)
        await self.send_log(after.guild.id, embed, file=file)

    # ---------------------------------------------------------
    # 🧱 KANÄLE
    # ---------------------------------------------------------
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        embed = self.create_log_embed(
            "➕ Kanal erstellt",
            f"**Name:** {channel.mention}\n**Typ:** {channel.type}",
        )
        await self.send_log(channel.guild.id, embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        embed = self.create_log_embed(
            "❌ Kanal gelöscht",
            f"**Name:** #{channel.name}\n**Typ:** {channel.type}",
        )
        await self.send_log(channel.guild.id, embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        if before.name != after.name:
            embed = self.create_log_embed(
                "✏️ Kanal umbenannt",
                f"**Vorher:** #{before.name}\n**Nachher:** #{after.name}",
            )
            await self.send_log(after.guild.id, embed)


# ---------------------------------------------------------
# ⚙️ Setup
# ---------------------------------------------------------
async def setup(bot):
    if "AuditLogger" in bot.cogs:
        bot.remove_cog("AuditLogger")
    await bot.add_cog(AuditLogger(bot))
