"""Arrêt propre du worker personnel sans traiter les anciens travaux."""

from unittest.mock import patch

import worker
from tests.helpers import OfflineCase


class WorkerTests(OfflineCase):
    def test_keyboard_interrupt_stops_worker_once(self):
        with (
            patch.object(worker, "DATABASE_PATH", self.root / "test.db"),
            patch.object(
                worker, "run_next_user_job", side_effect=KeyboardInterrupt
            ) as run,
            patch(
                "app.jobs.run_next",
                side_effect=AssertionError("Worker historique interdit"),
            ) as legacy,
        ):
            worker.main()
        run.assert_called_once()
        legacy.assert_not_called()
