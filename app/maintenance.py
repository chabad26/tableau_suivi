from datetime import datetime, timedelta, timezone

from app.database import get_connection
from app.owned_applications import require_user_id
from app.settings import APPLICATION_EXPIRY_DAYS

EXPIRABLE_STATUSES = {"RECEIVED", "OTHER"}


def expire_stale_applications(user_id: int | None = None) -> int:
    """Expire les candidatures en attente, éventuellement pour un seul propriétaire."""
    if user_id is not None:
        user_id = require_user_id(user_id)
    cutoff = datetime.now(timezone.utc) - timedelta(days=APPLICATION_EXPIRY_DAYS)

    placeholders = ", ".join("?" for _ in EXPIRABLE_STATUSES)

    with get_connection() as connection:
        cursor = connection.execute(
            f"""
            UPDATE applications
            SET current_status = CASE WHEN manual_override = 0
                    THEN 'EXPIRED' ELSE current_status END,
                manual_status = CASE WHEN manual_override = 1
                    THEN 'EXPIRED' ELSE manual_status END
            WHERE (CASE WHEN manual_override = 1
                    THEN manual_status ELSE current_status END) IN ({placeholders})
              AND julianday(last_update) <= julianday(?)
              {"AND user_id = ?" if user_id is not None else ""}
            """,
            (
                *EXPIRABLE_STATUSES,
                cutoff.isoformat(),
                *((user_id,) if user_id is not None else ()),
            ),
        )

        connection.commit()

        return cursor.rowcount
