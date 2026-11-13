"""Retrait du statut historique sans perte d'archives ni événement artificiel."""

import sqlite3
from datetime import datetime, timedelta, timezone

from app.classifier import detect_status
from app.dashboard import dashboard_statistics
from app.database import get_connection, init_database
from app.maintenance import expire_stale_applications
from app.owned_applications import create_user_application, set_user_application_status
from app.owned_importer import import_user_emails
from app.statuses import STATUS_LABELS
from tests.helpers import OfflineCase, fake_email


class RetiredSentStatusTests(OfflineCase):
    def setUp(self):
        super().setUp()
        self.alice = self.login_test_user()
        self.bob = self.create_test_user("bob@example.invalid")

    def history(self):
        with get_connection() as db:
            return [
                tuple(row)
                for row in db.execute(
                    "SELECT * FROM application_status_history ORDER BY id"
                )
            ]

    def test_startup_migrates_both_owners_and_preserves_history_notes_and_dates(self):
        application = create_user_application(
            self.alice, "Archive Alice", "Analyste", note="Correction privée"
        )
        foreign = create_user_application(self.bob, "Archive Bob", "Technicien")
        import_user_emails(
            self.alice, [fake_email(status="SENT", html_body="<p>Archive</p>")]
        )
        with get_connection() as db:
            db.execute(
                "UPDATE applications SET current_status='SENT',manual_status='SENT' WHERE id IN (?,?)",
                (application, foreign),
            )
            # Simule le déclencheur installé par l'ancienne version.
            db.execute("DROP TRIGGER record_application_status_changed")
            db.execute("""CREATE TRIGGER record_application_status_changed AFTER UPDATE OF current_status,manual_status ON applications BEGIN
            INSERT INTO application_status_history(application_id,user_id,event_kind,previous_status,status)
            VALUES(NEW.id,NEW.user_id,'change',OLD.current_status,NEW.current_status); END""")
            before = [
                tuple(row)
                for row in db.execute(
                    "SELECT id,user_id,manual_note,manual_override,first_seen,last_update FROM applications ORDER BY id"
                )
            ]
        events = self.history()
        init_database()
        with get_connection() as db:
            after = [
                tuple(row)
                for row in db.execute(
                    "SELECT id,user_id,manual_note,manual_override,first_seen,last_update FROM applications ORDER BY id"
                )
            ]
            self.assertEqual(after, before)
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) FROM applications WHERE current_status='SENT' OR manual_status='SENT'"
                ).fetchone()[0],
                0,
            )
            email = db.execute(
                "SELECT detected_status,html_body,body FROM emails"
            ).fetchone()
            self.assertEqual(
                tuple(email), ("RECEIVED", "<p>Archive</p>", fake_email().body)
            )
        self.assertEqual(self.history(), events)
        init_database()
        self.assertEqual(self.history(), events)
        set_user_application_status(self.alice, application, "INTERVIEW")
        self.assertEqual(self.history()[-1][4:6], ("RECEIVED", "INTERVIEW"))

    def test_legacy_history_is_aggregated_with_received_without_rewriting_it(self):
        application = create_user_application(self.alice, "Archive", "Analyste")
        with get_connection() as db:
            for status in ("SENT", "RECEIVED"):
                db.execute(
                    "INSERT INTO application_status_history(application_id,user_id,event_kind,previous_status,status) VALUES(?,?,'change','OTHER',?)",
                    (application, self.alice, status),
                )
        before = self.history()
        data = dashboard_statistics(self.alice)
        self.assertNotIn("SENT", data["counts"])
        self.assertEqual(sum(row["counts"]["RECEIVED"] for row in data["timeline"]), 2)
        self.assertEqual(self.history(), before)

    def test_removed_status_is_not_offered_or_accepted_by_the_web(self):
        self.assertNotIn("SENT", STATUS_LABELS)
        page = self.client.get("/application/new")
        self.assertNotIn('value="SENT"', page.text)
        self.assertNotIn("Envoyée", page.text)
        self.assertEqual(
            self.client.post(
                "/application/new", data={"company": "Test", "status": "SENT"}
            ).status_code,
            400,
        )
        application = create_user_application(self.alice, "Test", "Analyste")
        self.assertEqual(
            self.client.post(
                f"/application/{application}/edit",
                data={"company": "Test", "status": "SENT"},
            ).status_code,
            400,
        )

    def test_submission_receipts_are_received_and_legacy_manual_can_expire(self):
        for subject in (
            "Votre candidature a été envoyée à ACME",
            "Your application has been sent",
            "Application successfully submitted",
        ):
            self.assertEqual(detect_status(subject, ""), "RECEIVED")
        application = create_user_application(
            self.alice, "Ancienne", "Analyste", note="Note conservée"
        )
        rejected = create_user_application(
            self.alice, "Refus", "Analyste", status="REJECTED"
        )
        old = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        with get_connection() as db:
            db.execute(
                "UPDATE applications SET current_status='SENT',manual_status='SENT',last_update=? WHERE id=?",
                (old, application),
            )
            db.execute(
                "UPDATE applications SET last_update=? WHERE id=?", (old, rejected)
            )
        init_database()
        self.assertEqual(expire_stale_applications(self.alice), 1)
        with get_connection() as db:
            row = db.execute(
                "SELECT manual_status,manual_note FROM applications WHERE id=?",
                (application,),
            ).fetchone()
            self.assertEqual(tuple(row), ("EXPIRED", "Note conservée"))
            self.assertEqual(
                db.execute(
                    "SELECT manual_status FROM applications WHERE id=?", (rejected,)
                ).fetchone()[0],
                "REJECTED",
            )

    def test_failed_migration_rolls_back_statuses_and_trigger_changes(self):
        application = create_user_application(self.alice, "Archive", "Analyste")
        import_user_emails(self.alice, [fake_email(status="SENT")])
        with get_connection() as db:
            db.execute(
                "UPDATE applications SET current_status='SENT',manual_status='SENT' WHERE id=?",
                (application,),
            )
            db.execute(
                "CREATE TRIGGER refuse_status_migration BEFORE UPDATE OF detected_status ON emails BEGIN SELECT RAISE(ABORT, 'fixture'); END"
            )
            before = [
                tuple(row)
                for row in db.execute(
                    "SELECT name,sql FROM sqlite_master WHERE type='trigger' ORDER BY name"
                )
            ]
        with self.assertRaises(sqlite3.IntegrityError):
            init_database()
        with get_connection() as db:
            self.assertEqual(
                tuple(
                    db.execute(
                        "SELECT current_status,manual_status FROM applications WHERE id=?",
                        (application,),
                    ).fetchone()
                ),
                ("SENT", "SENT"),
            )
            self.assertEqual(
                db.execute("SELECT detected_status FROM emails").fetchone()[0], "SENT"
            )
            self.assertEqual(
                [
                    tuple(row)
                    for row in db.execute(
                        "SELECT name,sql FROM sqlite_master WHERE type='trigger' ORDER BY name"
                    )
                ],
                before,
            )
