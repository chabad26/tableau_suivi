import unittest
from unittest.mock import patch

from app import database
from app.connectors.imap import scan_imap
from app.settings import API_START_DATE


class ImapConnectorTests(unittest.TestCase):

    def setUp(self):
        database.init_database()

    def test_scan_without_accounts_returns_empty_list(self):
        with patch(
            "app.connectors.imap.get_enabled_imap_accounts",
            return_value=[],
        ):
            emails = scan_imap(
                API_START_DATE
            )

        self.assertEqual(
            emails,
            [],
        )


if __name__ == "__main__":
    unittest.main()