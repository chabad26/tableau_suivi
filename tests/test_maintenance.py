"""La maintenance doit toujours être limitée à un propriétaire explicite."""

from unittest.mock import patch

from app.maintenance import expire_stale_applications
from tests.helpers import OfflineCase


class MaintenanceTests(OfflineCase):
    def test_invalid_owner_is_rejected_before_accessing_sqlite(self):
        with patch("app.maintenance.get_connection") as connect:
            for user_id in (None, True, 0, -1, "1"):
                with self.subTest(user_id=user_id), self.assertRaises(ValueError):
                    expire_stale_applications(user_id)
            connect.assert_not_called()
