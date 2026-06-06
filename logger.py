import os
import sys
from datetime import datetime

LOG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Unified_AI_Combat")
LOG_FILE = os.path.join(LOG_DIR, "combat_debug.log")

os.makedirs(LOG_DIR, exist_ok=True)

def log(msg):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {msg}\n")
    except Exception:
        pass
