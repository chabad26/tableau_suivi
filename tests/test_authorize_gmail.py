"""Consentement simulé et conservation du cache sur erreur d'identité."""

from unittest.mock import MagicMock, patch

from app.owned_imap import create_user_imap_account
from authorize_gmail import authorize_gmail_account
from tests.helpers import OfflineCase


class AuthorizeGmailTests(OfflineCase):
    def setUp(self):
        super().setUp()
        self.owner = self.create_test_user("alice@example.invalid")
        self.other = self.create_test_user("bob@example.invalid")
        self.account = create_user_imap_account(
            self.owner,
            email="alice@gmail.com",
            provider="gmail",
            host="imap.gmail.com",
            port=993,
            use_ssl=True,
            username="alice@gmail.com",
            folder="INBOX",
            auth_method="oauth2",
        )
        self.credentials = MagicMock(valid=True, refresh_token="fixture-refresh")
        self.credentials.to_json.return_value = '{"fixture":"new-cache"}'
        self.flow = self.stack.enter_context(patch("authorize_gmail.InstalledAppFlow"))
        self.flow.from_client_secrets_file.return_value.run_local_server.return_value = self.credentials
        self.http = self.stack.enter_context(patch("authorize_gmail.AuthorizedSession"))
        self.response = self.http.return_value.__enter__.return_value.get.return_value
        self.write = self.stack.enter_context(
            patch("authorize_gmail.write_oauth_cache")
        )

    def test_matching_identity_writes_only_target_private_cache(self):
        self.response.json.return_value = {"emailAddress": "ALICE@gmail.com"}
        authorize_gmail_account(self.owner, self.account)
        self.response.raise_for_status.assert_called_once()
        self.write.assert_called_once_with(
            self.owner, self.account, "gmail", '{"fixture":"new-cache"}'
        )

    def test_wrong_identity_never_overwrites_existing_cache(self):
        self.response.json.return_value = {"emailAddress": "bob@gmail.com"}
        with self.assertRaisesRegex(ValueError, "ne correspond pas"):
            authorize_gmail_account(self.owner, self.account)
        self.write.assert_not_called()

    def test_other_owner_cannot_start_consent(self):
        with self.assertRaises(ValueError):
            authorize_gmail_account(self.other, self.account)
        self.flow.from_client_secrets_file.assert_not_called()
        self.write.assert_not_called()

    def test_missing_refresh_token_never_overwrites_existing_cache(self):
        self.credentials.refresh_token = None
        with self.assertRaises(ValueError):
            authorize_gmail_account(self.owner, self.account)
        self.write.assert_not_called()
