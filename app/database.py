"""Accès SQLite et migrations ; API historique conservée."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.extractor import clean_job_title, company_key, job_title_score
from app.models import DetectedEmail
from app.settings import DATABASE_PATH

# Connexion et migrations


def get_connection() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)

    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    connection.row_factory = sqlite3.Row

    return connection


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

        ensure_column(connection, "applications", "manual_status", "TEXT")

        ensure_column(connection, "applications", "manual_note", "TEXT")

        ensure_column(
            connection, "applications", "manual_override", "INTEGER NOT NULL DEFAULT 0"
        )

        ensure_column(connection, "emails", "body", "TEXT")

        # Répare les anciennes références sans supprimer les messages.
        connection.execute("""
            UPDATE emails SET application_id = NULL
            WHERE application_id IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM applications WHERE id = emails.application_id)
        """)
        # Compatibilité avec les anciennes tables sans contrainte FK :
        # mêmes garanties sans reconstruire ni perdre des colonnes historiques.
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
            (message_id,),
        ).fetchone()

        return result is not None


def save_email(email: DetectedEmail, application_id: int | None = None) -> bool:

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
                    score,
                    body
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    email.body,
                ),
            )

            connection.commit()

        return True

    except sqlite3.IntegrityError:
        # Message-ID déjà présent
        return False


def get_application_emails(application_id: int) -> list[sqlite3.Row]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                message_id,
                mailbox,
                sender,
                subject,
                received_at,
                detected_status,
                score,
                body
            FROM emails
            WHERE application_id = ?
            ORDER BY received_at DESC
            """,
            (application_id,),
        ).fetchall()

        return list(rows)


# Candidatures : lecture et création


def get_applications() -> list[sqlite3.Row]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                company,
                job_title,
                source,
                first_seen,
                last_update,
                current_status,
                manual_status,
                manual_note,
                manual_override
            FROM applications
            ORDER BY last_update DESC
            """
        ).fetchall()

        return list(rows)


def get_application(application_id: int) -> sqlite3.Row | None:
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT
                id,
                company,
                job_title,
                source,
                first_seen,
                last_update,
                current_status,
                manual_status,
                manual_note,
                manual_override
            FROM applications
            WHERE id = ?
            """,
            (application_id,),
        ).fetchone()


def find_application(company: str, job_title: str) -> int | None:
    target_company_key = company_key(company)

    target_job_title = job_title.strip().casefold() if job_title else ""

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                company,
                job_title,
                last_update
            FROM applications
            ORDER BY last_update DESC
            """
        ).fetchall()

    for row in rows:
        existing_company = row["company"] or ""

        if company_key(existing_company) != target_company_key:
            continue

        existing_job_title = (row["job_title"] or "").strip().casefold()

        #
        # Si on connaît les deux postes,
        # ils doivent correspondre.
        #
        if (
            target_job_title
            and existing_job_title
            and target_job_title != existing_job_title
        ):
            continue

        #
        # Même entreprise, et au moins un poste inconnu
        # ou bien postes identiques.
        #
        return int(row["id"])

    return None


def create_application(
    company: str, job_title: str, source: str, status: str, date: datetime
) -> int:

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO applications (
                company,
                job_title,
                source,
                first_seen,
                last_update,
                current_status
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (company, job_title, source, date.isoformat(), date.isoformat(), status),
        )

        connection.commit()

        if cursor.lastrowid is None:
            raise RuntimeError("Impossible de récupérer l'ID de la candidature.")

        return int(cursor.lastrowid)


def get_or_create_application(
    company: str, job_title: str, source: str, status: str, date: datetime
) -> int:

    application_id = find_application(company, job_title)

    if application_id is not None:
        return application_id

    return create_application(
        company=company, job_title=job_title, source=source, status=status, date=date
    )


def create_manual_application(
    company: str, job_title: str, source: str, status: str, note: str = ""
) -> int:

    now = datetime.now(timezone.utc)

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO applications (
                company,
                job_title,
                source,
                first_seen,
                last_update,
                current_status,
                manual_status,
                manual_note,
                manual_override
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                company,
                job_title,
                source,
                now.isoformat(),
                now.isoformat(),
                status,
                status,
                note,
            ),
        )

        connection.commit()

        if cursor.lastrowid is None:
            raise RuntimeError("Impossible de récupérer l'ID de la candidature.")

        return int(cursor.lastrowid)


def create_discord_proposal(company: str, job_title: str, note: str = "") -> int:
    now = datetime.now(timezone.utc)

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO applications (
                company,
                job_title,
                source,
                first_seen,
                last_update,
                current_status,
                manual_status,
                manual_note,
                manual_override
            )
            VALUES (?, ?, ?, ?, ?, ?, NULL, ?, 0)
            """,
            (
                company,
                job_title,
                "Discord / Centre de formation",
                now.isoformat(),
                now.isoformat(),
                "PROPOSED",
                note,
            ),
        )

        connection.commit()

        if cursor.lastrowid is None:
            raise RuntimeError("Impossible de créer la proposition Discord.")

        return int(cursor.lastrowid)


