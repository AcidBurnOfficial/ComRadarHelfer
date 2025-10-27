# abstimmung.py
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Modal, TextInput
import aiohttp
import os
import json
from datetime import datetime
from config import (
    COMRADAR_VOTE_CHANNEL_ID,
    COMRADAR_VOTING_CHANNEL_ID,
    ADMIN_ROLE_IDS,
    TAG_OFFEN_ID,
    TEST_GUILD_ID,
)

ABSTIMMUNGEN_FILE = "data/abstimmungen.json"
os.makedirs("data", exist_ok=True)


# -------------------------
# Helper: JSON load/save
# -------------------------
def _load_abstimmungen():
    try:
        if not os.path.exists(ABSTIMMUNGEN_FILE):
            return []
        with open(ABSTIMMUNGEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_abstimmungen(data):
    os.makedirs(os.path.dirname(ABSTIMMUNGEN_FILE) or "data", exist_ok=True)
    with open(ABSTIMMUNGEN_FILE, "w", encoding="utf-8") as f:
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


# -------------------------
# Modal
# -------------------------
class AbstimmungModal(Modal, title="🧾 Neue Abstimmung"):
    def __init__(self):
        super().__init__(timeout=None)
        self.beschuldigter = TextInput(label="Beschuldigter Spieler", required=True)
        self.geschaedigter = TextInput(label="Geschädigter Spieler", required=True)
        self.netzwerk = TextInput(label="Netzwerk (1.8 / Cloud)", required=True)
        self.schaden = TextInput(label="Schadenshöhe", required=True)
        self.link = TextInput(label="Forumlink / Quelle", required=True)

        for field in [
            self.beschuldigter,
            self.geschaedigter,
            self.netzwerk,
            self.schaden,
            self.link,
        ]:
            self.add_item(field)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        beschuldigter = self.beschuldigter.value.strip()
        uuid = await get_uuid(beschuldigter)
        guild = interaction.guild

        forum_channel = guild.get_channel(COMRADAR_VOTE_CHANNEL_ID)
        voting_channel = guild.get_channel(COMRADAR_VOTING_CHANNEL_ID)

        if not forum_channel or not voting_channel:
            await interaction.followup.send("❌ Forum- oder Voting-Kanal nicht gefunden.", ephemeral=True)
            return

        # Tag-Objekt optional ermitteln
        applied_tags = []
        try:
            for tag in getattr(forum_channel, "available_tags", []):
                if getattr(tag, "id", None) == TAG_OFFEN_ID:
                    applied_tags = [tag]
                    break
        except Exception:
            applied_tags = []

        # Erstelle Thread und halte Starter-Message sauber fest
        try:
            created = await forum_channel.create_thread(
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
                auto_archive_duration=10080,
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Fehler beim Erstellen der Abstimmung: {e}", ephemeral=True)
            return

        # Normalerweise ist 'created' ein Thread-Objekt, aber verschiedene discord.py-Versionen
        # können unterschiedliche Wrapps zurückgeben. Finde Thread und Starter-Message robust.
        thread_obj = None
        starter_message = None

        # 1) Wenn create_thread ein Thread-Objekt zurückgibt
        if isinstance(created, discord.Thread):
            thread_obj = created

        # 2) Wenn Wrapper enthält direkte message/thread props
        if thread_obj is None:
            thread_obj = getattr(created, "thread", None) or getattr(created, "thread_obj", None)

        # 3) Fallback: suche Thread im forum_channel anhand Name (letzte Threads)
        if thread_obj is None:
            try:
                for t in forum_channel.threads:
                    if t.name == beschuldigter:
                        thread_obj = t
                        break
            except Exception:
                thread_obj = None

        # 4) Versuche Starter-Nachricht zu holen (erste Nachricht im Thread)
        if thread_obj is not None:
            try:
                # neuere discord.py erlaubt thread_obj.fetch_message(starter_id) oder history
                async for m in thread_obj.history(limit=1, oldest_first=True):
                    starter_message = m
                    break
            except Exception:
                # letzter Versuch: some wrappers expose .message or .starter_message
                starter_message = getattr(created, "message", None) or getattr(created, "starter_message", None)

        # setze Reaktionen falls Starter-Message vorhanden
        if starter_message:
            try:
                for emoji in ("🔴", "🟠", "🟢"):
                    await starter_message.add_reaction(emoji)
            except Exception as e:
                print(f"[WARN] Konnte Forum-Reaktionen nicht hinzufügen: {e}")
        else:
            print("[WARN] Starter-Nachricht nicht gefunden — Forum-Reaktionen nicht gesetzt.")

        # Öffentliches (anonyme) Embed im Voting-Channel posten
        embed = discord.Embed(
            title=f"🧾 Neue Abstimmung: {beschuldigter}",
            color=discord.Color.gold(),
            description=(
                f"**Geschädigter:** {self.geschaedigter.value}\n"
                f"**Netzwerk:** {self.netzwerk.value}\n"
                f"**Schaden:** {self.schaden.value}\n"
                f"**Forumlink:** {self.link.value}\n\n"
                f"🔴 **Schuldig:** 0\n🟠 **Enthaltung:** 0\n🟢 **Unschuldig:** 0"
            ),
        )
        embed.set_footer(
            text=f"UUID: {uuid or 'Unbekannt'} • Erstellt am {datetime.now().strftime('%d.%m.%Y %H:%M Uhr')}"
        )

        public_msg = await voting_channel.send(embed=embed)

        # Speichere mapping: thread_id + starter_message_id + public_msg_id
        thread_id_to_store = getattr(thread_obj, "id", None)
        starter_msg_id_to_store = getattr(starter_message, "id", None)

        daten = _load_abstimmungen()
        daten.append(
            {
                "beschuldigter": beschuldigter,
                "uuid": uuid or "Unbekannt",
                "thread_id": thread_id_to_store,
                "starter_message_id": starter_msg_id_to_store,
                "public_msg_id": public_msg.id,
                "created_at": datetime.utcnow().isoformat(),
            }
        )
        _save_abstimmungen(daten)

        await interaction.followup.send(f"✅ Abstimmung zu **{beschuldigter}** wurde gestartet!", ephemeral=True)


# -------------------------
# Cog: Live-Sync Listener
# -------------------------
class Abstimmung(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="abstimmung", description="Startet eine neue Abstimmung im ComRadar-System.")
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))
    async def abstimmung(self, interaction: discord.Interaction):
        if not any(r.id == ADMIN_ROLE_IDS for r in interaction.user.roles):
            await interaction.response.send_message("❌ Nur Admins dürfen diesen Befehl verwenden.", ephemeral=True)
            return
        await interaction.response.send_modal(AbstimmungModal())

    # raw add/remove decken wir ab (funktioniert auch wenn Nachricht nicht im Cache ist)
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        await self._handle_reaction_change(payload)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        await self._handle_reaction_change(payload)

    async def _handle_reaction_change(self, payload: discord.RawReactionActionEvent):
        # ignore bot
        if payload.user_id == self.bot.user.id:
            return

        daten = _load_abstimmungen()

        # 1) Versuche matching per starter_message_id (zuverlässig)
        eintrag = next((e for e in daten if e.get("starter_message_id") == payload.message_id), None)

        # 2) Falls nicht gefunden, fall back auf thread_id == payload.channel_id
        if eintrag is None:
            eintrag = next((e for e in daten if e.get("thread_id") == payload.channel_id), None)

        if not eintrag:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        # Bestimme Kanal in dem die Reaction passiert ist
        try:
            channel = guild.get_channel(payload.channel_id)
            # falls channel None, ggf fetch channel
            if channel is None:
                channel = await guild.fetch_channel(payload.channel_id)
        except Exception:
            channel = None

        # Hole die betroffene Nachricht: bevorzugt payload.message_id
        msg = None
        try:
            if channel and payload.message_id:
                msg = await channel.fetch_message(payload.message_id)
        except Exception:
            msg = None

        # Falls msg nicht gefunden, aber wir haben starter_message_id & thread_id, versuche fetch im thread
        if msg is None and eintrag.get("starter_message_id") and eintrag.get("thread_id"):
            try:
                thread_channel = guild.get_channel(eintrag["thread_id"])
                if thread_channel is None:
                    thread_channel = await guild.fetch_channel(eintrag["thread_id"])
                if thread_channel:
                    msg = await thread_channel.fetch_message(eintrag["starter_message_id"])
            except Exception:
                msg = None

        # Wenn wir immer noch keine Message haben -> abort
        if msg is None:
            return

        # Zähle die 3 Emojis von dieser Nachricht
        counts = {"🔴": 0, "🟠": 0, "🟢": 0}
        try:
            for reaction in msg.reactions:
                emoji = str(reaction.emoji)
                if emoji in counts:
                    # -1 um Bot-Account falls vorhanden
                    counts[emoji] = max(reaction.count - (1 if self.bot.user in await reaction.users().flatten() else 0), 0)
        except Exception:
            # fallback: falls reaction.users() nicht verfügbar, nutze reaction.count-1 ungeprüft
            try:
                for reaction in msg.reactions:
                    emoji = str(reaction.emoji)
                    if emoji in counts:
                        counts[emoji] = max(reaction.count - 1, 0)
            except Exception:
                pass

        # Update public message
        try:
            guild_obj = self.bot.get_guild(payload.guild_id)
            public_channel = guild_obj.get_channel(COMRADAR_VOTING_CHANNEL_ID)
            if public_channel is None:
                public_channel = await guild_obj.fetch_channel(COMRADAR_VOTING_CHANNEL_ID)
            public_msg = await public_channel.fetch_message(eintrag["public_msg_id"])
            embed = public_msg.embeds[0]
            # replace the three lines starting with the emojis
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


async def setup(bot):
    await bot.add_cog(Abstimmung(bot))
