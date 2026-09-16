"""File locale persistante ; un seul travail actif, aucune tâche dans Flask."""

import json
from dataclasses import asdict
from uuid import uuid4

from app.database import get_connection

KINDS = {
    "scan",
    "reclassify",
    "test:thunderbird",
    "test:gmail",
    "test:microsoft",
    "reconnect:gmail",
    "reconnect:microsoft",
}


def init_jobs() -> None:
    with get_connection() as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, kind TEXT NOT NULL, state TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            started_at TEXT, finished_at TEXT, result TEXT, error TEXT
        )""")


def enqueue(kind: str) -> str:
    if kind not in KINDS:
        raise ValueError("Travail inconnu")
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT id FROM jobs WHERE kind = ? AND state IN ('queued', 'running')",
            (kind,),
        ).fetchone()
        if existing:
            return str(existing["id"])
        job_id = uuid4().hex
        connection.execute(
            "INSERT INTO jobs (id, kind, state) VALUES (?, ?, ?)",
            (job_id, kind, "queued"),
        )
    return job_id


def list_jobs():
    with get_connection() as connection:
        return connection.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC, rowid DESC LIMIT 50"
        ).fetchall()


def execute(kind: str) -> dict:
    # Imports différés : le serveur ne lance jamais une authentification.
    from app.connectors.gmail import TOKEN_FILE, scan_gmail
    from app.connectors.microsoft import TOKEN_CACHE_FILE, scan_microsoft
    from app.importer import import_emails
    from app.reclassifier import reclassify_emails
    from app.scanner import scan_all_mailboxes
    from app.settings import API_START_DATE

    if kind == "scan":
        return asdict(import_emails())
    if kind == "reclassify":
        return asdict(reclassify_emails())
    action, connector = kind.split(":")
    if action == "reconnect":
        (TOKEN_FILE if connector == "gmail" else TOKEN_CACHE_FILE).unlink(
            missing_ok=True
        )
    if connector == "thunderbird":
        emails = scan_all_mailboxes()
    elif connector == "gmail":
        emails = scan_gmail(API_START_DATE)
    else:
        emails = scan_microsoft(API_START_DATE)
    return {"detected": len(emails)}


def run_next() -> bool:
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute("SELECT 1 FROM jobs WHERE state = 'running'").fetchone():
            return False
        job = connection.execute(
            "SELECT * FROM jobs WHERE state = 'queued' ORDER BY created_at, rowid LIMIT 1"
        ).fetchone()
        if job is None:
            return False
        connection.execute(
            "UPDATE jobs SET state = 'running', started_at = CURRENT_TIMESTAMP WHERE id = ?",
            (job["id"],),
        )
    try:
        result = json.dumps(execute(job["kind"]), ensure_ascii=False)
        state, error = "succeeded", None
    except Exception as exception:
        # Ne pas exposer URL OAuth, jeton ou contenu de message via une exception.
        state, result = "failed", None
        error = f"Échec ({type(exception).__name__}). Vérifier la configuration et la connexion, puis relancer."
    with get_connection() as connection:
        connection.execute(
            "UPDATE jobs SET state = ?, result = ?, error = ?, finished_at = CURRENT_TIMESTAMP WHERE id = ?",
            (state, result, error, job["id"]),
        )
    return True


def recover_interrupted() -> None:
    """Appelé uniquement après acquisition du verrou exclusif du worker."""
    with get_connection() as connection:
        connection.execute("""UPDATE jobs SET state = 'failed',
            error = 'Travail interrompu. Relancer manuellement.', finished_at = CURRENT_TIMESTAMP
            WHERE state = 'running'""")
