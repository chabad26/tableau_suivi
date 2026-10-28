"""Tests de migration de l'unicité des emails."""

import sqlite3

from app.accounts import create_user
from app.database import get_connection
from app.owned_applications import create_user_application
from app.owned_importer import import_user_emails
from migrate_email_uniqueness import has_composite_unique, migrate
from tests.helpers import OfflineCase, fake_email


class EmailUniquenessTests(OfflineCase):
    def setUp(self):
        super().setUp()

        self.alice = create_user("alice@example.invalid", "MotDePasseAlice2026!")

        self.bob = create_user("bob@example.invalid", "MotDePasseBob2026!")

    def test_migration_preserves_existing_emails(self):
        message = fake_email("<historical@example.invalid>")

        import_user_emails(self.alice, [message])

        with get_connection() as connection:
            before = connection.execute(
                """
                SELECT id, user_id, message_id, body
                FROM emails
                """
            ).fetchone()

            assert before is not None
            before_values = tuple(before)

            migrated = migrate(connection)

        self.assertEqual(migrated, 1)

        with get_connection() as connection:
            after = connection.execute(
                """
                SELECT id, user_id, message_id, body
                FROM emails
                """
            ).fetchone()

            assert after is not None

            self.assertEqual(tuple(after), before_values)

    def test_two_users_can_store_same_message_id(self):
        with get_connection() as connection:
            migrate(connection)

        message = fake_email("<shared@example.invalid>")

        alice_result = import_user_emails(self.alice, [message])

        bob_result = import_user_emails(self.bob, [message])

        self.assertEqual(alice_result.added, 1)
        self.assertEqual(bob_result.added, 1)

        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT user_id
                FROM emails
                WHERE message_id = ?
                ORDER BY user_id
                """,
                ("<shared@example.invalid>",),
            ).fetchall()

        self.assertEqual(
            [row["user_id"] for row in rows], sorted([self.alice, self.bob])
        )

    def test_cross_user_application_link_is_rejected(self):
        alice_application = create_user_application(
            self.alice, "Entreprise Alice", "Développeuse"
        )

        with get_connection() as connection:
            migrate(connection)

        with self.assertRaises(sqlite3.IntegrityError):
            with get_connection() as connection:
                connection.execute(
                    """
                    INSERT INTO emails (
                        user_id,
                        message_id,
                        application_id,
                        mailbox,
                        received_at,
                        detected_status,
                        score
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.bob,
                        "<forbidden@example.invalid>",
                        alice_application,
                        "Fixture",
                        "2026-10-28T12:00:00+00:00",
                        "SENT",
                        10,
                    ),
                )

    def test_migration_is_idempotent(self):
        with get_connection() as connection:
            first = migrate(connection)

        with get_connection() as connection:
            second = migrate(connection)

            self.assertTrue(has_composite_unique(connection))

        self.assertEqual(first, 0)
        self.assertEqual(second, 0)

    def test_unowned_email_blocks_migration(self):
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO emails (
                    message_id,
                    mailbox,
                    received_at,
                    detected_status,
                    score
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "<unowned@example.invalid>",
                    "Fixture",
                    "2026-10-28T12:00:00+00:00",
                    "SENT",
                    10,
                ),
            )

        with get_connection() as connection:
            with self.assertRaises(RuntimeError):
                migrate(connection)

        with get_connection() as connection:
            self.assertFalse(has_composite_unique(connection))

    def test_deleting_application_detaches_emails_after_migration(self):
        """La suppression d'une candidature conserve ses emails."""

        message = fake_email("<detach@example.invalid>")

        import_user_emails(self.alice, [message])

        with get_connection() as connection:
            migrate(connection)

        with get_connection() as connection:
            application = connection.execute(
                """
                SELECT application_id
                FROM emails
                WHERE user_id = ?
                AND message_id = ?
                """,
                (self.alice, message.message_id),
            ).fetchone()

            assert application is not None
            application_id = application["application_id"]

            assert application_id is not None

            connection.execute(
                """
                DELETE FROM applications
                WHERE id = ?
                AND user_id = ?
                """,
                (application_id, self.alice),
            )

        with get_connection() as connection:
            email = connection.execute(
                """
                SELECT application_id
                FROM emails
                WHERE user_id = ?
                AND message_id = ?
                """,
                (self.alice, message.message_id),
            ).fetchone()

        assert email is not None

        self.assertIsNone(email["application_id"])
