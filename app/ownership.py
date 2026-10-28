"""Migration du schéma vers une application multi-utilisateur."""

import sqlite3

from app.database import get_connection

OWNED_TABLES = ("applications", "emails", "imap_accounts", "jobs")


def ensure_user_column(connection: sqlite3.Connection, table: str) -> None:
    """
    Ajoute user_id uniquement si la colonne n'existe pas.

    Les anciennes données restent présentes et leur
    propriétaire reste NULL jusqu'à attribution explicite.
    """

    columns = connection.execute(f"PRAGMA table_info({table})").fetchall()

    if not columns:
        raise RuntimeError(f"Table absente pendant la migration : {table}")

    existing = {row["name"] for row in columns}

    if "user_id" not in existing:
        connection.execute(
            f"""
            ALTER TABLE {table}
            ADD COLUMN user_id INTEGER
            """
        )


def init_ownership() -> None:
    """
    Prépare les tables pour l'isolation utilisateur.

    Cette migration est idempotente.
    """

    with get_connection() as connection:
        for table in OWNED_TABLES:
            ensure_user_column(connection, table)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_applications_user_id
            ON applications(user_id)
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_emails_user_application
            ON emails(user_id, application_id)
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_imap_accounts_user_id
            ON imap_accounts(user_id)
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_jobs_user_id
            ON jobs(user_id)
        """)
