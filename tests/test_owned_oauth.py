"""Tests de sélection des identités OAuth."""

from unittest.mock import MagicMock, patch

from app.accounts import create_user
from app.connectors.imap_auth import authenticate_owned_imap
from app.database import get_connection
from tests.helpers import OfflineCase


class OwnedOAuthTests(OfflineCase):
    def setUp(self):
        super().setUp()

        self.alice = create_user("alice@example.invalid", "MotDePasseAlice2026!")

        self.bob = create_user("bob@example.invalid", "MotDePasseBob2026!")

        with get_connection() as connection:
            cursor = connection.execute(
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
                    "alice@gmail.com",
                    "gmail",
                    "imap.gmail.com",
                    "alice@gmail.com",
                    "oauth2",
                    self.alice,
                ),
            )

            assert cursor.lastrowid is not None

            self.account_id = cursor.lastrowid

    def test_other_user_cannot_authenticate(self):
        connection = MagicMock()

        with patch("app.connectors.imap_auth.get_owned_gmail_token") as token:
            with self.assertRaises(ValueError):
                authenticate_owned_imap(
                    connection, self.bob, self.account_id, "alice@gmail.com", None
                )

            token.assert_not_called()
            connection.authenticate.assert_not_called()

    def test_wrong_username_is_rejected(self):
        connection = MagicMock()

        with patch("app.connectors.imap_auth.get_owned_gmail_token") as token:
            with self.assertRaises(ValueError):
                authenticate_owned_imap(
                    connection, self.alice, self.account_id, "bob@gmail.com", None
                )

            token.assert_not_called()

    def test_owned_gmail_uses_correct_identity(self):
        connection = MagicMock()

        with patch(
            "app.connectors.imap_auth.get_owned_gmail_token",
            return_value="test-access-token",
        ) as token:
            authenticate_owned_imap(
                connection, self.alice, self.account_id, "alice@gmail.com", None
            )

        token.assert_called_once_with(self.alice, self.account_id, "alice@gmail.com")

        connection.authenticate.assert_called_once()

        mechanism, callback = connection.authenticate.call_args.args

        self.assertEqual(mechanism, "XOAUTH2")

        payload = callback(b"")

        self.assertIn(b"user=alice@gmail.com", payload)

        self.assertIn(b"Bearer test-access-token", payload)
