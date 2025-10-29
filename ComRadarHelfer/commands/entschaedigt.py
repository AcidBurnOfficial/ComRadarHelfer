import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Modal, TextInput
import aiohttp
import os, json
from datetime import datetime

DATA_FILE = "data/entschaedigungen.json"
ABSTIMMUNGEN_FILE = "data/abstimmungen.json"
GUILD_SETTINGS_FILE = "data/guild_settings.json"
UUID_API = "https://griefer.info/community-radar/uuid-by-name?name="

# ---------------------------
# Hilfsfunktionen
# ---------------------------
def load_guild_settings():
    if not os.path.exists(GUILD_SETTINGS_FILE):
        return {}
    try:
        with open(GUILD_SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Warn] Fehler beim Laden von guild_settings.json: {e}")
        return {}

def get_guild_setting(guild_id: int, key: str, default=None):
    guild_data = load_guild_settings().get(str(guild_id), {})
    return guild_data.get(key, default)

async def fetch_uuid(name: str):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(UUID_API + name) as resp:
                if resp.status == 200:
                    j = await resp.json()
                    uuid = j.get("uuid")
                    if uuid:
                        uuid = uuid.replace("-", "")
                        return f"{uuid[:8]}-{uuid[8:12]}-{uuid[12:16]}-{uuid[16:20]}-{uuid[20:]}"
        except Exception:
            pass
        try:
            async with session.get(f"https://api.mojang.com/users/profiles/minecraft/{name}") as resp:
                if resp.status == 200:
                    j = await resp.json()
                    uuid = j.get("id")
                    if uuid:
                        uuid = uuid.replace("-", "")
                        return f"{uuid[:8]}-{uuid[8:12]}-{uuid[12:16]}-{uuid[16:20]}-{uuid[20:]}"
        except Exception:
            pass
    return None

def load_json(file_path):
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return list(data.values())
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        print(f"[Warn] Fehler beim Laden von {file_path}: {e}")
        return []

def save_data(data):
    os.makedirs(os.path.dirname(DATA_FILE) or "data", exist_ok=True)
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[Warn] save_data fehlgeschlagen: {e}")

def find_letzte_abstimmung(uuid: str, name: str, guild_id: int):
    daten = load_json(ABSTIMMUNGEN_FILE)
    if not daten:
        return None
    voting_channel_id = get_guild_setting(guild_id, "COMRADAR_VOTING_CHANNEL_ID")
    daten_sorted = sorted(daten, key=lambda e: e.get("created_at", ""), reverse=True)
    for e in daten_sorted:
        uuid_field = e.get("uuid", "") or ""
        uuid_field_norm = uuid_field.replace("-", "") if isinstance(uuid_field, str) else ""
        name_matches = (
            e.get("beschuldigter", "").lower() == name.lower()
            or e.get("scammer", "").lower() == name.lower()
            or e.get("spieler", "").lower() == name.lower()
            or e.get("scammer_name", "").lower() == name.lower()
        )
        uuid_matches = False
        if uuid:
            uuid_norm = uuid.replace("-", "")
            uuid_matches = uuid_norm == uuid_field_norm or uuid_norm in uuid_field_norm or uuid_field_norm in uuid_norm
        if name_matches or uuid_matches:
            public_id = e.get("public_msg_id")
            created_at = e.get("created_at")
            try:
                date_str = datetime.fromisoformat(created_at).strftime("%d.%m.%Y %H:%M")
            except Exception:
                date_str = created_at or "Unbekannt"
            if public_id and voting_channel_id:
                url = f"https://discord.com/channels/{guild_id}/{voting_channel_id}/{public_id}"
                return f"[{date_str}]({url})"
            return date_str
    return None

