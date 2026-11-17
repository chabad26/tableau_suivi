import sqlite3
from contextlib import closing

from app import database
from tests.helpers import OfflineCase, fake_email


class ConnectionTests(OfflineCase):
    def test_connection_is_closed(self):
        with database.get_connection() as connection:
            result = connection.execute("SELECT 1").fetchone()

            self.assertEqual(result[0], 1)

        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")

    def test_transaction_is_committed(self):
        with database.get_connection() as connection:
            connection.execute(
                """
                INSERT INTO applications (
                    company,
                    job_title,
                    source,
                    first_seen,
                    last_update,
                    current_status
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "Entreprise test",
                    "Développeur",
                    "Test",
                    "2026-10-28T08:00:00+00:00",
                    "2026-10-28T08:00:00+00:00",
                    "RECEIVED",
                ),
            )

        with database.get_connection() as connection:
            count = connection.execute(
                """
                SELECT COUNT(*)
                FROM applications
                WHERE company = ?
                """,
                ("Entreprise test",),
            ).fetchone()[0]

        self.assertEqual(count, 1)

    def test_transaction_is_rolled_back(self):
        with self.assertRaises(RuntimeError):
            with database.get_connection() as connection:
                connection.execute(
                    """
                    INSERT INTO applications (
                        company,
                        job_title,
                        source,
                        first_seen,
                        last_update,
                        current_status
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "Entreprise annulée",
                        "Administrateur système",
                        "Test",
                        "2026-10-28T08:00:00+00:00",
                        "2026-10-28T08:00:00+00:00",
                        "RECEIVED",
                    ),
                )

                raise RuntimeError("Erreur simulée")

        with database.get_connection() as connection:
            count = connection.execute(
                """
                SELECT COUNT(*)
                FROM applications
                WHERE company = ?
                """,
                ("Entreprise annulée",),
            ).fetchone()[0]

        self.assertEqual(count, 0)


class SchemaUpgradeTests(OfflineCase):
    def insert_legacy_email(self, application_id):
        email = fake_email()
        with database.get_connection() as db:
            db.execute(
                "INSERT INTO emails(message_id,application_id,mailbox,sender,subject,received_at,detected_status,score,body) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    email.message_id,
                    application_id,
                    email.mailbox,
                    email.sender,
                    email.subject,
                    email.date.isoformat(),
                    email.status,
                    email.score,
                    email.body,
                ),
            )

    def test_schema_upgrade_is_idempotent(self):
        with database.get_connection() as db:
            db.execute("DROP TABLE emails")
            db.execute("DROP TABLE applications")
            db.execute(
                "CREATE TABLE applications (id INTEGER PRIMARY KEY, company TEXT NOT NULL, job_title TEXT, source TEXT, first_seen TEXT NOT NULL, last_update TEXT NOT NULL, current_status TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE emails (id INTEGER PRIMARY KEY, message_id TEXT UNIQUE NOT NULL, application_id INTEGER, mailbox TEXT NOT NULL, sender TEXT, subject TEXT, received_at TEXT NOT NULL, detected_status TEXT NOT NULL, score INTEGER NOT NULL)"
            )
        application = self.application()
        database.init_database()
        database.init_database()
        self.insert_legacy_email(application)
        with database.get_connection() as db:
            self.assertEqual(
                db.execute("SELECT body FROM emails").fetchone()[0], fake_email().body
            )
            db.execute("DELETE FROM applications WHERE id=?", (application,))
            self.assertIsNone(
                db.execute("SELECT application_id FROM emails").fetchone()[0]
            )
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE emails SET application_id=123456")

    def test_foreign_keys_and_orphan_repair(self):
        application = self.application()
        self.insert_legacy_email(application)
        with database.get_connection() as db:
            self.assertEqual(db.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE emails SET application_id=999")
        # Ancienne écriture sans intégrité activée, simulée dans la base temporaire.
        with closing(sqlite3.connect(database.DATABASE_PATH)) as db, db:
            db.execute("DROP TRIGGER emails_application_update")
            db.execute("UPDATE emails SET application_id=999")
        database.init_database()
        database.init_database()
        with database.get_connection() as db:
            self.assertIsNone(
                db.execute("SELECT application_id FROM emails").fetchone()[0]
            )
            self.assertEqual(db.execute("SELECT count(*) FROM emails").fetchone()[0], 1)
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