# Candidatures : mises à jour


def update_application(
    application_id: int, status: str, date: datetime, job_title: str = ""
) -> None:

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                last_update,
                job_title
            FROM applications
            WHERE id = ?
            """,
            (application_id,),
        ).fetchone()

        if row is None:
            return

        current_last_update = datetime.fromisoformat(row["last_update"])

        current_job_title = row["job_title"] or ""

        #
        # Compléter le poste même avec un ancien mail
        #
        new_job_title = current_job_title if current_job_title else job_title

        #
        # Le statut ne doit être modifié
        # que par un mail plus récent.
        #
        if date >= current_last_update:
            connection.execute(
                """
                UPDATE applications
                SET
                    current_status = ?,
                    last_update = ?,
                    job_title = ?
                WHERE id = ?
                """,
                (status, date.isoformat(), new_job_title, application_id),
            )

        elif new_job_title != current_job_title:
            # Ancien mail utile uniquement pour compléter le poste.
            connection.execute(
                """
                UPDATE applications
                SET job_title = ?
                WHERE id = ?
                """,
                (new_job_title, application_id),
            )

        connection.commit()


def update_application_from_analysis(
    application_id: int, company: str, job_title: str, source: str
) -> bool:
    """
    Met à jour les informations issues de l'analyse automatique.

    Retourne True si au moins une information a changé.
    """

    with get_connection() as connection:
        current = connection.execute(
            """
            SELECT
                company,
                job_title,
                source
            FROM applications
            WHERE id = ?
            """,
            (application_id,),
        ).fetchone()

        if current is None:
            return False

        current_company = (current["company"] or "").strip()

        current_job_title = (current["job_title"] or "").strip()

        current_source = (current["source"] or "").strip()

        candidate_company = company.strip()
        candidate_source = source.strip()

        #
        # IMPORTANT :
        # on nettoie aussi l'ancien poste,
        # car il peut provenir d'une ancienne version
        # de l'extracteur.
        #
        cleaned_current_job = clean_job_title(current_job_title)

        cleaned_candidate_job = clean_job_title(job_title)

        current_score = job_title_score(cleaned_current_job)

        candidate_score = job_title_score(cleaned_candidate_job)

        #
        # Entreprise
        #
        new_company = candidate_company if candidate_company else current_company

        #
        # Source
        #
        new_source = candidate_source if candidate_source else current_source

        #
        # Poste
        #
        if candidate_score > current_score:
            new_job_title = cleaned_candidate_job

        elif candidate_score == current_score:
            #
            # À qualité égale, on préfère la version
            # nouvellement nettoyée.
            #
            new_job_title = cleaned_candidate_job or cleaned_current_job

        else:
            new_job_title = cleaned_current_job

        changed = (
            new_company != current_company
            or new_job_title != current_job_title
            or new_source != current_source
        )

        if not changed:
            return False

        connection.execute(
            """
            UPDATE applications
            SET
                company = ?,
                job_title = ?,
                source = ?
            WHERE id = ?
            """,
            (new_company, new_job_title, new_source, application_id),
        )

        connection.commit()

        return True


def update_application_details(
    application_id: int, company: str, job_title: str, source: str
) -> None:
    with get_connection() as connection:
        current = connection.execute(
            """
            SELECT
                company,
                job_title,
                source
            FROM applications
            WHERE id = ?
            """,
            (application_id,),
        ).fetchone()

        if current is None:
            return

        current_company = current["company"] or ""

        current_job_title = current["job_title"] or ""

        current_source = current["source"] or ""

        new_company = company.strip() if company.strip() else current_company

        candidate_job_title = job_title.strip()

        if job_title_score(candidate_job_title) > job_title_score(current_job_title):
            new_job_title = candidate_job_title
        else:
            new_job_title = current_job_title

        new_source = source.strip() if source.strip() else current_source

        connection.execute(
            """
            UPDATE applications
            SET
                company = ?,
                job_title = ?,
                source = ?
            WHERE id = ?
            """,
            (new_company, new_job_title, new_source, application_id),
        )

        connection.commit()


def set_manual_status(application_id: int, status: str, note: str = "") -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE applications
            SET
                manual_status = ?,
                manual_note = ?,
                manual_override = 1
            WHERE id = ?
            """,
            (status, note, application_id),
        )

        connection.commit()


