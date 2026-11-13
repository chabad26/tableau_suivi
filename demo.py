"""Démonstration locale isolée ; aucune connexion sortante ni secret réel."""

import argparse
import getpass
import os
import secrets
import sys
import threading
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

MARKER = "Job Tracker Campus — démonstration fictive v1\n"
DEFAULT_DIRECTORY = Path(__file__).resolve().parent / ".demo-campus"


def check_directory(directory: Path) -> Path:
    directory = directory.absolute()
    for parent in (directory, *directory.parents):
        if parent.is_symlink():
            raise ValueError("Un chemin de démonstration ne peut pas être symbolique.")
    return directory


def configure_demo(directory: Path) -> None:
    """À appeler avant tout import applicatif, sans lire la base habituelle."""
    path = directory / "campus.sqlite3"
    if path.is_symlink():
        raise ValueError("Base symbolique interdite.")
    if "app.settings" in sys.modules:
        raise RuntimeError("La démonstration exige un processus séparé.")
    os.environ.update(
        {
            "DATABASE_PATH": str(path),
            "FLASK_SECRET_KEY": secrets.token_hex(32),
            "GMAIL_CREDENTIALS_FILE": str(directory / "unused-google-client.json"),
            "GMAIL_TOKEN_FILE": str(directory / "unused-google-token.json"),
            "MICROSOFT_TOKEN_CACHE_FILE": str(directory / "unused-microsoft.json"),
            "SCAN_START_DATE": "2026-11-01T00:00:00+00:00",
            "APP_HTTPS": "false",
        }
    )


def offline_transport(stack: ExitStack) -> None:
    from app.mail_providers import detect_provider
    from app.offline_imap import FakeImap

    stack.enter_context(
        patch(
            "socket.socket.connect",
            side_effect=RuntimeError("Réseau sortant interdit en démonstration."),
        )
    )
    stack.enter_context(
        patch(
            "socket.socket.connect_ex",
            side_effect=RuntimeError("Réseau sortant interdit en démonstration."),
        )
    )
    stack.enter_context(
        patch(
            "socket.socket.sendto",
            side_effect=RuntimeError("Réseau sortant interdit en démonstration."),
        )
    )
    stack.enter_context(patch("app.secrets.set_imap_password", return_value=None))
    stack.enter_context(
        patch("app.owned_scanner.authenticate_owned_imap", return_value=None)
    )
    stack.enter_context(
        patch("app.web.connectors.detect_provider_smart", side_effect=detect_provider)
    )
    stack.enter_context(
        patch(
            "app.owned_scanner.get_imap_password", return_value="offline-fixture-only"
        )
    )
    stack.enter_context(
        patch(
            "app.connectors.imap.connect_imap",
            side_effect=lambda account: FakeImap(account.label),
        )
    )


def seed_demo(alice_password: str, bob_password: str) -> None:
    """Initialise uniquement la base sélectionnée avant les imports applicatifs."""
    from app.accounts import create_user
    from app.database import get_connection
    from app.owned_applications import create_user_application
    from app.owned_jobs import enqueue_user_job, run_next_user_job
    from app.web import create_app
    from migrate.migrate_email_uniqueness import migrate

    create_app()
    with get_connection() as connection:
        migrate(connection)
    alice = create_user("alice@campus.invalid", alice_password)
    bob = create_user("bob@campus.invalid", bob_password)
    for user_id, prefix in [(alice, "Alice"), (bob, "Bob")]:
        for company, status in [
            ("Atelier des Alpes", "RECEIVED"),
            ("Campus Numérique", "INTERVIEW"),
            ("Studio Horizon", "REJECTED"),
            ("Tech Montagne", "ACCEPTED"),
        ]:
            create_user_application(
                user_id,
                f"{company} — {prefix}",
                "Administrateur systèmes",
                source="Démonstration",
                status=status,
            )
        address = f"{prefix.lower()}-mail@campus.invalid"
        with get_connection() as connection:
            connection.execute(
                "INSERT INTO imap_accounts (email, host, username, provider, user_id) VALUES (?, 'imap.demo.invalid', ?, 'ovh', ?)",
                (address, address, user_id),
            )
        enqueue_user_job(user_id, "scan")
        if not run_next_user_job():
            raise RuntimeError("Le travail de démonstration n’a pas été exécuté.")
    with get_connection() as connection:
        if (
            connection.execute(
                "SELECT COUNT(*) FROM jobs WHERE state = 'succeeded'"
            ).fetchone()[0]
            != 2
        ):
            raise RuntimeError("Import fictif incomplet.")
        # Conservé pour montrer que le worker personnel ignore les anciens travaux.
        connection.execute(
            "INSERT INTO jobs (id, kind, state) VALUES ('historique-demo', 'scan', 'queued')"
        )


def serve_demo(directory: Path) -> None:
    from app.owned_jobs import recover_interrupted_user_jobs, run_next_user_job
    from app.web import create_app

    app = create_app()
    app.config.update(DEMO_MODE=True, SESSION_COOKIE_NAME="job_tracker_demo_session")
    stop = threading.Event()

    def work():
        while not stop.is_set():
            if not run_next_user_job():
                stop.wait(0.5)

    # Un seul serveur/worker de démonstration peut utiliser cette base.
    import fcntl

    with (directory / "campus.worker.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        recover_interrupted_user_jobs()
        worker = threading.Thread(target=work, daemon=True)
        worker.start()
        try:
            app.run(host="127.0.0.1", port=5001, debug=False, use_reloader=False)
        finally:
            stop.set()
            worker.join(timeout=5)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["init", "serve"])
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY)
    args = parser.parse_args()
    directory = check_directory(args.directory)
    if args.action == "init":
        if directory.exists():
            parser.error(
                "Le dossier existe déjà : aucune donnée ne sera écrasée. Choisir un nouveau --directory."
            )
        if not sys.stdin.isatty():
            parser.error(
                "Initialisation interactive requise pour saisir les mots de passe sans affichage."
            )
        alice_password = getpass.getpass(
            "Mot de passe fictif Alice (12 caractères minimum) : "
        )
        bob_password = getpass.getpass(
            "Mot de passe fictif Bob (12 caractères minimum) : "
        )
        if min(len(alice_password), len(bob_password)) < 12:
            parser.error("Les mots de passe doivent contenir au moins 12 caractères.")
        directory.mkdir(parents=True, mode=0o700)
        (directory / "campus.sqlite3").touch(mode=0o600, exist_ok=False)
        configure_demo(directory)
        with ExitStack() as stack:
            offline_transport(stack)
            seed_demo(alice_password, bob_password)
        (directory / ".demo-campus").write_text(MARKER, encoding="utf-8")
        print(
            "Démonstration initialisée. Comptes : alice@campus.invalid et bob@campus.invalid."
        )
    else:
        marker = directory / ".demo-campus"
        if (
            not marker.is_file()
            or marker.is_symlink()
            or marker.read_text(encoding="utf-8") != MARKER
        ):
            parser.error("Dossier de démonstration non initialisé.")
        if not (directory / "campus.sqlite3").is_file():
            parser.error("Base de démonstration absente.")
        configure_demo(directory)
        with ExitStack() as stack:
            offline_transport(stack)
            serve_demo(directory)


if __name__ == "__main__":
    main()
