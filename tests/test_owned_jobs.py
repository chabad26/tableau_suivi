"""Tests de la file de jobs multi-utilisateur."""

from unittest.mock import patch

from app.accounts import create_user, set_user_active
from app.database import get_connection
from app.owned_jobs import (
    enqueue_user_job,
    get_user_job,
    list_user_jobs,
    recover_interrupted_user_jobs,
    run_next_user_job,
)
from tests.helpers import OfflineCase


class OwnedJobsTests(OfflineCase):
    def setUp(self):
        super().setUp()

        self.alice = create_user("alice@example.invalid", "MotDePasseAlice2026!")

        self.bob = create_user("bob@example.invalid", "MotDePasseBob2026!")

    def test_jobs_are_isolated(self):
        alice_job = enqueue_user_job(self.alice, "scan")

        bob_job = enqueue_user_job(self.bob, "scan")

        self.assertNotEqual(alice_job, bob_job)

        self.assertEqual(len(list_user_jobs(self.alice)), 1)

        self.assertEqual(len(list_user_jobs(self.bob)), 1)

        self.assertIsNone(get_user_job(self.alice, bob_job))

    def test_duplicate_job_is_not_enqueued(self):
        first = enqueue_user_job(self.alice, "scan")

        second = enqueue_user_job(self.alice, "scan")

        self.assertEqual(first, second)

        self.assertEqual(len(list_user_jobs(self.alice)), 1)

    def test_disabled_user_cannot_enqueue(self):
        set_user_active(self.alice, False)

        with self.assertRaises(ValueError):
            enqueue_user_job(self.alice, "scan")

    def test_disabled_user_job_is_not_executed(self):
        job_id = enqueue_user_job(self.alice, "scan")

        set_user_active(self.alice, False)

        with patch("app.owned_jobs.execute_user_job") as execute:
            self.assertFalse(run_next_user_job())

            execute.assert_not_called()

        job = get_user_job(self.alice, job_id)

        assert job is not None

        self.assertEqual(job["state"], "queued")

    def test_job_runs_with_correct_user(self):
        job_id = enqueue_user_job(self.alice, "scan")

        with patch(
            "app.owned_jobs.execute_user_job",
            return_value={"detected": 2, "added": 2, "skipped": 0},
        ) as execute:
            self.assertTrue(run_next_user_job())

            execute.assert_called_once_with(self.alice, "scan")

        job = get_user_job(self.alice, job_id)

        assert job is not None

        self.assertEqual(job["state"], "succeeded")

    def test_failed_job_does_not_leak_exception(self):
        job_id = enqueue_user_job(self.alice, "scan")

        with patch(
            "app.owned_jobs.execute_user_job",
            side_effect=RuntimeError("mot-de-passe-secret-de-test"),
        ):
            self.assertTrue(run_next_user_job())

        job = get_user_job(self.alice, job_id)

        assert job is not None

        self.assertEqual(job["state"], "failed")

        self.assertNotIn("mot-de-passe-secret-de-test", str(job["error"]))

    def test_legacy_jobs_are_not_executed(self):
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    id,
                    kind,
                    state,
                    user_id
                )
                VALUES (?, ?, ?, NULL)
                """,
                ("legacy-job", "scan", "queued"),
            )

        with patch("app.owned_jobs.execute_user_job") as execute:
            self.assertFalse(run_next_user_job())

            execute.assert_not_called()

        with get_connection() as connection:
            legacy = connection.execute(
                """
                SELECT state
                FROM jobs
                WHERE id = 'legacy-job'
                """
            ).fetchone()

        assert legacy is not None

        self.assertEqual(legacy["state"], "queued")

    def test_recovery_only_affects_owned_jobs(self):
        job_id = enqueue_user_job(self.alice, "scan")

        with get_connection() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET state = 'running'
                WHERE id = ?
                """,
                (job_id,),
            )

            connection.execute(
                """
                INSERT INTO jobs (
                    id,
                    kind,
                    state,
                    user_id
                )
                VALUES ('legacy-running', 'scan', 'running', NULL)
                """
            )

        recover_interrupted_user_jobs()

        job = get_user_job(self.alice, job_id)

        assert job is not None

        self.assertEqual(job["state"], "failed")

        with get_connection() as connection:
            legacy = connection.execute(
                """
                SELECT state
                FROM jobs
                WHERE id = 'legacy-running'
                """
            ).fetchone()

        assert legacy is not None

        self.assertEqual(legacy["state"], "running")

    def test_unknown_kind_is_rejected(self):
        with self.assertRaises(ValueError):
            enqueue_user_job(self.alice, "reclassify")

        with self.assertRaises(ValueError):
            enqueue_user_job(self.alice, "test:imap:1")
