from dataclasses import replace
from unittest.mock import patch
from app import database, importer, reclassifier
from tests.helpers import OfflineCase, fake_email


class StorageAndImportTests(OfflineCase):
    def test_schema_upgrade_is_idempotent(self):
        with database.get_connection() as connection:
            connection.execute("DROP TABLE emails")
            connection.execute("DROP TABLE applications")
            connection.execute(
                "CREATE TABLE applications (id INTEGER PRIMARY KEY, company TEXT NOT NULL, job_title TEXT, source TEXT, first_seen TEXT NOT NULL, last_update TEXT NOT NULL, current_status TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE emails (id INTEGER PRIMARY KEY, message_id TEXT UNIQUE NOT NULL, application_id INTEGER, mailbox TEXT NOT NULL, sender TEXT, subject TEXT, received_at TEXT NOT NULL, detected_status TEXT NOT NULL, score INTEGER NOT NULL)"
            )
        application_id = self.application()
        database.init_database()
        database.init_database()
        self.assertIsNotNone(database.get_application(application_id))
        self.assertTrue(database.save_email(fake_email(), application_id))
        self.assertEqual(
            database.get_application_emails(application_id)[0]["body"],
            fake_email().body,
        )

        database.delete_application(application_id)
        with database.get_connection() as connection:
            self.assertIsNone(
                connection.execute("SELECT application_id FROM emails").fetchone()[0]
            )
            import sqlite3

            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("UPDATE emails SET application_id = 123456")

    def test_import_deduplicates_sources_and_repeated_runs(self):

        email = fake_email()

        with (
            patch.object(
                importer,
                "scan_external_connectors",
                return_value=[
                    email,
                    replace(
                        email,
                        mailbox="IMAP fixture",
                    ),
                    fake_email(""),
                ],
            ),
            patch.object(
                importer,
                "extract_application_data",
                return_value=(
                    "Entreprise Fictive",
                    "Développeur Python",
                    "Fixture",
                ),
            ),
        ):
            self.assertEqual(
                importer.import_emails(),
                importer.ImportResult(1, 1, 1),
            )

            self.assertEqual(
                importer.import_emails(),
                importer.ImportResult(1, 0, 0),
            )

    def test_merge_and_delete_keep_emails(self):
        source = self.application("Source Fictive")
        target = self.application("Cible Fictive")
        database.save_email(fake_email(), source)
        database.merge_applications(source, target)
        self.assertIsNone(database.get_application(source))
        self.assertEqual(len(database.get_application_emails(target)), 1)
        database.delete_application(target)
        self.assertTrue(database.email_exists(fake_email().message_id))
        self.assertIsNone(database.get_application(target))

    def test_manual_status_survives_reclassification(self):
        application_id = self.application()
        database.save_email(fake_email(status="REJECTED"), application_id)
        database.set_manual_status(application_id, "INTERVIEW", "Note fictive")
        self.assertEqual(reclassifier.recompute_application_statuses(), 1)
        row = database.get_application(application_id)
        assert row is not None
        self.assertEqual(row["current_status"], "REJECTED")
        self.assertEqual(row["manual_status"], "INTERVIEW")
        self.assertTrue(row["manual_override"])

class EvolutionTests(OfflineCase):
    def test_foreign_keys_and_orphan_repair(self):
        import sqlite3

        app_id = self.application()
        database.save_email(fake_email(), app_id)
        database.delete_application(app_id)
        with database.get_connection() as connection:
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertIsNone(
                connection.execute("SELECT application_id FROM emails").fetchone()[0]
            )
            self.assertEqual(
                connection.execute("SELECT count(*) FROM emails").fetchone()[0], 1
            )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("UPDATE emails SET application_id = 999")
        # Simule une ancienne écriture effectuée sans intégrité activée.
        with sqlite3.connect(database.DATABASE_PATH) as connection:
            connection.execute("DROP TRIGGER emails_application_update")
            connection.execute("UPDATE emails SET application_id = 999")
        database.init_database()
        database.init_database()
        with database.get_connection() as connection:
            self.assertIsNone(
                connection.execute("SELECT application_id FROM emails").fetchone()[0]
            )
            self.assertEqual(
                connection.execute("PRAGMA foreign_key_check").fetchall(), []
            )

    def test_reanalysis_all_sources_preserves_manual_status(self):
        app_id = self.application()
        database.set_manual_status(app_id, "INTERVIEW", "Note privée fictive")
        for index, source in enumerate(["IMAP Gmail", "IMAP Microsoft", "IMAP générique"]):
            database.save_email(
                fake_email(f"<{index}@example.invalid>", mailbox=source), app_id
            )
        with (
            patch.object(reclassifier, "detect_status", return_value="REJECTED"),
        ):
            result = reclassifier.reclassify_emails()
        self.assertEqual((result.found, result.changed, result.missing), (3, 3, 0))
        row = database.get_application(app_id)
        assert row is not None
        self.assertEqual(row["manual_status"], "INTERVIEW")
        self.assertEqual(row["manual_note"], "Note privée fictive")
        self.assertEqual(row["current_status"], "REJECTED")

    def test_missing_body_is_counted_as_missing(self):
        app_id = self.application()

        database.save_email(
            fake_email(
                "<missing@fixture>",
                body="",
            ),
            app_id,
        )

        database.save_email(
            fake_email(
                "<available@fixture>",
                body="Nous avons bien reçu votre candidature.",
            ),
            app_id,
        )

        result = reclassifier.reclassify_emails()

        self.assertEqual(
            (
                result.scanned,
                result.found,
                result.missing,
            ),
            (
                2,
                1,
                1,
            ),
        )