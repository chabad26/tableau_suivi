import contextlib
import io
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from app import database
from app.accounts import create_user
from app.connectors import gmail, microsoft
from app.models import DetectedEmail
from app.owned_applications import create_user_application
from app.web import create_app

NOW = datetime(2026, 9, 16, 12, tzinfo=timezone.utc)


def fake_email(message_id="<fixture@example.invalid>", **changes):
    email = DetectedEmail(
        mailbox="Fixture",
        date=NOW,
        sender="Recrutement <rh@example.invalid>",
        subject=("Votre candidature au poste de Développeur Python"),
        message_id=message_id,
        score=10,
        status="RECEIVED",
        reasons=["fixture"],
        body=("Nous avons bien reçu votre candidature."),
    )

    return replace(email, **changes)


class OfflineCase(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()

        self.addCleanup(self.stack.close)

        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))

        self.stack.enter_context(
            patch.object(database, "DATABASE_PATH", self.root / "test.db")
        )

        for module, attribute, filename in (
            (gmail, "TOKEN_FILE", "gmail-token.json"),
            (gmail, "CREDENTIALS_FILE", "gmail-client.json"),
            (microsoft, "TOKEN_CACHE_FILE", "microsoft-cache.json"),
        ):
            self.stack.enter_context(
                patch.object(module, attribute, self.root / filename)
            )

        self.stack.enter_context(
            patch(
                "socket.socket.connect",
                side_effect=AssertionError("Réseau interdit dans les tests"),
            )
        )

        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))

        self.app = create_app()
        self.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.client = self.app.test_client()

    def application(
        self,
        company="Entreprise Fictive",
        job_title="Développeur Python",
        source="Fixture",
        status="RECEIVED",
        date=NOW,
    ):
        return database.create_application(
            company=company,
            job_title=job_title,
            source=source,
            status=status,
            date=date,
        )

    def create_test_user(
        self,
        email: str = "test@example.invalid",
        password: str = "MotDePasseDeTest2026!",
    ) -> int:
        """Crée un utilisateur dans la base temporaire."""
        return create_user(email=email, password=password, role="student")

    def login_test_user(
        self,
        email: str = "test@example.invalid",
        password: str = "MotDePasseDeTest2026!",
        csrf_token: str | None = None,
    ) -> int:
        """Crée un compte et ouvre une session dans le client Flask."""
        user_id = self.create_test_user(email, password)

        data = {"email": email, "password": password}

        if csrf_token is not None:
            data["csrf_token"] = csrf_token

        response = self.client.post("/login", data=data)

        self.assertEqual(response.status_code, 303)

        return user_id
