import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.connectors.imap import ImapAccount, scan_imap_account
from tests.helpers import OfflineCase


def fake_account(*, last_uid: int = 100, uid_validity: int | None = 777) -> ImapAccount:
    return ImapAccount(
        account_id=1,
        key="db:1",
        label="fixture@example.invalid",
        provider="imap",
        host="imap.example.invalid",
        port=993,
        use_ssl=True,
        username="fixture@example.invalid",
        auth_method="password",
        password="secret",
        folder="INBOX",
        last_uid=last_uid,
        uid_validity=uid_validity,
    )


class ImapConnectorTests(OfflineCase):
    def test_scan_requires_explicit_authentication_before_connecting(self):
        with patch("app.connectors.imap.connect_imap") as connect:
            with self.assertRaises(TypeError):
                scan_imap_account(fake_account(), datetime.now(timezone.utc))
            connect.assert_not_called()

    def test_incremental_scan_retries_after_failed_uid(self):
        connection = MagicMock()

        connection.select.return_value = ("OK", [b"4"])

        connection.response.return_value = ("OK", [b"777"])

        raw_message = (
            b"From: recrutement@example.invalid\r\n"
            b"Subject: Votre candidature\r\n"
            b"Date: Tue, 06 Oct 2026 10:00:00 +0000\r\n"
            b"Message-ID: <fixture@example.invalid>\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n"
            b"\r\n"
            b"Nous avons bien recu votre candidature.\r\n"
        )

        def uid_side_effect(command, *args):
            if command == "search":
                return ("OK", [b"101 102 103 104"])

            if command == "fetch":
                uid = str(args[0])

                if uid == "103":
                    return ("NO", [])

                return ("OK", [(b"fixture", raw_message)])

            raise AssertionError(f"Commande IMAP inattendue : {command}")

        connection.uid.side_effect = uid_side_effect

        account = fake_account()

        since = datetime(2026, 10, 1, tzinfo=timezone.utc)

        with (
            patch("app.connectors.imap.connect_imap", return_value=connection),
            patch("app.connectors.imap.should_analyze_email", return_value=True),
            patch(
                "app.connectors.imap.score_message",
                return_value=(
                    10,
                    ["fixture"],
                    "Nous avons bien reçu votre candidature.",
                ),
            ),
            patch("app.connectors.imap.detect_status", return_value="RECEIVED"),
        ):
            batch = scan_imap_account(account, since, authenticator=lambda conn: None)

        self.assertEqual(len(batch.emails), 3)

        connection.uid.assert_any_call("search", None, "UID", "101:*")

        connection.uid.assert_any_call("fetch", "101", "(BODY.PEEK[])")

        self.assertEqual(
            (batch.last_uid, batch.uid_validity, batch.failed_uids), (102, 777, 1)
        )

    def test_uidvalidity_change_forces_date_scan(self):

        connection = MagicMock()

        connection.select.return_value = ("OK", [b"2"])

        connection.response.return_value = ("OK", [b"999"])

        connection.uid.return_value = ("OK", [b""])

        account = fake_account(last_uid=450, uid_validity=777)
        from app.database import get_connection

        with get_connection() as db:
            db.execute(
                "INSERT INTO imap_accounts(id,email,host,username,last_uid,uid_validity) VALUES(1,'fixture@example.invalid','imap.example.invalid','fixture@example.invalid',450,777)"
            )

        since = datetime(2026, 10, 1, tzinfo=timezone.utc)

        with patch("app.connectors.imap.connect_imap", return_value=connection):
            batch = scan_imap_account(account, since, authenticator=lambda conn: None)

        self.assertEqual(batch.emails, [])

        connection.uid.assert_called_once_with("search", None, "SINCE", "01-Oct-2026")

        self.assertEqual((batch.last_uid, batch.uid_validity), (0, 999))
        connection.select.assert_called_once_with("INBOX", readonly=True)
        with get_connection() as db:
            self.assertEqual(
                tuple(
                    db.execute(
                        "SELECT last_uid,uid_validity FROM imap_accounts WHERE id=1"
                    ).fetchone()
                ),
                (450, 777),
            )


class TransportSecurityTests(unittest.TestCase):
    def test_starttls_is_required_before_authentication(self):
        from dataclasses import replace

        from app.connectors.imap import connect_imap

        connection = MagicMock()
        with patch("app.connectors.imap.imaplib.IMAP4", return_value=connection):
            self.assertIs(
                connect_imap(replace(fake_account(), use_ssl=False, port=143)),
                connection,
            )
        connection.starttls.assert_called_once()
        connection.login.assert_not_called()

    def test_starttls_failure_closes_connection_without_authentication(self):
        from dataclasses import replace

        from app.connectors.imap import connect_imap

        connection = MagicMock()
        connection.starttls.side_effect = RuntimeError("TLS unavailable")
        with patch("app.connectors.imap.imaplib.IMAP4", return_value=connection):
            with self.assertRaises(RuntimeError):
                connect_imap(replace(fake_account(), use_ssl=False, port=143))
        connection.shutdown.assert_called_once()
        connection.login.assert_not_called()


if __name__ == "__main__":
    unittest.main()
