import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Add it to a .env file.")

# Comma-separated Telegram user IDs allowed to use /add_idea (e.g. ADMIN_USER_IDS=123456789,987654321)
_admin_raw = os.getenv("ADMIN_USER_IDS", "").strip()
ADMIN_USER_IDS: list[int] = []
if _admin_raw:
    for part in _admin_raw.split(","):
        part = part.strip()
        if part.isdigit():
            ADMIN_USER_IDS.append(int(part))
