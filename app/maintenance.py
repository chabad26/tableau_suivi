from datetime import datetime, timedelta, timezone

from app.database import get_connection
from app.settings import APPLICATION_EXPIRY_DAYS


EXPIRABLE_STATUSES = {
    "PROPOSED",
    "SENT",
    "RECEIVED",
    "OTHER",
}


def expire_stale_applications() -> int:
    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(
            days=APPLICATION_EXPIRY_DAYS
        )
    )

    placeholders = ", ".join(
        "?" for _ in EXPIRABLE_STATUSES
    )

    with get_connection() as connection:
        cursor = connection.execute(
            f"""
            UPDATE applications
            SET current_status = 'EXPIRED'
            WHERE manual_override = 0
              AND current_status IN ({placeholders})
              AND last_update <= ?
            """,
            (
                *EXPIRABLE_STATUSES,
                cutoff.isoformat(),
            ),
        )

        connection.commit()

        return cursor.rowcount