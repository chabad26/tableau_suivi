from unittest.mock import patch

from app.web import create_app
from tests.helpers import OfflineCase


class AppFactoryTests(OfflineCase):
    def test_database_is_not_initialized_on_every_request(self):
        app = self.app
        app.config.update(TESTING=True)

        with (
            patch("app.web.init_database") as init_db,
            patch("app.web.init_jobs") as init_jobs_mock,
        ):
            client = app.test_client()

            client.get("/application/999999")

            init_db.assert_not_called()
            init_jobs_mock.assert_not_called()