def clear_manual_override(application_id: int) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE applications
            SET
                manual_status = NULL,
                manual_note = NULL,
                manual_override = 0
            WHERE id = ?
            """,
            (application_id,),
        )

        connection.commit()


# Candidatures : fusion et suppression


def merge_applications(source_application_id: int, target_application_id: int) -> None:
    if source_application_id == target_application_id:
        raise ValueError("Impossible de fusionner une candidature avec elle-même.")

    with get_connection() as connection:
        source = connection.execute(
            """
            SELECT *
            FROM applications
            WHERE id = ?
            """,
            (source_application_id,),
        ).fetchone()

        target = connection.execute(
            """
            SELECT *
            FROM applications
            WHERE id = ?
            """,
            (target_application_id,),
        ).fetchone()

        if source is None:
            raise ValueError(f"Candidature source {source_application_id} introuvable.")

        if target is None:
            raise ValueError(f"Candidature cible {target_application_id} introuvable.")

        #
        # Rattache tous les mails de la source
        # vers la candidature cible.
        #
        connection.execute(
            """
            UPDATE emails
            SET application_id = ?
            WHERE application_id = ?
            """,
            (target_application_id, source_application_id),
        )

        #
        # Si la cible n'a pas de poste mais la source oui,
        # on récupère le poste de la source.
        #
        target_job_title = target["job_title"] or ""
        source_job_title = source["job_title"] or ""

        if not target_job_title and source_job_title:
            connection.execute(
                """
                UPDATE applications
                SET job_title = ?
                WHERE id = ?
                """,
                (source_job_title, target_application_id),
            )

        #
        # On conserve la date la plus ancienne
        # comme date de première apparition.
        #
        first_seen = min(source["first_seen"], target["first_seen"])

        #
        # Et la date la plus récente
        # comme dernière mise à jour.
        #
        last_update = max(source["last_update"], target["last_update"])

        connection.execute(
            """
            UPDATE applications
            SET
                first_seen = ?,
                last_update = ?
            WHERE id = ?
            """,
            (first_seen, last_update, target_application_id),
        )

        #
        # Suppression du doublon.
        #
        connection.execute(
            """
            DELETE FROM applications
            WHERE id = ?
            """,
            (source_application_id,),
        )

        connection.commit()


def delete_application(application_id: int) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            DELETE FROM applications
            WHERE id = ?
            """,
            (application_id,),
        )

        connection.commit()

def get_imap_accounts() -> list[sqlite3.Row]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                email,
                provider,
                host,
                port,
                use_ssl,
                username,
                folder,
                enabled,
                created_at
            FROM imap_accounts
            ORDER BY email
            """
        ).fetchall()

        return list(rows)


def get_imap_account(
    account_id: int,
) -> sqlite3.Row | None:
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT *
            FROM imap_accounts
            WHERE id = ?
            """,
            (account_id,),
        ).fetchone()

def get_enabled_imap_accounts() -> list[sqlite3.Row]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                email,
                provider,
                host,
                port,
                use_ssl,
                username,
                folder,
                enabled
            FROM imap_accounts
            WHERE enabled = 1
            ORDER BY email
            """
        ).fetchall()

        return list(rows)
    
def update_imap_account(
    account_id: int,
    email: str,
    provider: str,
    host: str,
    port: int,
    use_ssl: bool,
    username: str,
    folder: str,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE imap_accounts
            SET
                email = ?,
                provider = ?,
                host = ?,
                port = ?,
                use_ssl = ?,
                username = ?,
                folder = ?
            WHERE id = ?
            """,
            (
                email.strip(),
                provider.strip(),
                host.strip(),
                port,
                1 if use_ssl else 0,
                username.strip(),
                folder.strip() or "INBOX",
                account_id,
            ),
        )

        connection.commit()

def create_imap_account(
    email: str,
    provider: str,
    host: str,
    port: int,
    use_ssl: bool,
    username: str,
    folder: str = "INBOX",
) -> int:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO imap_accounts (
                email,
                provider,
                host,
                port,
                use_ssl,
                username,
                folder
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                email.strip(),
                provider.strip(),
                host.strip(),
                port,
                1 if use_ssl else 0,
                username.strip(),
                folder.strip() or "INBOX",
            ),
        )

        connection.commit()

        if cursor.lastrowid is None:
            raise RuntimeError(
                "Impossible de créer le compte IMAP."
            )

        return int(cursor.lastrowid)