"""Tests du scanner IMAP personnel."""

from datetime import datetime, timezone
from unittest.mock import patch

from app.accounts import create_user
from app.database import get_connection
from app.owned_scanner import build_user_imap_account, scan_user_imap
from tests.helpers import OfflineCase, fake_email

SINCE = datetime(2026, 10, 1, tzinfo=timezone.utc)


class OwnedScannerTests(OfflineCase):
    def setUp(self):
        super().setUp()

        self.alice_id = create_user("alice@example.invalid", "MotDePasseAlice2026!")

        self.bob_id = create_user("bob@example.invalid", "MotDePasseBob2026!")

        with get_connection() as connection:
            alice_cursor = connection.execute(
                """
                INSERT INTO imap_accounts (
                    email,
                    provider,
                    host,
                    username,
                    auth_method,
                    user_id
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "alice-mail@example.invalid",
                    "ovh",
                    "imap.example.invalid",
                    "alice-mail@example.invalid",
                    "password",
                    self.alice_id,
                ),
            )

            bob_cursor = connection.execute(
                """
                INSERT INTO imap_accounts (
                    email,
                    provider,
                    host,
                    username,
                    auth_method,
                    user_id
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "bob-mail@example.invalid",
                    "sfr",
                    "imap.example.invalid",
                    "bob-mail@example.invalid",
                    "password",
                    self.bob_id,
                ),
            )

            assert alice_cursor.lastrowid is not None
            assert bob_cursor.lastrowid is not None

            self.alice_account_id = alice_cursor.lastrowid
            self.bob_account_id = bob_cursor.lastrowid

    def test_alice_cannot_load_bob_account(self):
        with patch("app.owned_scanner.get_imap_password") as get_password:
            with self.assertRaises(ValueError):
                build_user_imap_account(self.alice_id, self.bob_account_id)

            get_password.assert_not_called()

    def test_alice_scans_only_her_account(self):
        message = fake_email("<alice-scan@example.invalid>")

        with (
            patch(
                "app.owned_scanner.get_imap_password", return_value="test-password"
            ) as get_password,
            patch(
                "app.owned_scanner.scan_imap_account", return_value=[message]
            ) as scan,
        ):
            result = scan_user_imap(self.alice_id, SINCE)

        self.assertEqual(result.scanned_accounts, 1)
        self.assertEqual(len(result.emails), 1)

        get_password.assert_called_once_with(self.alice_account_id)

        scan.assert_called_once()

        args, kwargs = scan.call_args

        account = args[0]

        self.assertTrue(callable(kwargs["authenticator"]))

        self.assertEqual(account.account_id, self.alice_account_id)

        self.assertFalse(kwargs["persist_sync_state"])

    def test_oauth_account_uses_private_authenticator(self):
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE imap_accounts
                SET provider = 'gmail',
                    auth_method = 'oauth2'
                WHERE id = ?
                """,
                (self.alice_account_id,),
            )

        with (
            patch("app.owned_scanner.get_imap_password") as get_password,
            patch("app.owned_scanner.scan_imap_account", return_value=[]) as scan,
        ):
            result = scan_user_imap(self.alice_id, SINCE)

        self.assertEqual(result.scanned_accounts, 1)

        get_password.assert_not_called()

        scan.assert_called_once()

        _, kwargs = scan.call_args

        self.assertFalse(kwargs["persist_sync_state"])

        self.assertTrue(callable(kwargs["authenticator"]))

    def test_disabled_account_is_not_scanned(self):
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE imap_accounts
                SET enabled = 0
                WHERE id = ?
                """,
                (self.alice_account_id,),
            )

        with patch("app.owned_scanner.scan_imap_account") as scan:
            result = scan_user_imap(self.alice_id, SINCE)

        self.assertEqual(result.scanned_accounts, 0)
        scan.assert_not_called()

    def test_invalid_user_is_rejected(self):
        with self.assertRaises(ValueError):
            scan_user_imap(0, SINCE)


def test_disabled_user_cannot_scan(self):
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE users
            SET active = 0
            WHERE id = ?
            """,
            (self.alice_id,),
        )

    with patch("app.owned_scanner.scan_imap_account") as scan:
        with self.assertRaises(ValueError):
            scan_user_imap(self.alice_id, SINCE)

        scan.assert_not_called()
