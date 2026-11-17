"""Schéma de la file persistante, exécutée uniquement par owned_jobs."""

from app.database import get_connection


def init_jobs() -> None:
    with get_connection() as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, kind TEXT NOT NULL, state TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            started_at TEXT, finished_at TEXT, result TEXT, error TEXT
        )""")
