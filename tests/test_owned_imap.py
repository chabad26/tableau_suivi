"""Tests d'isolation des comptes IMAP."""

from app.accounts import create_user
from app.database import get_connection
from app.owned_imap import (
    get_enabled_user_imap_accounts,
    get_user_imap_account,
    get_user_imap_accounts,
    set_user_imap_enabled,
    update_user_imap_health,
)
from tests.helpers import OfflineCase


class OwnedImapTests(OfflineCase):
    def setUp(self):
        super().setUp()

        self.alice = create_user("alice@example.invalid", "MotDePasseAlice2026!")

        self.bob = create_user("bob@example.invalid", "MotDePasseBob2026!")

        with get_connection() as connection:
            alice_account = connection.execute(
                """
                INSERT INTO imap_accounts (
                    email,
                    host,
                    username,
                    user_id
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    "alice-mail@example.invalid",
                    "imap.example.invalid",
                    "alice-mail@example.invalid",
                    self.alice,
                ),
            )

            bob_account = connection.execute(
                """
                INSERT INTO imap_accounts (
                    email,
                    host,
                    username,
                    user_id
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    "bob-mail@example.invalid",
                    "imap.example.invalid",
                    "bob-mail@example.invalid",
                    self.bob,
                ),
            )

            assert alice_account.lastrowid is not None
            assert bob_account.lastrowid is not None

            self.alice_account = int(alice_account.lastrowid)
            self.bob_account = int(bob_account.lastrowid)

    def test_accounts_are_private(self):
        alice_accounts = get_user_imap_accounts(self.alice)
        bob_accounts = get_user_imap_accounts(self.bob)

        self.assertEqual(len(alice_accounts), 1)
        self.assertEqual(len(bob_accounts), 1)

        self.assertEqual(alice_accounts[0]["email"], "alice-mail@example.invalid")

    def test_cannot_read_another_account(self):
        self.assertIsNone(get_user_imap_account(self.alice, self.bob_account))

    def test_cannot_disable_another_account(self):
        changed = set_user_imap_enabled(self.alice, self.bob_account, False)

        self.assertFalse(changed)

        bob_account = get_user_imap_account(self.bob, self.bob_account)

        assert bob_account is not None
        self.assertEqual(bob_account["enabled"], 1)

    def test_cannot_update_another_account_health(self):
        changed = update_user_imap_health(
            self.alice, self.bob_account, "error", "Test interdit"
        )

        self.assertFalse(changed)

        bob_account = get_user_imap_account(self.bob, self.bob_account)

        assert bob_account is not None
        self.assertNotEqual(bob_account["last_status"], "error")

    def test_enabled_accounts_are_scoped(self):
        set_user_imap_enabled(self.alice, self.alice_account, False)

        self.assertEqual(get_enabled_user_imap_accounts(self.alice), [])

        self.assertEqual(len(get_enabled_user_imap_accounts(self.bob)), 1)

    def test_invalid_user_is_rejected(self):
        with self.assertRaises(ValueError):
            get_user_imap_accounts(0)
