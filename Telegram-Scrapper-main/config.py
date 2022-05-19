import os

import dotenv

dotenv.load_dotenv("local.env")

api_id = int(os.environ.get("API_ID") or 6)
api_hash = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID"))
