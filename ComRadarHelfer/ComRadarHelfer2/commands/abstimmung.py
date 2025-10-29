# =============================================
# 📂 Einstellungen & Konstanten
# =============================================
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Modal, TextInput
import aiohttp
import os
import json
from datetime import datetime

GUILD_SETTINGS_FILE = "data/guild_settings.json"
ABSTIMMUNGEN_FILE = "data/abstimmungen.json"
os.makedirs("data", exist_ok=True)

# -------------------------
# JSON load/save helpers
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

# -------------------------
# UUID helper
# -------------------------
async def get_uuid(name: str) -> str | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.mojang.com/users/profiles/minecraft/{name}") as resp:
                if resp.status == 200:
                    j = await resp.json()
                    return j.get("id")
    except Exception:
        pass
    return None

# =============================================
# 🧾 Abstimmung Modal
# =============================================
class AbstimmungModal(Modal, title="🧾 Neue Abstimmung"):
    def __init__(self):
        super().__init__(timeout=None)
        self.beschuldigter = TextInput(label="Beschuldigter Spieler", required=True)
        self.geschaedigter = TextInput(label="Geschädigter Spieler", required=True)
        self.netzwerk = TextInput(label="Netzwerk (1.8 / Cloud)", required=True)
        self.schaden = TextInput(label="Schadenshöhe", required=True)
        self.link = TextInput(label="Forumlink / Quelle", required=True)
        for field in [self.beschuldigter, self.geschaedigter, self.netzwerk, self.schaden, self.link]:
            self.add_item(field)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild_id = str(interaction.guild.id)

        # Lade serverabhängige IDs
        guild_settings = load_json(GUILD_SETTINGS_FILE).get(guild_id, {})
        vote_channel_id = guild_settings.get("COMRADAR_VOTE_CHANNEL_ID")
        voting_channel_id = guild_settings.get("COMRADAR_VOTING_CHANNEL_ID")
        tag_offen_id = guild_settings.get("TAG_OFFEN_ID")

        forum_channel = interaction.guild.get_channel(vote_channel_id)
        voting_channel = interaction.guild.get_channel(voting_channel_id)
        if not forum_channel or not voting_channel:
            await interaction.followup.send("❌ Forum- oder Voting-Kanal nicht gefunden.", ephemeral=True)
            return

        beschuldigter = self.beschuldigter.value.strip()
        uuid = await get_uuid(beschuldigter)

        # Tags optional anwenden
        applied_tags = []
        try:
            for tag in getattr(forum_channel, "available_tags", []):
                if getattr(tag, "id", None) == tag_offen_id:
                    applied_tags = [tag]
                    break
        except Exception:
            applied_tags = []

        # Thread erstellen
        try:
            thread_obj = await forum_channel.create_thread(
                name=beschuldigter,
                content=(
                    f"**Beschuldigter:** {beschuldigter}\n"
                    f"**Geschädigter:** {self.geschaedigter.value}\n"
                    f"**Netzwerk:** {self.netzwerk.value}\n"
                    f"**Schaden:** {self.schaden.value}\n"
                    f"**Forumlink:** {self.link.value}\n"
                    f"**UUID:** `{uuid or 'Unbekannt'}`"
                ),
                applied_tags=applied_tags or None,
                auto_archive_duration=10080
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Fehler beim Erstellen der Abstimmung: {e}", ephemeral=True)
            return

        # Starter-Message ermitteln
        starter_message = None
        try:
            async for m in thread_obj.history(limit=1, oldest_first=True):
                starter_message = m
                break
        except Exception:
            starter_message = None

        # Reaktionen auf Forum-Message
        if starter_message:
            for emoji in ("🔴", "🟠", "🟢"):
                try:
                    await starter_message.add_reaction(emoji)
                except Exception:
                    continue

        # Öffentliche Nachricht im Voting-Channel posten
        embed = discord.Embed(
            title=f"🧾 Neue Abstimmung: {beschuldigter}",
            description=(
                f"**Geschädigter:** {self.geschaedigter.value}\n"
                f"**Netzwerk:** {self.netzwerk.value}\n"
                f"**Schaden:** {self.schaden.value}\n"
                f"**Forumlink:** {self.link.value}\n\n"
                f"🔴 **Schuldig:** 0\n🟠 **Enthaltung:** 0\n🟢 **Unschuldig:** 0"
            ),
            color=discord.Color.gold(),
        )
        embed.set_footer(text=f"UUID: {uuid or 'Unbekannt'} • Erstellt am {datetime.utcnow().strftime('%d.%m.%Y %H:%M Uhr')}")
        public_msg = await voting_channel.send(embed=embed)

        # Speichern
        daten = load_json(ABSTIMMUNGEN_FILE)
        daten.append({
            "guild_id": guild_id,
            "beschuldigter": beschuldigter,
            "uuid": uuid or "Unbekannt",
            "thread_id": thread_obj.id if thread_obj else None,
            "starter_message_id": starter_message.id if starter_message else None,
            "public_msg_id": public_msg.id,
            "created_at": datetime.utcnow().isoformat()
        })
        save_json(ABSTIMMUNGEN_FILE, daten)
        await interaction.followup.send(f"✅ Abstimmung zu **{beschuldigter}** wurde gestartet!", ephemeral=True)

# =============================================
# 🛰️ Cog: Multi-Guild Abstimmungen
# =============================================
class Abstimmung(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="abstimmung", description="Startet eine neue Abstimmung im ComRadar-System.")
    async def abstimmung(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        guild_settings = load_json(GUILD_SETTINGS_FILE).get(guild_id, {})
        if not any(r.id == guild_settings.get("ADMIN_ROLE_IDS") for r in interaction.user.roles):
            await interaction.response.send_message("❌ Nur Admins dürfen diesen Befehl verwenden.", ephemeral=True)
            return
        await interaction.response.send_modal(AbstimmungModal())

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        await self._handle_reaction_change(payload)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        await self._handle_reaction_change(payload)

    async def _handle_reaction_change(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
        daten = load_json(ABSTIMMUNGEN_FILE)
        eintrag = next((e for e in daten if e.get("starter_message_id") == payload.message_id or e.get("thread_id") == payload.channel_id), None)
        if not eintrag:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        # Channel und Message
        try:
            channel = guild.get_channel(payload.channel_id) or await guild.fetch_channel(payload.channel_id)
            msg = await channel.fetch_message(payload.message_id)
        except Exception:
            msg = None

        if msg is None and eintrag.get("thread_id") and eintrag.get("starter_message_id"):
            try:
                thread_channel = guild.get_channel(eintrag["thread_id"]) or await guild.fetch_channel(eintrag["thread_id"])
                if thread_channel:
                    msg = await thread_channel.fetch_message(eintrag["starter_message_id"])
            except Exception:
                msg = None
        if msg is None:
            return

        # Zähle Reaktionen
        counts = {"🔴": 0, "🟠": 0, "🟢": 0}
        try:
            for reaction in msg.reactions:
                emoji = str(reaction.emoji)
                if emoji in counts:
                    counts[emoji] = max(reaction.count - (1 if self.bot.user in await reaction.users().flatten() else 0), 0)
        except Exception:
            pass

        # Update Public Embed
        try:
            public_channel_id = eintrag.get("public_channel_id") or load_json(GUILD_SETTINGS_FILE).get(str(payload.guild_id), {}).get("COMRADAR_VOTING_CHANNEL_ID")
            public_channel = guild.get_channel(public_channel_id) or await guild.fetch_channel(public_channel_id)
            public_msg = await public_channel.fetch_message(eintrag["public_msg_id"])
            embed = public_msg.embeds[0]
            lines = embed.description.splitlines()
            for i, line in enumerate(lines):
                if line.startswith("🔴"):
                    lines[i] = f"🔴 **Schuldig:** {counts['🔴']}"
                elif line.startswith("🟠"):
                    lines[i] = f"🟠 **Enthaltung:** {counts['🟠']}"
                elif line.startswith("🟢"):
                    lines[i] = f"🟢 **Unschuldig:** {counts['🟢']}"
            embed.description = "\n".join(lines)
            await public_msg.edit(embed=embed)
        except Exception as e:
            print(f"[Sync] Fehler beim Updaten des öffentlichen Embeds: {e}")


# -----------------------------------------
# ⚙️ Setup
# -----------------------------------------
async def setup(bot):
    await bot.add_cog(Abstimmung(bot))
