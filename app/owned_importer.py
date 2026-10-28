"""Importation des emails avec isolation par utilisateur."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from app.database import get_connection
from app.extractor import company_key, extract_application_data
from app.models import DetectedEmail
from app.owned_applications import require_user_id
from migrate_email_uniqueness import has_composite_unique


class MessageIdConflictError(RuntimeError):
    """Le Message-ID existe déjà dans l'espace d'un autre utilisateur."""


@dataclass
class OwnedImportResult:
    detected: int
    added: int
    skipped: int


def normalized_date(value: datetime) -> datetime:
    """Normalise les dates en UTC avant comparaison."""

    if value.tzinfo is None:
        raise ValueError("Date d'email sans fuseau horaire.")

    return value.astimezone(timezone.utc)


def find_owned_application(
    connection: sqlite3.Connection, user_id: int, company: str, job_title: str
) -> int | None:
    """Retrouve une candidature uniquement chez son propriétaire."""

    rows = connection.execute(
        """
        SELECT id, company, job_title
        FROM applications
        WHERE user_id = ?
        ORDER BY last_update DESC
        """,
        (user_id,),
    ).fetchall()

    target_company = company_key(company)
    target_title = job_title.strip().casefold()

    for row in rows:
        if company_key(str(row["company"] or "")) != target_company:
            continue

        existing_title = str(row["job_title"] or "").strip().casefold()

        if target_title and existing_title and target_title != existing_title:
            continue

        return int(row["id"])

    return None


def create_owned_application(
    connection: sqlite3.Connection,
    user_id: int,
    company: str,
    job_title: str,
    source: str,
    email: DetectedEmail,
) -> int:
    """Crée une candidature sans quitter la transaction en cours."""

    received_at = normalized_date(email.date).isoformat()

    cursor = connection.execute(
        """
        INSERT INTO applications (
            user_id,
            company,
            job_title,
            source,
            first_seen,
            last_update,
            current_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, company, job_title, source, received_at, received_at, email.status),
    )

    if cursor.lastrowid is None:
        raise RuntimeError("Impossible de créer la candidature.")

    return int(cursor.lastrowid)


def update_owned_application(
    connection: sqlite3.Connection,
    user_id: int,
    application_id: int,
    email: DetectedEmail,
    job_title: str,
) -> None:
    """Met à jour le statut selon la date du message."""

    current = connection.execute(
        """
        SELECT last_update, job_title
        FROM applications
        WHERE id = ?
          AND user_id = ?
        """,
        (application_id, user_id),
    ).fetchone()

    if current is None:
        raise RuntimeError("Candidature introuvable pour cet utilisateur.")

    incoming_date = normalized_date(email.date)

    existing_date = normalized_date(datetime.fromisoformat(str(current["last_update"])))

    current_title = str(current["job_title"] or "")
    new_title = current_title or job_title

    if incoming_date >= existing_date:
        connection.execute(
            """
            UPDATE applications
            SET current_status = ?,
                last_update = ?,
                job_title = ?
            WHERE id = ?
              AND user_id = ?
            """,
            (
                email.status,
                incoming_date.isoformat(),
                new_title,
                application_id,
                user_id,
            ),
        )

    elif new_title != current_title:
        connection.execute(
            """
            UPDATE applications
            SET job_title = ?
            WHERE id = ?
              AND user_id = ?
            """,
            (new_title, application_id, user_id),
        )


def import_user_emails(
    user_id: int, detected_emails: list[DetectedEmail]
) -> OwnedImportResult:
    """
    Importe des messages pour un seul utilisateur.

    Aucune connexion réseau.
    Toutes les écritures sont atomiques.
    """

    user_id = require_user_id(user_id)

    added = 0
    skipped = 0
    seen_message_ids: set[str] = set()

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")

        # Vérification du compte au moment de l'import.
        owner = connection.execute(
            """
            SELECT id
            FROM users
            WHERE id = ?
              AND active = 1
            """,
            (user_id,),
        ).fetchone()

        if owner is None:
            raise ValueError("Utilisateur inexistant ou désactivé.")

        composite_unique = has_composite_unique(connection)

        for email in detected_emails:
            message_id = email.message_id.strip()

            if not message_id:
                skipped += 1
                continue

            # Déduplication à l'intérieur de cette importation.
            if message_id in seen_message_ids:
                skipped += 1
                continue

            seen_message_ids.add(message_id)

            # IMPORTANT :
            # Le schéma actuel possède encore UNIQUE(message_id).
            if composite_unique:
                existing = connection.execute(
                    """
                    SELECT user_id
                    FROM emails
                    WHERE user_id = ?
                      AND message_id = ?
                    """,
                    (user_id, message_id),
                ).fetchone()

            else:
                # Compatibilité avec les bases de test
                # qui utilisent encore UNIQUE(message_id).
                existing = connection.execute(
                    """
                    SELECT user_id
                    FROM emails
                    WHERE message_id = ?
                    """,
                    (message_id,),
                ).fetchone()

            if existing is not None:
                if existing["user_id"] == user_id:
                    skipped += 1
                    continue

                raise MessageIdConflictError(
                    "Le schéma SQLite utilise encore UNIQUE(message_id)."
                )

            company, job_title, source = extract_application_data(
                email.subject, email.sender, email.body
            )

            application_id = find_owned_application(
                connection, user_id, company, job_title
            )

            if application_id is None:
                application_id = create_owned_application(
                    connection, user_id, company, job_title, source, email
                )

            received_at = normalized_date(email.date).isoformat()

            connection.execute(
                """
                INSERT INTO emails (
                    user_id,
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    message_id,
                    application_id,
                    email.mailbox,
                    email.sender,
                    email.subject,
                    received_at,
                    email.status,
                    email.score,
                    email.body,
                ),
            )

            update_owned_application(
                connection, user_id, application_id, email, job_title
            )

            added += 1

    return OwnedImportResult(
        detected=len(detected_emails), added=added, skipped=skipped
    )