# ---------------------------
# Modal
# ---------------------------
class EntschaedigtModal(Modal, title="💰 Entschädigung einreichen"):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(TextInput(label="Scammer-Name", required=True))
        self.add_item(TextInput(label="Ticket-Link oder Ticket-ID", required=True))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild_id = interaction.guild.id
        scammer = self.children[0].value.strip()
        ticket = self.children[1].value.strip()
        uuid = await fetch_uuid(scammer)

        forum_id = get_guild_setting(guild_id, "COMRADAR_VOTE_CHANNEL_ID")
        voting_id = get_guild_setting(guild_id, "COMRADAR_VOTING_CHANNEL_ID")
        tag_offen_id = get_guild_setting(guild_id, "TAG_OFFEN_ID")
        tag_entschaedigt_id = get_guild_setting(guild_id, "TAG_ENTSCHAEDIGT_ID")

        forum = interaction.guild.get_channel(forum_id)
        voting = interaction.guild.get_channel(voting_id)
        if not forum or not voting:
            await interaction.followup.send("⚠️ Forum oder Voting-Kanal nicht gefunden.", ephemeral=True)
            return
        if not isinstance(forum, discord.ForumChannel):
            await interaction.followup.send("❌ Der konfigurierte Vote-Kanal ist kein Forum.", ephemeral=True)
            return

        letzte_abstimmung = find_letzte_abstimmung(uuid, scammer, guild_id)
        scammer_link = f"[{scammer}](https://griefer.info/community-radar/player/{scammer})"
        ticket_display = f"[Zum Ticket]({ticket})" if ticket.startswith("http") else f"`{ticket}`"

        content_lines = [
            f"**Scammer:** {scammer_link}",
            f"**UUID:** `{uuid or 'Unbekannt'}`",
            f"**Ticket:** {ticket_display}",
            f"**Eingereicht von:** {interaction.user.mention}",
            "\n---\n",
        ]
        if letzte_abstimmung:
            content_lines.append(f"**Letzte Abstimmung:** {letzte_abstimmung}")
            content_lines.append("\n---\n")
        content_lines.append("Teammitglieder können hier über die Entschädigung abstimmen.\n\n📆 = Verkürzung | 💼 = Austragung")
        content = "\n".join(content_lines)

        try:
            available_tags = getattr(forum, "available_tags", []) or []
            tags = []
            for tag_id in (tag_offen_id, tag_entschaedigt_id):
                tag = discord.utils.get(available_tags, id=tag_id)
                if tag:
                    tags.append(tag)
            applied_tags = tags if tags else []

            created = await forum.create_thread(
                name=f"{scammer}",
                content=content,
                applied_tags=applied_tags,
                auto_archive_duration=10080,
            )

            thread = created if isinstance(created, discord.Thread) else getattr(created, "thread", None)
            thread_message = getattr(created, "message", None) or (thread.get_partial_message(thread.id) if thread else None)

            if thread and thread_message is None:
                try:
                    async for m in thread.history(limit=1, oldest_first=True):
                        thread_message = m
                        break
                except Exception:
                    thread_message = None

            if not thread:
                await interaction.followup.send("❌ Fehler: Thread konnte nicht ermittelt werden.", ephemeral=True)
                return

            if thread_message:
                for emoji in ("📆", "💼"):
                    try:
                        await thread_message.add_reaction(emoji)
                    except Exception:
                        pass

            letzte_abstimmung_text = letzte_abstimmung or "Keine bekannt"
            embed = discord.Embed(
                title=f"💰 Entschädigung: {scammer}",
                description=(
                    f"**UUID:** `{uuid or 'Unbekannt'}`\n\n"
                    f"🧾 **Letzte Abstimmung:** {letzte_abstimmung_text}\n\n"
                    f"📆 **Verkürzung:** 0\n💼 **Austragung:** 0"
                ),
                color=discord.Color.gold(),
                timestamp=datetime.utcnow(),
            )
            embed.set_footer(text=f"Eingereicht von {interaction.user}")
            voting_msg = await voting.send(embed=embed)

            store = load_json(DATA_FILE)
            store.append({
                "scammer": scammer,
                "uuid": uuid,
                "ticket": ticket,
                "thread_id": thread.id,
                "starter_message_id": thread_message.id if thread_message else None,
                "public_msg_id": voting_msg.id,
                "created_at": datetime.utcnow().isoformat(),
            })
            save_data(store)
            await interaction.followup.send(f"✅ Entschädigung für `{scammer}` erstellt.", ephemeral=True)

        except Exception as e:
            print(f"[FEHLER] {e}")
            await interaction.followup.send(f"❌ Fehler beim Erstellen: {e}", ephemeral=True)

# ---------------------------
# Cog
# ---------------------------
class Entschaedigt(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="entschädigt", description="Reicht eine Entschädigungsanfrage ein (Team only).")
    async def entschädigt(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        admin_roles = get_guild_setting(guild_id, "ADMIN_ROLE_IDS", [])
        if not any(r.id in admin_roles for r in interaction.user.roles) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Du hast keine Berechtigung.", ephemeral=True)
            return
        await interaction.response.send_modal(EntschaedigtModal(self.bot))

    async def _handle_reaction_change(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return

        daten = load_json(DATA_FILE)
        eintrag = next((e for e in daten if e.get("starter_message_id") == payload.message_id), None)
        if eintrag is None:
            eintrag = next((e for e in daten if e.get("thread_id") == payload.channel_id), None)
        if not eintrag:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        try:
            channel = guild.get_channel(payload.channel_id) or await guild.fetch_channel(payload.channel_id)
            msg = await channel.fetch_message(payload.message_id)
        except Exception:
            return

        counts = {"📆": 0, "💼": 
