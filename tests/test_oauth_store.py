"""Tests du stockage OAuth privé."""

from app.accounts import create_user, set_user_active
from app.database import get_connection
from app.oauth_store import oauth_token_path, read_oauth_cache, write_oauth_cache
from tests.helpers import OfflineCase


class OAuthStoreTests(OfflineCase):
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

    def test_token_path_is_scoped_to_account(self):
        path = oauth_token_path(self.alice, self.account_id, "gmail")

        self.assertEqual(path.name, "gmail_token.json")

        self.assertEqual(path.parent.name, str(self.account_id))

    def test_alice_can_write_and_read_her_cache(self):
        write_oauth_cache(
            self.alice, self.account_id, "gmail", '{"fixture": "secret-test"}'
        )

        content = read_oauth_cache(self.alice, self.account_id, "gmail")

        self.assertEqual(content, '{"fixture": "secret-test"}')

        path = oauth_token_path(self.alice, self.account_id, "gmail")

        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_bob_cannot_read_alices_cache(self):
        write_oauth_cache(
            self.alice, self.account_id, "gmail", '{"fixture": "alice-only"}'
        )

        with self.assertRaises(ValueError):
            read_oauth_cache(self.bob, self.account_id, "gmail")

    def test_bob_cannot_overwrite_alices_cache(self):
        write_oauth_cache(
            self.alice, self.account_id, "gmail", '{"fixture": "original"}'
        )

        with self.assertRaises(ValueError):
            write_oauth_cache(
                self.bob, self.account_id, "gmail", '{"fixture": "intrusion"}'
            )

        self.assertEqual(
            read_oauth_cache(self.alice, self.account_id, "gmail"),
            '{"fixture": "original"}',
        )

    def test_wrong_provider_is_rejected(self):
        with self.assertRaises(ValueError):
            oauth_token_path(self.alice, self.account_id, "microsoft")

    def test_disabled_user_cannot_read_token(self):
        set_user_active(self.alice, False)

        with self.assertRaises(ValueError):
            read_oauth_cache(self.alice, self.account_id, "gmail")

    def test_missing_cache_returns_none(self):
        self.assertIsNone(read_oauth_cache(self.alice, self.account_id, "gmail"))
