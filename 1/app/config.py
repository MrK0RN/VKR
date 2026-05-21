import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
NET_JSON_PATH = BASE_DIR / "app" / "petri" / "hodgkin_net.json"

LOG_LEVEL = "INFO"
LOG_DIR = BASE_DIR / "logs"
LOG_JSON = True
LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 5

SESSION_SECRET_KEY = os.environ.get("HODGKIN_SESSION_SECRET", "hodgkin-dev-secret-change-in-production")
SESSION_COOKIE_NAME = "hodgkin_session"
SESSION_TTL_SECONDS = 24 * 3600
