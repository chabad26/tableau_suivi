"""Tests hors réseau des connecteurs OAuth privés."""

from unittest import TestCase
from unittest.mock import MagicMock, patch

from app.connectors.gmail import get_owned_gmail_token
from app.connectors.microsoft import get_owned_microsoft_token


class GmailRefreshTests(TestCase):
    @patch("app.connectors.gmail.locked_oauth_account")
    @patch("app.connectors.gmail._get_owned_gmail_token_unlocked")
    def test_gmail_uses_locked_private_flow(self, get_token, lock):
        get_token.return_value = "gmail-token-test"

        result = get_owned_gmail_token(1, 3, "alice@gmail.com")

        self.assertEqual(result, "gmail-token-test")

        lock.assert_called_once_with(1, 3, "gmail")

        get_token.assert_called_once_with(1, 3, "alice@gmail.com")

    @patch("app.connectors.gmail.write_oauth_cache")
    @patch("app.connectors.gmail.AuthorizedSession")
    @patch("app.connectors.gmail.Credentials")
    @patch("app.connectors.gmail.read_oauth_cache")
    def test_gmail_refresh_and_identity_check(
        self, read, credentials_class, session_class, write
    ):
        from app.connectors.gmail import _get_owned_gmail_token_unlocked

        read.return_value = '{"fixture": true}'

        credentials = MagicMock()
        credentials.expired = True
        credentials.refresh_token = "refresh-token-test"
        credentials.valid = True
        credentials.token = "access-token-test"
        credentials.to_json.return_value = '{"updated": true}'

        credentials_class.from_authorized_user_info.return_value = credentials

        response = MagicMock()
        response.json.return_value = {"emailAddress": "alice@gmail.com"}

        session_class.return_value.__enter__.return_value.get.return_value = response

        result = _get_owned_gmail_token_unlocked(1, 3, "alice@gmail.com")

        self.assertEqual(result, "access-token-test")

        credentials.refresh.assert_called_once()
        response.raise_for_status.assert_called_once()

        write.assert_called_once_with(1, 3, "gmail", '{"updated": true}')

    @patch("app.connectors.gmail.write_oauth_cache")
    @patch("app.connectors.gmail.AuthorizedSession")
    @patch("app.connectors.gmail.Credentials")
    @patch("app.connectors.gmail.read_oauth_cache")
    def test_gmail_rejects_wrong_identity(
        self, read, credentials_class, session_class, write
    ):
        from app.connectors.gmail import _get_owned_gmail_token_unlocked

        read.return_value = '{"fixture": true}'

        credentials = MagicMock()
        credentials.expired = False
        credentials.valid = True
        credentials.token = "test-token"

        credentials_class.from_authorized_user_info.return_value = credentials

        response = MagicMock()
        response.json.return_value = {"emailAddress": "bob@gmail.com"}

        session_class.return_value.__enter__.return_value.get.return_value = response

        with self.assertRaises(RuntimeError):
            _get_owned_gmail_token_unlocked(1, 3, "alice@gmail.com")

        write.assert_not_called()


class MicrosoftRefreshTests(TestCase):
    @patch("app.connectors.microsoft.locked_oauth_account")
    @patch("app.connectors.microsoft._get_owned_microsoft_token_unlocked")
    def test_microsoft_uses_locked_private_flow(self, get_token, lock):
        get_token.return_value = "ms-token-test"

        result = get_owned_microsoft_token(1, 4, "alice@example.com")

        self.assertEqual(result, "ms-token-test")

        lock.assert_called_once_with(1, 4, "microsoft")

        get_token.assert_called_once_with(1, 4, "alice@example.com")

    @patch("app.connectors.microsoft.MICROSOFT_CLIENT_ID", "test-client-id")
    @patch("app.connectors.microsoft.write_oauth_cache")
    @patch("app.connectors.microsoft.msal.PublicClientApplication")
    @patch("app.connectors.microsoft.msal.SerializableTokenCache")
    @patch("app.connectors.microsoft.read_oauth_cache")
    def test_microsoft_selects_correct_account(
        self, read, cache_class, app_class, write
    ):
        from app.connectors.microsoft import _get_owned_microsoft_token_unlocked

        read.return_value = '{"fixture": true}'

        cache = cache_class.return_value
        cache.has_state_changed = True
        cache.serialize.return_value = '{"updated": true}'

        application = app_class.return_value

        correct_account = {"username": "alice@example.com"}

        application.get_accounts.return_value = [
            {"username": "bob@example.com"},
            correct_account,
        ]

        application.acquire_token_silent.return_value = {
            "access_token": "ms-access-token-test"
        }

        result = _get_owned_microsoft_token_unlocked(1, 4, "alice@example.com")

        self.assertEqual(result, "ms-access-token-test")

        self.assertEqual(
            application.acquire_token_silent.call_args.kwargs["account"],
            correct_account,
        )

        write.assert_called_once_with(1, 4, "microsoft", '{"updated": true}')

    @patch("app.connectors.microsoft.MICROSOFT_CLIENT_ID", "test-client-id")
    @patch("app.connectors.microsoft.write_oauth_cache")
    @patch("app.connectors.microsoft.msal.PublicClientApplication")
    @patch("app.connectors.microsoft.msal.SerializableTokenCache")
    @patch("app.connectors.microsoft.read_oauth_cache")
    def test_microsoft_rejects_ambiguous_identity(
        self, read, cache_class, app_class, write
    ):
        from app.connectors.microsoft import _get_owned_microsoft_token_unlocked

        read.return_value = '{"fixture": true}'

        application = app_class.return_value

        application.get_accounts.return_value = [
            {"username": "alice@example.com"},
            {"username": "ALICE@example.com"},
        ]

        with self.assertRaises(RuntimeError):
            _get_owned_microsoft_token_unlocked(1, 4, "alice@example.com")

        application.acquire_token_silent.assert_not_called()
        write.assert_not_called()
