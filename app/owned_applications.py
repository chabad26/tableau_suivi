"""Accès aux candidatures avec isolation par utilisateur."""

import sqlite3
from datetime import datetime, timezone

from app.database import get_connection
from app.extractor import job_title_score


def require_user_id(user_id: int) -> int:
    """Refuse les identifiants absents ou invalides."""
    if type(user_id) is not int or user_id <= 0:
        raise ValueError("Identifiant utilisateur invalide.")

    return user_id

def update_user_application(
    user_id: int,
    application_id: int,
    company: str,
    job_title: str,
    source: str,
    status: str,
    note: str = "",
) -> bool:
    """Modifie uniquement une candidature appartenant à l'utilisateur."""

    user_id = require_user_id(user_id)

    if not company.strip():
        raise ValueError("Le nom de l'entreprise est obligatoire.")

    with get_connection() as connection:
        current = connection.execute(
            """
            SELECT company, job_title, source
            FROM applications
            WHERE id = ?
              AND user_id = ?
            """,
            (application_id, user_id),
        ).fetchone()

        if current is None:
            return False

        current_title = str(current["job_title"] or "")
        candidate_title = job_title.strip()

        new_title = (
            candidate_title
            if job_title_score(candidate_title) > job_title_score(current_title)
            else current_title
        )

        cursor = connection.execute(
            """
            UPDATE applications
            SET company = ?,
                job_title = ?,
                source = ?,
                manual_status = ?,
                manual_note = ?,
                manual_override = 1
            WHERE id = ?
              AND user_id = ?
            """,
            (
                company.strip(),
                new_title,
                source.strip() or str(current["source"] or ""),
                status,
                note,
                application_id,
                user_id,
            ),
        )

        return cursor.rowcount == 1

def get_user_applications(user_id: int) -> list[sqlite3.Row]:
    """Retourne uniquement les candidatures de cet utilisateur."""
    user_id = require_user_id(user_id)

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                a.*,
                (
                    SELECT e.mailbox
                    FROM emails AS e
                    WHERE e.application_id = a.id
                      AND e.user_id = a.user_id
                    ORDER BY e.received_at DESC
                    LIMIT 1
                ) AS mailbox
            FROM applications AS a
            WHERE a.user_id = ?
            ORDER BY a.last_update DESC
            """,
            (user_id,),
        ).fetchall()

    return list(rows)


def get_user_application(user_id: int, application_id: int) -> sqlite3.Row | None:
    """Retourne une candidature seulement si elle appartient à l'utilisateur."""
    user_id = require_user_id(user_id)

    with get_connection() as connection:
        return connection.execute(
            """
            SELECT *
            FROM applications
            WHERE id = ?
              AND user_id = ?
            """,
            (application_id, user_id),
        ).fetchone()


def get_user_application_emails(user_id: int, application_id: int) -> list[sqlite3.Row]:
    """Retourne les emails d'une candidature appartenant à l'utilisateur."""
    user_id = require_user_id(user_id)

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT e.*
            FROM emails AS e
            JOIN applications AS a
              ON a.id = e.application_id
             AND a.user_id = e.user_id
            WHERE a.id = ?
              AND a.user_id = ?
            ORDER BY e.received_at DESC
            """,
            (application_id, user_id),
        ).fetchall()

    return list(rows)


def create_user_application(
    user_id: int,
    company: str,
    job_title: str,
    source: str = "Manuel",
    status: str = "SENT",
    note: str = "",
) -> int:
    """Crée une candidature appartenant explicitement à l'utilisateur."""
    user_id = require_user_id(user_id)

    if not company.strip():
        raise ValueError("Le nom de l'entreprise est obligatoire.")

    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO applications (
                user_id,
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                user_id,
                company.strip(),
                job_title.strip(),
                source.strip() or "Manuel",
                now,
                now,
                status,
                status,
                note,
            ),
        )

        if cursor.lastrowid is None:
            raise RuntimeError("Création de candidature impossible.")

        return int(cursor.lastrowid)


def set_user_application_status(
    user_id: int, application_id: int, status: str, note: str = ""
) -> bool:
    """Modifie le statut uniquement si l'utilisateur est propriétaire."""
    user_id = require_user_id(user_id)

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE applications
            SET manual_status = ?,
                manual_note = ?,
                manual_override = 1
            WHERE id = ?
              AND user_id = ?
            """,
            (status, note, application_id, user_id),
        )

        return cursor.rowcount == 1


def delete_user_application(user_id: int, application_id: int) -> bool:
    """Supprime une candidature sans supprimer les emails associés."""
    user_id = require_user_id(user_id)

    with get_connection() as connection:
        cursor = connection.execute(
            """
            DELETE FROM applications
            WHERE id = ?
              AND user_id = ?
            """,
            (application_id, user_id),
        )

        return cursor.rowcount == 1
