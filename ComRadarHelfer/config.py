# ============================================
# 🧠 ComRadarHelfer – zentrale Konfiguration
# ============================================

import os
import json
from dotenv import load_dotenv

# ------------------------------
# 🔐 .env laden
# ------------------------------
load_dotenv()

# ------------------------------
# 🧩 Hilfsfunktionen
# ------------------------------
def parse_int_list(env_var: str) -> list[int]:
    """Wandelt kommaseparierte Zahlen in eine Integer-Liste um."""
    return [int(x) for x in env_var.split(",") if x.strip().isdigit()] if env_var else []

def parse_json(env_var: str):
    """Versucht, JSON sicher zu laden."""
    try:
        return json.loads(env_var)
    except Exception:
        return {}

# ------------------------------
# ⚙️ Basis-Konfiguration
# ------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
TEST_GUILD_ID = int(os.getenv("TEST_GUILD_ID", 0))

# ------------------------------
# 🪪 Rollen & Berechtigungen
# ------------------------------
ADMIN_ROLE_IDS = int(os.getenv("ADMIN_ROLE_IDS", 0))
SUPPORT_ROLE_IDS = parse_int_list(os.getenv("SUPPORT_ROLE_IDS", ""))
ALLOWED_USER_IDS = parse_int_list(os.getenv("ALLOWED_USER_IDS", ""))
ALLOWED_ROLE_IDS = parse_int_list(os.getenv("ALLOWED_ROLE_IDS", ""))

# ------------------------------
# 🧾 Logging
# ------------------------------
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", 0))
JOIN_LOG_CHANNEL_ID = int(os.getenv("JOIN_LOG_CHANNEL_ID", 0))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_PATH = os.getenv("LOG_PATH", "logs")

# ------------------------------
# 🎫 Ticketsystem
# ------------------------------
TICKET_CATEGORY_ID = int(os.getenv("TICKET_CATEGORY_ID", 0))
SCAMMER_ADMIN_CHANNEL_ID = int(os.getenv("SCAMMER_ADMIN_CHANNEL_ID", 0))
TICKET_LOG_CHANNEL_ID = int(os.getenv("TICKET_LOG_CHANNEL_ID", 0))
TRANSCRIPT_CHANNEL_ID = int(os.getenv("TRANSCRIPT_CHANNEL_ID", 0))
SCAMMERHILFE_ADMIN_ROLE_ID = int(os.getenv("SCAMMERHILFE_ADMIN_ROLE_ID", 0))
TEAMS = parse_json(os.getenv("TEAMS", "{}"))

# ------------------------------
# 🧾 Abstimmungssystem
# ------------------------------
FORUM_CHANNEL_ID = int(os.getenv("FORUM_CHANNEL_ID", 0))
VOTE_CHANNEL_ID = int(os.getenv("VOTE_CHANNEL_ID", 0))
TAG_OFFEN_ID = int(os.getenv("TAG_OFFEN_ID", 0))
TAG_GESCHLOSSEN_ID = int(os.getenv("TAG_GESCHLOSSEN_ID", 0))

# ------------------------------
# 💰 Entschädigungssystem
# ------------------------------
COMRADAR_VOTE_CHANNEL_ID = int(os.getenv("COMRADAR_VOTE_CHANNEL_ID", 0))
COMRADAR_VOTING_CHANNEL_ID = int(os.getenv("COMRADAR_VOTING_CHANNEL_ID", 0))
TAG_ENTSCHAEDIGT_ID = int(os.getenv("TAG_ENTSCHAEDIGT_ID", 0))
TAG_OFFEN_ENTSCHAEDIGT_ID = int(os.getenv("TAG_OFFEN_ENTSCHAEDIGT_ID", 0))

# ------------------------------
# ⚙️ Auto-Rollen
# ------------------------------
AUTO_ROLE_IDS = parse_int_list(os.getenv("AUTO_ROLE_IDS", ""))

# ------------------------------
# 🪪 ComRadar Wahlen
# ------------------------------
COMRADAR_NOMINIERUNG_CHANNEL_ID = int(os.getenv("COMRADAR_NOMINIERUNG_CHANNEL_ID", 0))
COMRADAR_WAHLEN_CHANNEL_ID = int(os.getenv("COMRADAR_WAHLEN_CHANNEL_ID", 0))
COMRADAR_WAHLERGEBNISSE_CHANNEL_ID = int(os.getenv("COMRADAR_WAHLERGEBNISSE_CHANNEL_ID", 0))
# ------------------------------
# 🎁 Giveaways
# ------------------------------
GIVEAWAY_CHANNEL_ID = int(os.getenv("GIVEAWAY_CHANNEL_ID", 0))

# ------------------------------
# 📊 Umfragen
# ------------------------------
UMFRAGEN_CHANNEL_ID = int(os.getenv("UMFRAGEN_CHANNEL_ID", 0))

# ------------------------------
# 📂 Datenpfade
# ------------------------------
DATA_PATH = os.getenv("DATA_PATH", "data")

# ------------------------------
# ✅ Zusammenfassung (optional)
# ------------------------------
if __name__ == "__main__":
    print("✅ Konfiguration geladen:")
    print(f"Guild-ID: {TEST_GUILD_ID}")
    print(f"Admin-Rollen: {ADMIN_ROLE_IDS}")
    print(f"Support-Rollen: {SUPPORT_ROLE_IDS}")
    print(f"Ticket-Log-Kanal: {TICKET_LOG_CHANNEL_ID}")
    print(f"Transcript-Kanal: {TRANSCRIPT_CHANNEL_ID}")
    print(f"ScammerHilfe Admin-Rolle: {SCAMMERHILFE_ADMIN_ROLE_ID}")
