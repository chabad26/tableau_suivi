from unittest.mock import patch

from app import database, jobs
from tests.helpers import OfflineCase


class LegacyJobsTests(OfflineCase):
    def test_queue_failure_and_serialization(self):
        jobs.init_jobs()
        first = jobs.enqueue("scan")
        self.assertEqual(jobs.enqueue("scan"), first)
        jobs.enqueue("reclassify")
        with database.get_connection() as connection:
            connection.execute(
                "UPDATE jobs SET state = 'running' WHERE id = ?", (first,)
            )
        with patch.object(jobs, "execute") as execute:
            self.assertFalse(jobs.run_next())
            execute.assert_not_called()
        with database.get_connection() as connection:
            connection.execute(
                "UPDATE jobs SET state = 'queued' WHERE id = ?", (first,)
            )
        with patch.object(jobs, "execute", side_effect=RuntimeError("secret-fixture")):
            self.assertTrue(jobs.run_next())
        with patch.object(jobs, "execute", return_value={"found": 1}):
            self.assertTrue(jobs.run_next())
        rows = jobs.list_jobs()
        self.assertEqual({row["state"] for row in rows}, {"failed", "succeeded"})
        self.assertNotIn(
            "secret-fixture", self.client.get("/jobs").get_data(as_text=True)
        )
        jobs.init_jobs()
        self.assertEqual(len(jobs.list_jobs()), 2)

    def test_worker_restart_keeps_pending_and_marks_interrupted(self):
        jobs.init_jobs()
        interrupted = jobs.enqueue("scan")
        jobs.enqueue("reclassify")
        with database.get_connection() as connection:
            connection.execute(
                "UPDATE jobs SET state = 'running' WHERE id = ?", (interrupted,)
            )
        jobs.recover_interrupted()
        self.assertEqual(
            {row["state"] for row in jobs.list_jobs()}, {"failed", "queued"}
        )
        with patch.object(jobs, "execute", return_value={"found": 0}):
            self.assertTrue(jobs.run_next())
        self.assertEqual(
            {row["state"] for row in jobs.list_jobs()}, {"failed", "succeeded"}
        )
