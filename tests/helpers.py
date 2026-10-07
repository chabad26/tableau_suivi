import contextlib
import io
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import web

from app import database
from app.connectors import gmail, microsoft
from app.models import DetectedEmail


NOW = datetime(
    2026,
    9,
    16,
    12,
    tzinfo=timezone.utc,
)


def fake_email(
    message_id="<fixture@example.invalid>",
    **changes,
):
    email = DetectedEmail(
        mailbox="Fixture",
        date=NOW,
        sender="Recrutement <rh@example.invalid>",
        subject=(
            "Votre candidature au poste "
            "de Développeur Python"
        ),
        message_id=message_id,
        score=10,
        status="RECEIVED",
        reasons=["fixture"],
        body=(
            "Nous avons bien reçu "
            "votre candidature."
        ),
    )

    return replace(
        email,
        **changes,
    )


class OfflineCase(unittest.TestCase):

    def setUp(self):
        self.stack = contextlib.ExitStack()

        self.addCleanup(
            self.stack.close
        )

        self.root = Path(
            self.stack.enter_context(
                tempfile.TemporaryDirectory()
            )
        )

        self.stack.enter_context(
            patch.object(
                database,
                "DATABASE_PATH",
                self.root / "test.db",
            )
        )

        for module, attribute, filename in (
            (
                gmail,
                "TOKEN_FILE",
                "gmail-token.json",
            ),
            (
                gmail,
                "CREDENTIALS_FILE",
                "gmail-client.json",
            ),
            (
                microsoft,
                "TOKEN_CACHE_FILE",
                "microsoft-cache.json",
            ),
        ):
            self.stack.enter_context(
                patch.object(
                    module,
                    attribute,
                    self.root / filename,
                )
            )

        self.stack.enter_context(
            patch(
                "socket.socket.connect",
                side_effect=AssertionError(
                    "Réseau interdit dans les tests"
                ),
            )
        )

        self.stack.enter_context(
            patch.dict(
                web.app.config,
                TESTING=True,
            )
        )

        self.stack.enter_context(
            contextlib.redirect_stdout(
                io.StringIO()
            )
        )

        database.init_database()

        self.client = (
            web.app.test_client()
        )

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