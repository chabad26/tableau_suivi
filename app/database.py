import sqlite3
from pathlib import Path
from app.models import DetectedEmail

DATABASE_PATH = Path("data/job_tracker.db")


def get_connection() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    connection = sqlite3.connect(DATABASE_PATH)

    connection.row_factory = sqlite3.Row

    return connection


def init_database() -> None:
    with get_connection() as connection:

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
            CREATE INDEX IF NOT EXISTS idx_applications_company
            ON applications(company)
        """)

        connection.commit()

def email_exists(message_id: str) -> bool:
    if not message_id:
        return False

    with get_connection() as connection:

        result = connection.execute(
            """
            SELECT id
            FROM emails
            WHERE message_id = ?
            """,
            (message_id,)
        ).fetchone()

        return result is not None

def save_email(
    email: DetectedEmail,
    application_id: int | None = None
) -> bool:

    if not email.message_id:
        return False

    try:
        with get_connection() as connection:

            connection.execute(
                """
                INSERT INTO emails (
                    message_id,
                    application_id,
                    mailbox,
                    sender,
                    subject,
                    received_at,
                    detected_status,
                    score
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    email.message_id,
                    application_id,
                    email.mailbox,
                    email.sender,
                    email.subject,
                    email.date.isoformat(),
                    email.status,
                    email.score,
                )
            )

            connection.commit()

        return True

    except sqlite3.IntegrityError:
        # Message-ID déjà présent
        return False