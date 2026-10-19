import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Check for .env in fireshield-flask first, then project root, then secrets/.env
env_locations = [
    BASE_DIR / ".env",
    BASE_DIR.parent / ".env",
    BASE_DIR.parent / "secrets" / ".env",
]

for env_path in env_locations:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        break

class Config:
    """Application configuration loaded from environment variables."""
    # ThingSpeak credentials
    THINGSPEAK_CHANNEL_ID = os.environ.get("THINGSPEAK_CHANNEL_ID", "").strip()
    THINGSPEAK_READ_API_KEY = os.environ.get("THINGSPEAK_READ_API_KEY", "").strip()
    THINGSPEAK_BASE_URL = os.environ.get("THINGSPEAK_BASE_URL", "https://api.thingspeak.com").strip()
    
    # Server settings
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "fireshield-secret-key-change-in-production")
    FLASK_HOST = os.environ.get("FLASK_HOST", "0.0.0.0")
    FLASK_PORT = int(os.environ.get("FLASK_PORT", "5000"))
    DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() in ("true", "1", "yes")
    
    # Telemetry settings
    POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", "15"))
    MAX_HISTORY_RESULTS = int(os.environ.get("MAX_HISTORY_RESULTS", "500"))
    CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", "15"))
    STALE_THRESHOLD_SECONDS = int(os.environ.get("STALE_THRESHOLD_SECONDS", "60"))
    
    # CORS settings: restrict to allowed origins (Flutter web local dev, etc.)
    CORS_ALLOWED_ORIGINS = [
        origin.strip() for origin in os.environ.get(
            "CORS_ALLOWED_ORIGINS",
            "http://localhost:5000,http://127.0.0.1:5000,http://localhost:3000,http://127.0.0.1:3000,http://localhost:8080,http://127.0.0.1:8080,http://localhost:8000,http://127.0.0.1:8000"
        ).split(",") if origin.strip()
    ]
    
    # Paths
    DATA_RAW_DIR = BASE_DIR / "data" / "raw"
    DATA_PROCESSED_DIR = BASE_DIR / "data" / "processed"
    DATA_LABELS_DIR = BASE_DIR / "data" / "labels"
    DATA_MODELS_DIR = BASE_DIR / "data" / "models"
    DATA_NOTIFICATIONS_DIR = BASE_DIR / "data" / "notifications"

    # VAPID / Web Push Settings
    VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "").strip()
    VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
    VAPID_CONTACT_EMAIL = os.environ.get("VAPID_CONTACT_EMAIL", "admin@fireshield.local").strip()
    VAPID_KEYS_FILE = BASE_DIR / "data" / "vapid_keys.json"

    # ntfy Notification Settings (mobile push without Firebase)
    NTFY_BASE_URL = os.environ.get("NTFY_BASE_URL", "https://ntfy.sh").strip().rstrip("/")
    NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "fireshield_alerts_3534677").strip()
    NTFY_ACCESS_TOKEN = os.environ.get("NTFY_ACCESS_TOKEN", "").strip()

    # Risk Evaluation Engine Settings
    EARLY_WARNING_TEMP_RISE_RATE_C_PER_MIN = float(os.environ.get("EARLY_WARNING_TEMP_RISE_RATE_C_PER_MIN", "1.5"))
    BASELINE_ANOMALY_SIGMA_THRESHOLD = float(os.environ.get("BASELINE_ANOMALY_SIGMA_THRESHOLD", "2.5"))
    COOLDOWN_SECONDS_EARLY_WARNING = int(os.environ.get("COOLDOWN_SECONDS_EARLY_WARNING", "300"))
    COOLDOWN_SECONDS_ANOMALY = int(os.environ.get("COOLDOWN_SECONDS_ANOMALY", "600"))
    ALL_CLEAR_CONSECUTIVE_READINGS = int(os.environ.get("ALL_CLEAR_CONSECUTIVE_READINGS", "3"))

    # SQLite Database for Events and Outbox
    DATABASE_PATH = BASE_DIR / "data" / "events.db"
