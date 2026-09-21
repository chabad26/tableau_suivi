"""Configuration chargée une fois au démarrage, indépendante du dossier courant."""

import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
load_dotenv(ENV_FILE, override=False)


def configured_path(name: str, default: str) -> Path:
    path = Path(os.getenv(name, default)).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def configured_date(value: str) -> datetime:
    try:
        date = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(
            "SCAN_START_DATE doit être une date ISO, par exemple 2026-08-01."
        ) from error
    return date if date.tzinfo else date.replace(tzinfo=ZoneInfo("Europe/Paris"))


API_START_DATE = configured_date(os.getenv("SCAN_START_DATE", "2026-08-01"))
DATABASE_PATH = configured_path("DATABASE_PATH", "data/job_tracker.db")
GMAIL_CREDENTIALS_FILE = configured_path("GMAIL_CREDENTIALS_FILE", "credentials.json")
GMAIL_TOKEN_FILE = configured_path("GMAIL_TOKEN_FILE", "token.json")
MICROSOFT_TOKEN_CACHE_FILE = configured_path(
    "MICROSOFT_TOKEN_CACHE_FILE", "microsoft_token_cache.json"
)
MICROSOFT_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID", "").strip()
MICROSOFT_AUTHORITY = os.getenv(
    "MICROSOFT_AUTHORITY", "https://login.microsoftonline.com/common"
).strip()
SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "") or os.urandom(32).hex()


APPLICATION_EXPIRY_DAYS = int(
    os.getenv(
        "APPLICATION_EXPIRY_DAYS",
        "30",
    )
)