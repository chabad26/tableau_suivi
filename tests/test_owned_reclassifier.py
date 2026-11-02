"""Réanalyse personnelle : SQL temporaire, aucune connexion aux messageries."""

import sqlite3
from datetime import datetime, timezone
from unittest.mock import patch

from app.accounts import set_user_active
from app.database import get_connection
from app.owned_applications import (
    create_user_application,
    get_user_application,
    set_user_application_status,
)
from app.owned_importer import import_user_emails
from app.owned_jobs import (
    enqueue_user_job,
    get_user_job,
    list_user_jobs,
    run_next_user_job,
)
from app.owned_reclassifier import reclassify_user_emails
from migrate_email_uniqueness import migrate
from tests.helpers import OfflineCase, fake_email


class OwnedReclassifierTests(OfflineCase):
    def setUp(self):
        super().setUp()
        self.alice = self.login_test_user("alice@example.invalid")
        self.bob = self.create_test_user("bob@example.invalid")
        import_user_emails(self.alice, [fake_email("<alice@example.invalid>")])
        import_user_emails(self.bob, [fake_email("<bob@example.invalid>")])
        with get_connection() as connection:
            self.alice_app = connection.execute(
                "SELECT application_id FROM emails WHERE user_id=?", (self.alice,)
            ).fetchone()[0]
            self.bob_app = connection.execute(
                "SELECT application_id FROM emails WHERE user_id=?", (self.bob,)
            ).fetchone()[0]

    def snapshot(self, table, user_id):
        with get_connection() as connection:
            return [
                tuple(row)
                for row in connection.execute(
                    f"SELECT * FROM {table} WHERE user_id=? ORDER BY id", (user_id,)
                ).fetchall()
            ]

    def test_only_owners_emails_and_applications_are_reclassified(self):
        before_emails = self.snapshot("emails", self.bob)
        before_apps = self.snapshot("applications", self.bob)
        with patch("app.owned_reclassifier.detect_status", return_value="REJECTED"):
            result = reclassify_user_emails(self.alice)
        self.assertEqual(
            (result.scanned, result.found, result.changed, result.missing), (1, 1, 1, 0)
        )
        self.assertEqual(
            get_user_application(self.alice, self.alice_app)["current_status"],
            "REJECTED",
        )
        self.assertEqual(self.snapshot("emails", self.bob), before_emails)
        self.assertEqual(self.snapshot("applications", self.bob), before_apps)

    def test_manual_status_note_and_details_are_preserved(self):
        set_user_application_status(
            self.alice, self.alice_app, "INTERVIEW", "Note manuelle"
        )
        before = dict(get_user_application(self.alice, self.alice_app))
        with (
            patch("app.owned_reclassifier.detect_status", return_value="REJECTED"),
            patch("app.owned_reclassifier.extract_application_data") as extract,
        ):
            reclassify_user_emails(self.alice)
        after = get_user_application(self.alice, self.alice_app)
        for key in (
            "company",
            "job_title",
            "source",
            "manual_status",
            "manual_note",
            "manual_override",
        ):
            self.assertEqual(after[key], before[key])
        self.assertEqual(after["current_status"], "REJECTED")
        extract.assert_not_called()

    def test_real_classifier_updates_status_from_archived_text(self):
        with get_connection() as connection:
            connection.execute(
                "UPDATE emails SET subject='Candidature non retenue', body='Votre candidature non retenue.' WHERE user_id=?",
                (self.alice,),
            )
        result = reclassify_user_emails(self.alice)
        self.assertEqual(result.changed, 1)
        self.assertEqual(
            get_user_application(self.alice, self.alice_app)["current_status"],
            "REJECTED",
        )

    def test_details_are_updated_without_degrading_job_title(self):
        with get_connection() as connection:
            connection.execute(
                "UPDATE applications SET job_title='Administrateur systèmes et réseaux' WHERE id=? AND user_id=?",
                (self.alice_app, self.alice),
            )
        with patch(
            "app.owned_reclassifier.extract_application_data",
            return_value=("Nouvelle entreprise", "", "Nouvelle source"),
        ):
            result = reclassify_user_emails(self.alice)
        row = get_user_application(self.alice, self.alice_app)
        self.assertEqual(row["company"], "Nouvelle entreprise")
        self.assertEqual(row["source"], "Nouvelle source")
        self.assertEqual(row["job_title"], "Administrateur systèmes et réseaux")
        self.assertEqual(result.applications_updated, 1)

    def test_missing_body_is_counted_without_fetch_or_destructive_update(self):
        with get_connection() as connection:
            connection.execute(
                "UPDATE emails SET body='' WHERE user_id=?", (self.alice,)
            )
        before = self.snapshot("emails", self.alice)
        with patch("app.owned_reclassifier.detect_status") as detect:
            result = reclassify_user_emails(self.alice)
        self.assertEqual(
            (result.scanned, result.found, result.missing, result.changed), (1, 0, 1, 0)
        )
        self.assertEqual(self.snapshot("emails", self.alice), before)
        detect.assert_not_called()

    def test_latest_email_uses_chronological_order_not_lexical_date_order(self):
        import_user_emails(self.alice, [fake_email("<alice-latest@example.invalid>")])
        with get_connection() as connection:
            connection.execute(
                "UPDATE emails SET subject='older', received_at='2026-11-02T12:00:00+02:00' WHERE message_id='<alice@example.invalid>' AND user_id=?",
                (self.alice,),
            )
            connection.execute(
                "UPDATE emails SET subject='newer', received_at='2026-11-02T10:30:00+00:00' WHERE message_id='<alice-latest@example.invalid>' AND user_id=?",
                (self.alice,),
            )
        with patch(
            "app.owned_reclassifier.detect_status",
            side_effect=lambda subject, body: (
                "REJECTED" if subject == "newer" else "RECEIVED"
            ),
        ):
            reclassify_user_emails(self.alice)
        row = get_user_application(self.alice, self.alice_app)
        self.assertEqual(row["current_status"], "REJECTED")
        self.assertEqual(row["last_update"], "2026-11-02T10:30:00+00:00")

    def test_invalid_date_does_not_replace_application_status_or_timestamp(self):
        before = get_user_application(self.alice, self.alice_app)
        with get_connection() as connection:
            connection.execute(
                "UPDATE emails SET received_at='date invalide' WHERE user_id=?",
                (self.alice,),
            )
        with patch("app.owned_reclassifier.detect_status", return_value="REJECTED"):
            reclassify_user_emails(self.alice)
        after = get_user_application(self.alice, self.alice_app)
        self.assertEqual(after["current_status"], before["current_status"])
        self.assertEqual(after["last_update"], before["last_update"])

    def test_duplicate_message_id_in_other_user_is_not_updated(self):
        with get_connection() as connection:
            migrate(connection)
            connection.execute(
                "UPDATE emails SET message_id='shared-id' WHERE user_id IN (?,?)",
                (self.alice, self.bob),
            )
        bob_before = self.snapshot("emails", self.bob)
        with patch("app.owned_reclassifier.detect_status", return_value="REJECTED"):
            reclassify_user_emails(self.alice)
        self.assertEqual(self.snapshot("emails", self.bob), bob_before)

    def test_orphan_email_is_reanalysed_without_recreating_application(self):
        with get_connection() as connection:
            connection.execute(
                "UPDATE emails SET application_id=NULL WHERE user_id=?", (self.alice,)
            )
        with patch("app.owned_reclassifier.detect_status", return_value="REJECTED"):
            result = reclassify_user_emails(self.alice)
        self.assertEqual(result.changed, 1)
        self.assertEqual(len(self.snapshot("applications", self.alice)), 1)

    def test_reanalysis_is_atomic_when_second_message_fails(self):
        import_user_emails(self.alice, [fake_email("<alice-second@example.invalid>")])
        before_emails = self.snapshot("emails", self.alice)
        before_apps = self.snapshot("applications", self.alice)
        with patch(
            "app.owned_reclassifier.detect_status",
            side_effect=["REJECTED", RuntimeError("fixture failure")],
        ):
            with self.assertRaises(RuntimeError):
                reclassify_user_emails(self.alice)
        self.assertEqual(self.snapshot("emails", self.alice), before_emails)
        self.assertEqual(self.snapshot("applications", self.alice), before_apps)

    def test_repeated_reanalysis_is_idempotent_and_preserves_bodies_and_dates(self):
        reclassify_user_emails(self.alice)
        emails = self.snapshot("emails", self.alice)
        apps = self.snapshot("applications", self.alice)
        result = reclassify_user_emails(self.alice)
        self.assertEqual((result.changed, result.applications_updated), (0, 0))
        self.assertEqual(self.snapshot("emails", self.alice), emails)
        self.assertEqual(self.snapshot("applications", self.alice), apps)

    def test_no_network_oauth_or_global_reanalysis_is_used(self):
        with (
            patch(
                "app.reclassifier.reclassify_emails",
                side_effect=AssertionError("Chemin global interdit"),
            ) as global_reanalysis,
            patch(
                "app.owned_scanner.scan_user_imap",
                side_effect=AssertionError("Réseau interdit"),
            ) as scan,
            patch(
                "app.oauth_store.read_oauth_cache",
                side_effect=AssertionError("Jetons interdits"),
            ) as oauth,
        ):
            result = reclassify_user_emails(self.alice)
        self.assertEqual(result.found, 1)
        global_reanalysis.assert_not_called()
        scan.assert_not_called()
        oauth.assert_not_called()

    def test_invalid_or_disabled_user_is_rejected(self):
        set_user_active(self.alice, False)
        before = self.snapshot("emails", self.alice)
        for user in (self.alice, 0, -1, 99999):
            with self.assertRaises(ValueError):
                reclassify_user_emails(user)
        self.assertEqual(self.snapshot("emails", self.alice), before)

    def test_manual_application_without_email_is_unchanged(self):
        app_id = create_user_application(
            self.alice, "Entreprise manuelle", "Poste manuel", status="SENT"
        )
        before = tuple(get_user_application(self.alice, app_id))
        reclassify_user_emails(self.alice)
        self.assertEqual(tuple(get_user_application(self.alice, app_id)), before)

    def test_route_enqueues_only_for_session_user_and_deduplicates(self):
        before = self.snapshot("emails", self.alice)
        for _ in range(2):
            self.assertEqual(
                self.client.post("/reclassify", data={"user_id": self.bob}).status_code,
                303,
            )
        jobs = list_user_jobs(self.alice)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["kind"], "reclassify")
        self.assertEqual(list_user_jobs(self.bob), [])
        self.assertEqual(self.snapshot("emails", self.alice), before)
        with patch("app.owned_reclassifier.detect_status", return_value="REJECTED"):
            self.assertTrue(run_next_user_job())
        self.assertEqual(get_user_job(self.alice, jobs[0]["id"])["state"], "succeeded")
        page = self.client.get("/jobs")
        self.assertIn("Réanalyse de mes emails archivés", page.text)
        self.assertIn("Emails archivés parcourus", page.text)

    def test_csrf_is_required_and_a_valid_token_allows_enqueue(self):
        import re

        self.app.config["WTF_CSRF_ENABLED"] = True
        self.assertEqual(self.client.post("/reclassify").status_code, 400)
        self.assertEqual(
            self.client.post("/reclassify", data={"csrf_token": "invalid"}).status_code,
            400,
        )
        self.assertEqual(list_user_jobs(self.alice), [])
        page = self.client.get("/")
        token = re.search(r'name="csrf_token"\s+value="([^"]+)"', page.text).group(1)
        self.assertEqual(
            self.client.post("/reclassify", data={"csrf_token": token}).status_code, 303
        )

    def test_anonymous_reanalysis_is_not_enqueued(self):
        self.assertEqual(self.app.test_client().post("/reclassify").status_code, 302)
        self.assertEqual(list_user_jobs(self.alice), [])

    def test_historical_unowned_reanalysis_job_is_never_executed(self):
        with get_connection() as connection:
            connection.execute(
                "INSERT INTO jobs (id,kind,state) VALUES ('legacy-reclassify','reclassify','queued')"
            )
        with patch("app.owned_reclassifier.reclassify_user_emails") as reclassify:
            self.assertFalse(run_next_user_job())
        reclassify.assert_not_called()
        with get_connection() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT state FROM jobs WHERE id='legacy-reclassify'"
                ).fetchone()[0],
                "queued",
            )

    def test_legacy_cross_user_link_cannot_update_another_application(self):
        before = self.snapshot("applications", self.bob)
        with get_connection() as connection:
            connection.execute(
                "UPDATE emails SET application_id=? WHERE user_id=?",
                (self.bob_app, self.alice),
            )
        with patch("app.owned_reclassifier.detect_status", return_value="REJECTED"):
            reclassify_user_emails(self.alice)
        self.assertEqual(self.snapshot("applications", self.bob), before)

    def test_worker_failure_does_not_log_archived_content_or_exception_secret(self):
        import contextlib
        import io

        job_id = enqueue_user_job(self.alice, "reclassify")
        before = self.snapshot("emails", self.alice)
        output = io.StringIO()
        with (
            contextlib.redirect_stdout(output),
            patch(
                "app.owned_reclassifier.detect_status",
                side_effect=RuntimeError("ARCHIVE-SECRET-FIXTURE"),
            ),
        ):
            self.assertTrue(run_next_user_job())
        job = get_user_job(self.alice, job_id)
        self.assertEqual(job["state"], "failed")
        self.assertNotIn("ARCHIVE-SECRET-FIXTURE", output.getvalue())
        self.assertNotIn("ARCHIVE-SECRET-FIXTURE", str(job["error"]))
        self.assertEqual(self.snapshot("emails", self.alice), before)

    def test_user_without_archived_emails_has_empty_successful_result(self):
        empty_user = self.create_test_user("empty@example.invalid")
        result = reclassify_user_emails(empty_user)
        self.assertEqual(
            (
                result.scanned,
                result.found,
                result.changed,
                result.applications_updated,
                result.missing,
            ),
            (0, 0, 0, 0, 0),
        )
