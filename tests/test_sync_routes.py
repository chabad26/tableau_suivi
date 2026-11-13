"""Routes de synchronisation : session, propriétaire et absence de chemin global."""

import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from app.owned_jobs import (
    enqueue_user_job,
    get_user_job,
    list_user_jobs,
    run_next_user_job,
)
from tests.helpers import OfflineCase


class SyncRouteTests(OfflineCase):
    def setUp(self):
        super().setUp()
        self.alice = self.login_test_user("alice@example.invalid")
        self.bob = self.create_test_user("bob@example.invalid")

    def test_scan_ignores_supplied_owner_and_deduplicates(self):
        with patch(
            "app.jobs.enqueue", side_effect=AssertionError("Chemin global interdit")
        ):
            for _ in range(2):
                response = self.client.post("/scan", data={"user_id": self.bob})
                self.assertEqual(response.status_code, 303)
        self.assertEqual(len(list_user_jobs(self.alice)), 1)
        self.assertEqual(list_user_jobs(self.bob), [])

    def test_jobs_never_show_other_users_or_historical_jobs(self):
        from app.database import get_connection

        alice_job = enqueue_user_job(self.alice, "scan")
        bob_job = enqueue_user_job(self.bob, "scan")
        with get_connection() as connection:
            connection.execute(
                "UPDATE jobs SET error = 'BOB-PRIVATE' WHERE id = ?", (bob_job,)
            )
            connection.execute(
                "INSERT INTO jobs (id, kind, state, error) VALUES ('legacy', 'scan', 'failed', 'LEGACY-PRIVATE')"
            )
        response = self.client.get("/jobs")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"BOB-PRIVATE", response.data)
        self.assertNotIn(b"LEGACY-PRIVATE", response.data)
        self.assertIsNone(get_user_job(self.alice, bob_job))
        self.assertIsNotNone(get_user_job(self.alice, alice_job))

    def test_anonymous_requests_cannot_enqueue_or_list(self):
        client = self.app.test_client()
        self.assertEqual(client.post("/scan").status_code, 302)
        self.assertEqual(client.get("/jobs").status_code, 302)
        self.assertEqual(list_user_jobs(self.alice), [])

    def test_unmigrated_routes_cannot_enqueue(self):
        for route in ["/connectors/gmail/test"]:
            self.assertEqual(self.client.post(route).status_code, 503)
        self.assertEqual(list_user_jobs(self.alice), [])

    def test_http_stays_available_while_personal_worker_runs(self):
        entered = threading.Event()
        release = threading.Event()

        def slow_task(user_id, kind):
            entered.set()
            if not release.wait(5):
                raise TimeoutError("Fixture bloquée")
            return {"detected": 0}

        self.client.post("/scan")
        with (
            patch("app.owned_jobs.execute_user_job", side_effect=slow_task),
            ThreadPoolExecutor(1) as pool,
        ):
            future = pool.submit(run_next_user_job)
            try:
                self.assertTrue(entered.wait(2))
                self.assertEqual(self.client.get("/").status_code, 200)
                self.assertEqual(self.client.get("/jobs").status_code, 200)
                self.assertFalse(future.done())
                self.assertFalse(run_next_user_job())
            finally:
                release.set()
            self.assertTrue(future.result(timeout=2))
