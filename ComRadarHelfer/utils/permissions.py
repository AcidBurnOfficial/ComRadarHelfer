import discord
from functools import wraps
import logging
import os
from logging.handlers import TimedRotatingFileHandler
import json

# =====================================================
# 📂 Server-Konfig-Datei
# =====================================================
SERVER_CONFIG_FILE = "data/server_config.json"

def load_server_config(guild_id: int) -> dict:
    """Lädt die Konfiguration für einen bestimmten Server."""
    if not os.path.exists(SERVER_CONFIG_FILE):
        return {}
    with open(SERVER_CONFIG_FILE, "r", encoding="utf-8") as f:
        all_data = json.load(f)
    return all_data.get(str(guild_id), {})


# =====================================================
# 🎨 Farbige Logging-Ausgabe in Konsole & Datei
# =====================================================
class ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[94m",    # Blau
        logging.INFO: "\033[92m",     # Grün
        logging.WARNING: "\033[93m",  # Gelb
        logging.ERROR: "\033[91m",    # Rot
        logging.CRITICAL: "\033[95m", # Magenta
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelno, self.RESET)
        message = super().format(record)
        return f"{color}{message}{self.RESET}"


# -----------------------------------------------------
# 🧾 Logging Setup (Datei + Konsole)
# -----------------------------------------------------
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, "bot.log")

file_handler = TimedRotatingFileHandler(
    log_file, when="midnight", interval=1, backupCount=14, encoding="utf-8"
)
file_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(file_formatter)

console_handler = logging.StreamHandler()
console_formatter = ColorFormatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
console_handler.setFormatter(console_formatter)

logger = logging.getLogger("bot")
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)
logger.propagate = False


# =====================================================
# 🛰️ Discord Log Handler (pro Server)
# =====================================================
class DiscordLogHandler(logging.Handler):
    """Sendet Warnungen & Fehler als farbige Embeds an Discord-Server."""
    COLOR_MAP = {
        logging.INFO: 0x2ecc71,     # Grün
        logging.WARNING: 0xf1c40f,  # Gelb
        logging.ERROR: 0xe74c3c,    # Rot
        logging.CRITICAL: 0x9b59b6, # Lila
    }

    ICON_MAP = {
        logging.INFO: "🟢",
        logging.WARNING: "⚠️",
        logging.ERROR: "🔴",
        logging.CRITICAL: "💥",
    }

    def __init__(self, bot):
        super().__init__(level=logging.WARNING)  # WARN+ an Discord
        self.bot = bot

    async def send_to_discord(self, record: logging.LogRecord, message: str):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            cfg = load_server_config(guild.id)
            log_channel_id = cfg.get("LOG_CHANNEL_ID")
            if not log_channel_id:
                continue

            channel = self.bot.get_channel(log_channel_id)
            if not channel:
                continue

            color = self.COLOR_MAP.get(record.levelno, 0x95a5a6)
            icon = self.ICON_MAP.get(record.levelno, "🪶")

            embed = discord.Embed(
                title=f"{icon} [{record.levelname}] Log-Eintrag",
                description=f"```{message}```",
                color=color,
                timestamp=discord.utils.utcnow()
            )
            embed.set_footer(text=f"Logger: {record.name}")

            try:
                await channel.send(embed=embed)
            except Exception as e:
                print(f"[WARN] Konnte Log nicht an Discord senden: {e}")

    def emit(self, record):
        try:
            message = self.format(record)
            self.bot.loop.create_task(self.send_to_discord(record, message))
        except Exception:
            self.handleError(record)


# =====================================================
# 🛡️ Berechtigungen
# =====================================================
def has_permission(user: discord.Member) -> bool:
    guild_id = user.guild.id
    cfg = load_server_config(guild_id)

    allowed_users = cfg.get("ALLOWED_USER_IDS", [])
    allowed_roles = cfg.get("ALLOWED_ROLE_IDS", [])
    admin_roles = cfg.get("ADMIN_ROLE_IDS", [])
    support_roles = cfg.get("SUPPORT_ROLE_IDS", [])

    if user.id in allowed_users:
        return True

    role_ids = [r.id for r in user.roles]
    allowed_combined = set(allowed_roles + admin_roles + support_roles)

    if any(rid in allowed_combined for rid in role_ids):
        return True

    if user.guild_permissions.administrator:
        return True

    return False


# =====================================================
# 🔒 Decorator für Slash Commands
# =====================================================
def restricted_command():
    def decorator(func):
        @wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            user = interaction.user
            if not has_permission(user):
                logger.warning(
                    f"🚫 Zugriff verweigert: {user} (ID: {user.id}) versuchte '{func.__name__}' auszuführen."
                )
                await interaction.response.send_message(
                    "❌ Du darfst diesen Befehl nicht ausführen.",
                    ephemeral=True
                )
                return
            logger.info(f"✅ {user} (ID: {user.id}) führt '{func.__name__}' aus.")
            return await func(self, interaction, *args, **kwargs)
        return wrapper
    return decorator


# =====================================================
# 🪄 Aktivierung des DiscordLogHandlers
# =====================================================
def setup_discord_logging(bot):
    """Fügt den Discord-Handler dem Logger hinzu."""
    discord_handler = DiscordLogHandler(bot)
    discord_handler.setFormatter(file_formatter)
    logger.addHandler(discord_handler)
    logger.info("📡 Discord-Logging-Handler aktiviert")
