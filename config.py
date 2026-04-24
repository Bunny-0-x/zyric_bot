#(©)Zyric Network

import os
import json
import logging
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler

load_dotenv()

# ── Core Bot ──────────────────────────────────────────────────────────
TG_BOT_TOKEN     = os.environ.get("TG_BOT_TOKEN", "")
APP_ID           = int(os.environ.get("APP_ID", "0"))
API_HASH         = os.environ.get("API_HASH", "")
OWNER_ID         = int(os.environ.get("OWNER_ID", "0"))
CHANNEL_ID       = int(os.environ.get("CHANNEL_ID", "0"))
PORT             = int(os.environ.get("PORT", "8080"))

# ── Database ──────────────────────────────────────────────────────────
DB_URI           = os.environ.get("DATABASE_URL", "")
DB_NAME          = os.environ.get("DATABASE_NAME", "zyric")

# ── UserBot ───────────────────────────────────────────────────────────
USERBOT_PHONE    = os.environ.get("USERBOT_PHONE", "")     # e.g. +919876543210
USERBOT_API_ID   = int(os.environ.get("USERBOT_API_ID", os.environ.get("APP_ID", "0")))
USERBOT_API_HASH = os.environ.get("USERBOT_API_HASH", os.environ.get("API_HASH", ""))

# ── Channel Branding ──────────────────────────────────────────────────
POWERED_BY       = os.environ.get("POWERED_BY", "@YourChannel")   # e.g. @Anime_Unity
MAIN_CHANNEL_ID  = int(os.environ.get("MAIN_CHANNEL_ID", "0"))    # Main announcement channel

# ── Fleet (multi-bot) ─────────────────────────────────────────────────
# Format in .env:
# TELEGRAM_FLEET=[{"token":"123:ABC","dump_channel":-100xxx},{"token":"456:DEF","dump_channel":-100yyy}]
_fleet_raw       = os.environ.get("TELEGRAM_FLEET", "[]")
TELEGRAM_FLEET   = json.loads(_fleet_raw)

# ── Force Sub ─────────────────────────────────────────────────────────
FORCE_SUB_CHANNEL = int(os.environ.get("FORCE_SUB_CHANNEL", "0"))
JOIN_REQUEST_ENABLE = os.environ.get("JOIN_REQUEST_ENABLED", None)

# ── Auto Delete ───────────────────────────────────────────────────────
AUTO_DELETE_SECONDS = 600   # 10 minutes — do NOT change

# ── Bot Settings ──────────────────────────────────────────────────────
TG_BOT_WORKERS   = int(os.environ.get("TG_BOT_WORKERS", "4"))
PROTECT_CONTENT  = os.environ.get("PROTECT_CONTENT", "False") == "True"
START_PIC        = os.environ.get("START_PIC", "")
START_MSG        = os.environ.get("START_MESSAGE",
    "Hello {first}\n\nI can store private files in Specified Channel "
    "and other users can access it from special link.")
FORCE_MSG        = os.environ.get("FORCE_SUB_MESSAGE",
    "Hello {first}\n\n<b>You need to join my Channel to use me.</b>")

try:
    ADMINS = [int(x) for x in os.environ.get("ADMINS", "").split()]
except ValueError:
    raise Exception("ADMINS list contains invalid integers.")
ADMINS.append(OWNER_ID)

# ── Logging ───────────────────────────────────────────────────────────
LOG_FILE = "zyric.log"
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler(LOG_FILE, maxBytes=50_000_000, backupCount=10),
        logging.StreamHandler()
    ]
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)
DISABLE_CHANNEL_BUTTON = False
AUTO_DELETE_TIME = 0

# Auto-added missing variables
AUTO_DELETE_TIME = 0
AUTO_DELETE_SECONDS = 0
AUTO_DEL_SUCCESS_MSG = "Message will be deleted in {time} seconds."
DISABLE_CHANNEL_BUTTON = False
JOIN_REQUEST_ENABLE = False
PROTECT_CONTENT = False
FORCE_SUB_CHANNEL = None
FORCE_MSG = "You must join our channel to use this bot."
USER_REPLY_TEXT = "This is a file bot. Send a valid link."
BOT_STATS_TEXT = "Bot is running fine."
START_MSG = "Welcome! I am Zyric Bot."
START_PIC = ""
POWERED_BY = "Zyric Network"
TG_BOT_WORKERS = 4
PORT = 8080
