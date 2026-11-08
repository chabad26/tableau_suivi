"""Connexion et suivi non bloquants, sans réseau ni secrets réels."""

import sqlite3
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.database import get_connection
from app.owned_importer import import_user_emails
from app.owned_jobs import enqueue_user_job, list_user_jobs, run_next_user_job
from tests.helpers import OfflineCase, fake_email


class LoginSyncTests(OfflineCase):
    def setUp(self):
        super().setUp()
        self.app.config["AUTO_SYNC_ON_LOGIN"] = True
        self.alice = self.create_test_user("alice@example.invalid")
        self.bob = self.create_test_user("bob@example.invalid")
        with get_connection() as connection:
            connection.execute(
                "INSERT INTO imap_accounts (email,host,username,provider,user_id) VALUES ('alice@mail.invalid','imap.demo.invalid','alice@mail.invalid','ovh',?)",
                (self.alice,),
            )

    def login(self, password="MotDePasseDeTest2026!"):
        return self.client.post(
            "/login", data={"email": "alice@example.invalid", "password": password}
        )

    def test_login_only_queues_local_work_before_scan(self):
        with (
            patch(
                "app.owned_scanner.scan_user_imap",
                side_effect=AssertionError("No network in HTTP"),
            ),
            patch(
                "app.owned_reclassifier.reclassify_user_emails",
                side_effect=AssertionError("No processing in HTTP"),
            ),
        ):
            self.assertEqual(self.login().status_code, 303)
        with get_connection() as connection:
            jobs = connection.execute(
                "SELECT user_id,kind FROM jobs ORDER BY rowid"
            ).fetchall()
        self.assertEqual(
            [(r["user_id"], r["kind"]) for r in jobs],
            [(self.alice, "reclassify"), (self.alice, "scan")],
        )
        self.assertEqual(list_user_jobs(self.bob), [])
        self.assertIn('id="login-sync"', self.client.get("/account").text)
        self.assertEqual(
            self.client.get("/jobs/login-sync").json,
            {"pending": True, "failed": False, "queued": True},
        )

    def test_invalid_login_does_not_queue(self):
        self.assertEqual(self.login("wrong").status_code, 200)
        self.assertEqual(list_user_jobs(self.alice), [])

    def test_relogin_reuses_pending_jobs(self):
        self.login()
        first = {r["id"] for r in list_user_jobs(self.alice)}
        self.client.post("/logout")
        self.login()
        self.assertEqual({r["id"] for r in list_user_jobs(self.alice)}, first)

    def test_no_enabled_mailbox_still_reclassifies_without_scan(self):
        with get_connection() as connection:
            connection.execute(
                "UPDATE imap_accounts SET enabled=0 WHERE user_id=?", (self.alice,)
            )
        self.login()
        self.assertEqual(
            [r["kind"] for r in list_user_jobs(self.alice)], ["reclassify"]
        )
        self.assertTrue(run_next_user_job())
        self.assertEqual(
            self.client.get("/jobs/login-sync").json,
            {"pending": False, "failed": False, "queued": False},
        )
        self.assertNotIn('id="login-sync"', self.client.get("/account").text)

    def test_offline_scan_does_not_prevent_local_reanalysis_or_http(self):
        import_user_emails(
            self.alice,
            [fake_email(date=datetime.now(timezone.utc) - timedelta(days=31))],
        )
        self.login()
        self.assertTrue(run_next_user_job())
        self.assertEqual(list_user_jobs(self.alice)[1]["state"], "succeeded")
        with get_connection() as connection:
            status = connection.execute(
                "SELECT current_status FROM applications WHERE user_id=?", (self.alice,)
            ).fetchone()
        self.assertEqual(status["current_status"], "EXPIRED")
        with patch(
            "app.owned_scanner.scan_user_imap",
            side_effect=OSError("PRIVATE-NETWORK-DETAIL"),
        ):
            self.assertTrue(run_next_user_job())
        status = self.client.get("/jobs/login-sync")
        self.assertEqual(
            status.json, {"pending": False, "failed": True, "queued": False}
        )
        self.assertNotIn("PRIVATE", status.text)
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/account").status_code, 200)

    def test_failed_queue_does_not_prevent_login(self):
        with patch(
            "app.web.auth.enqueue_user_job",
            side_effect=sqlite3.OperationalError("fixture"),
        ):
            self.assertEqual(self.login().status_code, 303)
        self.assertEqual(self.client.get("/account").status_code, 200)

    def test_status_is_authenticated_and_owner_scoped(self):
        self.assertEqual(self.client.get("/jobs/login-sync").status_code, 302)
        foreign = enqueue_user_job(self.bob, "scan")
        self.login()
        with self.client.session_transaction() as session:
            session["login_sync_jobs"] = [foreign]
        status = self.client.get("/jobs/login-sync")
        self.assertEqual(
            status.json, {"pending": False, "failed": True, "queued": False}
        )
        self.assertNotIn(foreign, status.text)

    def test_missing_csrf_does_not_queue(self):
        self.app.config["WTF_CSRF_ENABLED"] = True
        self.assertEqual(self.login().status_code, 400)
        self.assertEqual(list_user_jobs(self.alice), [])
