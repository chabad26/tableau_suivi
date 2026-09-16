"""Constantes communes ; les dates locales et API gardent leur fuseau initial."""

from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
API_START_DATE = datetime(2026, 8, 1, tzinfo=ZoneInfo("Europe/Paris"))
MAILBOX_START_DATE = datetime(2026, 8, 1, tzinfo=timezone.utc)
