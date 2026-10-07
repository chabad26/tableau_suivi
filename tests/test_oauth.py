from unittest.mock import MagicMock, patch
from app.connectors import gmail, microsoft
import json
import unittest
from tests.helpers import OfflineCase

class ConnectorTests(OfflineCase):

    def test_token_cache_round_trip_uses_temporary_file(self):
        microsoft.TOKEN_CACHE_FILE.write_text(
            json.dumps({"Account": {"fixture": {"username": "test@example.invalid"}}})
        )
        cache = microsoft.load_cache()
        self.assertIn("fixture", json.loads(cache.serialize())["Account"])
        cache.has_state_changed = True
        microsoft.save_cache(cache)
        self.assertIn(
            "fixture", json.loads(microsoft.TOKEN_CACHE_FILE.read_text())["Account"]
        )

    def test_gmail_refresh_error_restarts_oauth_flow(self):
        expired_credentials = MagicMock()

        expired_credentials.expired = True
        expired_credentials.refresh_token = (
            "fixture-refresh-token"
        )
        expired_credentials.valid = False

        new_credentials = MagicMock()
        new_credentials.valid = True
        new_credentials.to_json.return_value = (
            '{"token": "fixture-new-token"}'
        )

        flow = MagicMock()
        flow.run_local_server.return_value = (
            new_credentials
        )

        gmail.TOKEN_FILE.write_text(
            '{"fixture": true}',
            encoding="utf-8",
        )

        from google.auth.exceptions import (
            RefreshError,
        )

        expired_credentials.refresh.side_effect = (
            RefreshError(
                "fixture refresh failure"
            )
        )

        with (
            patch.object(
                gmail.Credentials,
                "from_authorized_user_file",
                return_value=expired_credentials,
            ),
            patch.object(
                gmail.InstalledAppFlow,
                "from_client_secrets_file",
                return_value=flow,
            ),
        ):
            credentials = gmail.get_credentials()

        self.assertIs(
            credentials,
            new_credentials,
        )

        expired_credentials.refresh.assert_called_once()

        flow.run_local_server.assert_called_once_with(
            port=0
        )

        self.assertTrue(
            gmail.TOKEN_FILE.exists()
        )

        self.assertEqual(
            gmail.TOKEN_FILE.read_text(
                encoding="utf-8"
            ),
            '{"token": "fixture-new-token"}',
        )

    def test_gmail_invalid_token_file_restarts_oauth_flow(self):
        new_credentials = MagicMock()

        new_credentials.valid = True
        new_credentials.to_json.return_value = (
            '{"token": "fixture-new-token"}'
        )

        flow = MagicMock()
        flow.run_local_server.return_value = (
            new_credentials
        )

        gmail.TOKEN_FILE.write_text(
            "token cassé",
            encoding="utf-8",
        )

        with (
            patch.object(
                gmail.Credentials,
                "from_authorized_user_file",
                side_effect=ValueError(
                    "invalid token"
                ),
            ),
            patch.object(
                gmail.InstalledAppFlow,
                "from_client_secrets_file",
                return_value=flow,
            ),
        ):
            credentials = gmail.get_credentials()

        self.assertIs(
            credentials,
            new_credentials,
        )

        flow.run_local_server.assert_called_once_with(
            port=0
        )

if __name__ == "__main__":
    unittest.main()