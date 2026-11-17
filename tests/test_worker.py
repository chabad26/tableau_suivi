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
        ):
            worker.main()
        run.assert_called_once()
