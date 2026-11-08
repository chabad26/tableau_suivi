"""Tests de l'importateur multi-utilisateur."""

from app.accounts import create_user
from app.database import get_connection
from app.owned_importer import MessageIdConflictError, import_user_emails
from tests.helpers import OfflineCase, fake_email


class OwnedImporterTests(OfflineCase):
    def setUp(self):
        super().setUp()

        self.alice_id = create_user("alice@example.invalid", "MotDePasseAlice2026!")

        self.bob_id = create_user("bob@example.invalid", "MotDePasseBob2026!")

    def test_import_creates_owned_data(self):
        message = fake_email("<alice-1@example.invalid>")

        result = import_user_emails(self.alice_id, [message])

        self.assertEqual(result.detected, 1)
        self.assertEqual(result.added, 1)

        with get_connection() as connection:
            application = connection.execute(
                """
                SELECT user_id
                FROM applications
                LIMIT 1
                """
            ).fetchone()

            email = connection.execute(
                """
                SELECT user_id
                FROM emails
                LIMIT 1
                """
            ).fetchone()

        assert application is not None
        assert email is not None

        self.assertEqual(application["user_id"], self.alice_id)
        self.assertEqual(email["user_id"], self.alice_id)

    def test_next_import_replaces_invalid_automatic_title(self):
        import_user_emails(self.alice_id, [fake_email("<first@example.invalid>")])
        with get_connection() as connection:
            connection.execute(
                "UPDATE applications SET job_title='Votre candidature' WHERE user_id=?",
                (self.alice_id,),
            )
        import_user_emails(self.alice_id, [fake_email("<next@example.invalid>")])
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT job_title FROM applications WHERE user_id=?", (self.alice_id,)
            ).fetchall()
        self.assertEqual([row["job_title"] for row in rows], ["Développeur Python"])

    def test_import_keeps_manually_cleared_title(self):
        import_user_emails(self.alice_id, [fake_email("<first@example.invalid>")])
        with get_connection() as connection:
            connection.execute(
                "UPDATE applications SET job_title='', manual_override=1, manual_note='À conserver' WHERE user_id=?",
                (self.alice_id,),
            )
        import_user_emails(self.alice_id, [fake_email("<next@example.invalid>")])
        with get_connection() as connection:
            row = connection.execute(
                "SELECT job_title, manual_note FROM applications WHERE user_id=?",
                (self.alice_id,),
            ).fetchone()
        self.assertEqual(row["job_title"], "")
        self.assertEqual(row["manual_note"], "À conserver")

    def test_different_jobs_at_same_company_stay_separate(self):
        messages = [
            fake_email("<developer@example.invalid>"),
            fake_email(
                "<technician@example.invalid>",
                subject="Votre candidature au poste de Technicien réseaux",
            ),
        ]
        import_user_emails(self.alice_id, messages)
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT job_title FROM applications WHERE user_id=? ORDER BY id",
                (self.alice_id,),
            ).fetchall()
        self.assertEqual(
            [row["job_title"] for row in rows],
            ["Développeur Python", "Technicien réseaux"],
        )

    def test_duplicate_email_is_skipped(self):
        message = fake_email("<alice-2@example.invalid>")

        import_user_emails(self.alice_id, [message])

        result = import_user_emails(self.alice_id, [message])

        self.assertEqual(result.added, 0)
        self.assertEqual(result.skipped, 1)

    def test_duplicate_in_same_batch_is_skipped(self):
        message = fake_email("<alice-3@example.invalid>")

        result = import_user_emails(self.alice_id, [message, message])

        self.assertEqual(result.detected, 2)
        self.assertEqual(result.added, 1)
        self.assertEqual(result.skipped, 1)

    def test_other_users_message_id_fails_explicitly(self):
        message = fake_email("<shared@example.invalid>")

        import_user_emails(self.alice_id, [message])

        with self.assertRaises(MessageIdConflictError):
            import_user_emails(self.bob_id, [message])

        with get_connection() as connection:
            count = connection.execute(
                """
                SELECT COUNT(*)
                FROM emails
                WHERE user_id = ?
                """,
                (self.bob_id,),
            ).fetchone()[0]

        self.assertEqual(count, 0)

    def test_import_rolls_back_on_conflict(self):
        shared = fake_email("<shared@example.invalid>")
        new_email = fake_email("<bob-new@example.invalid>")

        import_user_emails(self.alice_id, [shared])

        # Le premier message serait normalement accepté.
        # Le second provoque un conflit.
        with self.assertRaises(MessageIdConflictError):
            import_user_emails(self.bob_id, [new_email, shared])

        with get_connection() as connection:
            count = connection.execute(
                """
                SELECT COUNT(*)
                FROM emails
                WHERE user_id = ?
                """,
                (self.bob_id,),
            ).fetchone()[0]

        # Aucun des deux messages n'a été conservé.
        self.assertEqual(count, 0)

    def test_disabled_user_cannot_import(self):
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE users
                SET active = 0
                WHERE id = ?
                """,
                (self.alice_id,),
            )

        with self.assertRaises(ValueError):
            import_user_emails(
                self.alice_id, [fake_email("<disabled@example.invalid>")]
            )

    def test_invalid_owner_is_rejected(self):
        with self.assertRaises(ValueError):
            import_user_emails(0, [fake_email("<invalid@example.invalid>")])
