"""File de travaux multi-utilisateur."""

import json
import sqlite3
from dataclasses import asdict
from uuid import uuid4

from app.database import get_connection
from app.owned_applications import require_user_id

ALLOWED_KINDS = frozenset({"scan"})


def check_active_user(connection: sqlite3.Connection, user_id: int) -> None:
    """Vérifie l'existence et l'activation du propriétaire."""

    user = connection.execute(
        """
        SELECT id
        FROM users
        WHERE id = ?
          AND active = 1
        """,
        (user_id,),
    ).fetchone()

    if user is None:
        raise ValueError("Utilisateur inexistant ou désactivé.")


def enqueue_user_job(user_id: int, kind: str) -> str:
    """Ajoute une tâche à la file personnelle."""

    user_id = require_user_id(user_id)

    if kind not in ALLOWED_KINDS:
        raise ValueError("Type de travail non autorisé.")

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")

        check_active_user(connection, user_id)

        # Une même tâche ne doit pas être lancée deux fois
        # simultanément par le même utilisateur.
        existing = connection.execute(
            """
            SELECT id
            FROM jobs
            WHERE user_id = ?
              AND kind = ?
              AND state IN ('queued', 'running')
            LIMIT 1
            """,
            (user_id, kind),
        ).fetchone()

        if existing is not None:
            return str(existing["id"])

        job_id = uuid4().hex

        connection.execute(
            """
            INSERT INTO jobs (
                id,
                user_id,
                kind,
                state
            )
            VALUES (?, ?, ?, 'queued')
            """,
            (job_id, user_id, kind),
        )

        return job_id


def list_user_jobs(user_id: int, limit: int = 50) -> list[sqlite3.Row]:
    """Liste uniquement les travaux du propriétaire."""

    user_id = require_user_id(user_id)

    if not 1 <= limit <= 200:
        raise ValueError("Limite invalide.")

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM jobs
            WHERE user_id = ?
            ORDER BY created_at DESC, rowid DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()

    return list(rows)


def get_user_job(user_id: int, job_id: str) -> sqlite3.Row | None:
    """Retourne un travail seulement s'il appartient à l'utilisateur."""

    user_id = require_user_id(user_id)

    with get_connection() as connection:
        return connection.execute(
            """
            SELECT *
            FROM jobs
            WHERE id = ?
              AND user_id = ?
            """,
            (job_id, user_id),
        ).fetchone()


def execute_user_job(user_id: int, kind: str) -> dict:
    """
    Exécute un travail personnel.

    Cette fonction ne dépend pas de Flask.
    """

    user_id = require_user_id(user_id)

    if kind != "scan":
        raise ValueError("Type de travail non autorisé.")

    from app.owned_importer import import_user_emails
    from app.owned_scanner import scan_user_imap
    from app.settings import API_START_DATE

    scan_result = scan_user_imap(user_id=user_id, since=API_START_DATE)

    # Un scan partiellement échoué ne doit pas être
    # déclaré comme une synchronisation complète.
    if scan_result.errors:
        raise RuntimeError("Un ou plusieurs comptes IMAP n'ont pas pu être analysés.")

    import_result = import_user_emails(
        user_id=user_id, detected_emails=scan_result.emails
    )

    return {
        **asdict(import_result),
        "scanned_accounts": scan_result.scanned_accounts,
        "skipped_accounts": scan_result.skipped_accounts,
    }


def claim_next_user_job() -> tuple[str, int, str] | None:
    """Réserve atomiquement le prochain travail personnel."""

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")

        # Le worker actuel est mono-exécution.
        if connection.execute(
            """
            SELECT 1
            FROM jobs
            WHERE state = 'running'
              AND user_id IS NOT NULL
            LIMIT 1
            """
        ).fetchone():
            return None

        job = connection.execute(
            """
            SELECT j.id, j.user_id, j.kind
            FROM jobs AS j
            JOIN users AS u
              ON u.id = j.user_id
            WHERE j.state = 'queued'
              AND j.user_id IS NOT NULL
              AND u.active = 1
              AND j.kind = 'scan'
            ORDER BY j.created_at, j.rowid
            LIMIT 1
            """
        ).fetchone()

        if job is None:
            return None

        job_id = str(job["id"])
        user_id = int(job["user_id"])
        kind = str(job["kind"])

        connection.execute(
            """
            UPDATE jobs
            SET state = 'running',
                started_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND user_id = ?
              AND state = 'queued'
            """,
            (job_id, user_id),
        )

        return job_id, user_id, kind


def finish_user_job(
    job_id: str,
    user_id: int,
    state: str,
    result: dict | None = None,
    error: str | None = None,
) -> None:
    """Enregistre le résultat du travail réservé."""

    if state not in {"succeeded", "failed"}:
        raise ValueError("État final invalide.")

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE jobs
            SET state = ?,
                result = ?,
                error = ?,
                finished_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND user_id = ?
              AND state = 'running'
            """,
            (
                state,
                json.dumps(result, ensure_ascii=False) if result is not None else None,
                error,
                job_id,
                user_id,
            ),
        )

        if cursor.rowcount != 1:
            raise RuntimeError("Travail introuvable ou état inattendu.")


def run_next_user_job() -> bool:
    """Exécute au maximum un travail personnel."""

    claimed = claim_next_user_job()

    if claimed is None:
        return False

    job_id, user_id, kind = claimed

    try:
        # Revérification juste avant l'exécution :
        # le compte peut avoir été désactivé entre-temps.
        with get_connection() as connection:
            check_active_user(connection, user_id)

        result = execute_user_job(user_id, kind)

    except Exception as exception:
        print(f"❌ Job {job_id} : {type(exception).__name__}: {exception}")

        finish_user_job(
            job_id,
            user_id,
            state="failed",
            error=(
                f"Échec ({type(exception).__name__}). "
                "Vérifier les connecteurs puis relancer."
            ),
        )

    else:
        finish_user_job(job_id, user_id, state="succeeded", result=result)

    return True


def recover_interrupted_user_jobs() -> None:
    """
    Marque les travaux interrompus comme échoués.

    Les anciens jobs sans propriétaire ne sont pas modifiés.
    """

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE jobs
            SET state = 'failed',
                error = 'Travail interrompu. Relancer manuellement.',
                finished_at = CURRENT_TIMESTAMP
            WHERE state = 'running'
              AND user_id IS NOT NULL
            """
        )
