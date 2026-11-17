"""Accès SQLite, schéma et opérations de persistance."""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager

from app.application_history import init_application_history
from app.settings import DATABASE_PATH

# Connexion et migrations


@contextmanager
def get_connection() -> Generator[sqlite3.Connection]:
    """
    Fournit une connexion SQLite transactionnelle.

    - Commit si aucune exception.
    - Rollback en cas d'exception.
    - Fermeture systématique.
    """
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        connection.row_factory = sqlite3.Row

        connection.execute("PRAGMA foreign_keys = ON")

        connection.execute("PRAGMA busy_timeout = 10000")

        with connection:
            yield connection

    finally:
        connection.close()


def ensure_column(
    connection: sqlite3.Connection, table: str, column: str, definition: str
) -> None:
    columns = connection.execute(f"PRAGMA table_info({table})").fetchall()

    existing = {row["name"] for row in columns}

    if column not in existing:
        connection.execute(
            f"""
            ALTER TABLE {table}
            ADD COLUMN {column} {definition}
            """
        )


def init_database() -> None:
    with get_connection() as connection:
        # Schéma, déclencheurs et conversion des statuts forment un seul ensemble.
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                company TEXT NOT NULL,
                job_title TEXT,

                source TEXT,

                first_seen TEXT NOT NULL,
                last_update TEXT NOT NULL,

                current_status TEXT NOT NULL
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                message_id TEXT UNIQUE NOT NULL,

                application_id INTEGER,

                mailbox TEXT NOT NULL,

                sender TEXT,
                subject TEXT,

                received_at TEXT NOT NULL,

                detected_status TEXT NOT NULL,

                score INTEGER NOT NULL,

                FOREIGN KEY(application_id)
                    REFERENCES applications(id)
                    ON DELETE SET NULL
            )
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_emails_message_id
            ON emails(message_id)
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_emails_application_received
            ON emails (
                application_id,
                received_at DESC
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS imap_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                email TEXT UNIQUE NOT NULL,
                provider TEXT,

                host TEXT NOT NULL,
                port INTEGER NOT NULL DEFAULT 993,
                use_ssl INTEGER NOT NULL DEFAULT 1,

                username TEXT NOT NULL,
                folder TEXT NOT NULL DEFAULT 'INBOX',

                enabled INTEGER NOT NULL DEFAULT 1,

                created_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_applications_company
            ON applications(company)
        """)

        ensure_column(
            connection,
            "imap_accounts",
            "last_status",
            "TEXT NOT NULL DEFAULT 'unknown'",
        )

        ensure_column(connection, "imap_accounts", "last_error", "TEXT")

        ensure_column(connection, "imap_accounts", "last_checked_at", "TEXT")

        ensure_column(
            connection,
            "imap_accounts",
            "auth_method",
            "TEXT NOT NULL DEFAULT 'password'",
        )

        ensure_column(
            connection, "imap_accounts", "last_uid", "INTEGER NOT NULL DEFAULT 0"
        )

        ensure_column(connection, "imap_accounts", "uid_validity", "INTEGER")

        ensure_column(connection, "applications", "manual_status", "TEXT")

        ensure_column(connection, "applications", "manual_note", "TEXT")
        ensure_column(
            connection, "applications", "offer_text", "TEXT NOT NULL DEFAULT ''"
        )
        ensure_column(
            connection, "applications", "offer_url", "TEXT NOT NULL DEFAULT ''"
        )

        ensure_column(
            connection, "applications", "manual_override", "INTEGER NOT NULL DEFAULT 0"
        )

        ensure_column(connection, "emails", "body", "TEXT")
        ensure_column(connection, "emails", "html_body", "TEXT NOT NULL DEFAULT ''")
        ensure_column(connection, "emails", "in_reply_to", "TEXT NOT NULL DEFAULT ''")
        ensure_column(
            connection, "emails", "references_header", "TEXT NOT NULL DEFAULT ''"
        )

        # Retrait du statut historique : pas de perte de candidature ni de faux
        # changement dans le journal lors du regroupement avec « Reçue ».
        if connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='application_status_history'"
        ).fetchone() and any(
            row["name"] == "user_id"
            for row in connection.execute("PRAGMA table_info(applications)")
        ):
            init_application_history(connection)
        connection.execute(
            "UPDATE applications SET current_status='RECEIVED' WHERE current_status='SENT'"
        )
        connection.execute(
            "UPDATE applications SET manual_status='RECEIVED' WHERE manual_status='SENT'"
        )
        connection.execute(
            "UPDATE emails SET detected_status='RECEIVED' WHERE detected_status='SENT'"
        )

        # Répare les anciennes références orphelines sans supprimer les messages.
        connection.execute("""
            UPDATE emails SET application_id = NULL
            WHERE application_id IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM applications WHERE id = emails.application_id)
        """)
        # Garantit l'intégrité des références même si la contrainte FK
        # n'est pas présente dans une base existante.
        connection.execute("""
            CREATE TRIGGER IF NOT EXISTS detach_application_emails
            BEFORE DELETE ON applications BEGIN
                UPDATE emails SET application_id = NULL WHERE application_id = OLD.id;
            END
        """)

        for operation in ("INSERT", "UPDATE"):
            connection.execute(f"""
                CREATE TRIGGER IF NOT EXISTS emails_application_{operation.lower()}
                BEFORE {operation} ON emails
                WHEN NEW.application_id IS NOT NULL
                  AND NOT EXISTS (SELECT 1 FROM applications WHERE id = NEW.application_id)
                BEGIN SELECT RAISE(ABORT, 'Unknown application'); END
            """)

        connection.commit()


# Emails
