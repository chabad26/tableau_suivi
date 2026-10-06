import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from app import database
from app.connectors.imap import (
    ImapAccount,
    scan_imap,
    scan_imap_account,
)
from app.settings import API_START_DATE

def fake_account(
    *,
    last_uid: int = 100,
    uid_validity: int | None = 777,
) -> ImapAccount:
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

class ImapConnectorTests(unittest.TestCase):

    def setUp(self):
        database.init_database()

    def test_scan_without_accounts_returns_empty_list(self):
        with patch(
            "app.connectors.imap.get_enabled_imap_accounts",
            return_value=[],
        ):
            emails = scan_imap(
                API_START_DATE
            )

        self.assertEqual(
            emails,
            [],
        )

    def test_incremental_scan_retries_after_failed_uid(self):
        connection = MagicMock()

        connection.select.return_value = (
            "OK",
            [b"4"],
        )

        connection.response.return_value = (
            "OK",
            [b"777"],
        )

        raw_message = (
            b"From: recrutement@example.invalid\r\n"
            b"Subject: Votre candidature\r\n"
            b"Date: Tue, 06 Oct 2026 10:00:00 +0000\r\n"
            b"Message-ID: <fixture@example.invalid>\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n"
            b"\r\n"
            b"Nous avons bien recu votre candidature.\r\n"
        )

        def uid_side_effect(
            command,
            *args,
        ):
            if command == "search":
                return (
                    "OK",
                    [b"101 102 103 104"],
                )

            if command == "fetch":
                uid = str(args[0])

                if uid == "103":
                    return (
                        "NO",
                        [],
                    )

                return (
                    "OK",
                    [
                        (
                            b"fixture",
                            raw_message,
                        )
                    ],
                )

            raise AssertionError(
                f"Commande IMAP inattendue : {command}"
            )

        connection.uid.side_effect = (
            uid_side_effect
        )

        account = fake_account()

        since = datetime(
            2026,
            10,
            1,
            tzinfo=timezone.utc,
        )

        with (
            patch(
                "app.connectors.imap.connect_imap",
                return_value=connection,
            ),
            patch(
                "app.connectors.imap.authenticate_imap",
            ),
            patch(
                "app.connectors.imap.should_analyze_email",
                return_value=True,
            ),
            patch(
                "app.connectors.imap.score_message",
                return_value=(
                    10,
                    ["fixture"],
                    "Nous avons bien reçu votre candidature.",
                ),
            ),
            patch(
                "app.connectors.imap.detect_status",
                return_value="RECEIVED",
            ),
            patch(
                "app.connectors.imap.update_imap_sync_state",
            ) as update_sync,
        ):
            emails = scan_imap_account(
                account,
                since,
            )

        self.assertEqual(
            len(emails),
            3,
        )

        connection.uid.assert_any_call(
            "search",
            None,
            "UID",
            "101:*",
        )

        connection.uid.assert_any_call(
            "fetch",
            "101",
            "(BODY.PEEK[])",
        )

        update_sync.assert_called_once_with(
            1,
            102,
            777,
        )

    def test_uidvalidity_change_forces_date_scan(self):

        connection = MagicMock()

        connection.select.return_value = (
            "OK",
            [b"2"],
        )

        connection.response.return_value = (
            "OK",
            [b"999"],
        )

        connection.uid.return_value = (
            "OK",
            [b""],
        )

        account = fake_account(
            last_uid=450,
            uid_validity=777,
        )

        since = datetime(
            2026,
            10,
            1,
            tzinfo=timezone.utc,
        )

        with (
            patch(
                "app.connectors.imap.connect_imap",
                return_value=connection,
            ),
            patch(
                "app.connectors.imap.authenticate_imap",
            ),
            patch(
                "app.connectors.imap.update_imap_sync_state",
            ) as update_sync,
        ):
            emails = scan_imap_account(
                account,
                since,
            )

        self.assertEqual(
            emails,
            [],
        )

        connection.uid.assert_called_once_with(
            "search",
            None,
            "SINCE",
            "01-Oct-2026",
        )

        update_sync.assert_called_once_with(
            1,
            0,
            999,
        )


if __name__ == "__main__":
    unittest.main()

    