"""Gestion personnelle des connecteurs, sans réseau ni véritable keyring."""

import contextlib
import io
import re
from unittest.mock import MagicMock, patch

from app.database import get_connection
from app.owned_imap import (
    create_user_imap_account,
    get_user_imap_account,
    imap_account_revision,
)
from app.owned_importer import import_user_emails
from app.owned_jobs import (
    enqueue_user_job,
    get_user_job,
    list_user_jobs,
    run_next_user_job,
)
from tests.helpers import OfflineCase, fake_email


class ConnectorWebTests(OfflineCase):
    def setUp(self):
        super().setUp()
        self.alice = self.login_test_user("alice@example.invalid")
        self.bob = self.create_test_user("bob@example.invalid")
        self.store = self.stack.enter_context(patch("app.secrets.set_imap_password"))
        self.read_secret = self.stack.enter_context(
            patch("app.owned_scanner.get_imap_password", return_value="fixture-only")
        )
        self.account = create_user_imap_account(self.alice, **self.values())
        self.bob_account = create_user_imap_account(
            self.bob,
            **self.values(email="bob@mail.invalid", username="bob@mail.invalid"),
        )
        self.store.reset_mock()

    def values(self, **changes):
        values = dict(
            email="alice@mail.invalid",
            provider="ovh",
            host="imap.example.invalid",
            port=993,
            use_ssl=True,
            username="alice@mail.invalid",
            folder="INBOX",
            auth_method="password",
            password="fixture-only",
        )
        values.update(changes)
        return values

    def form(self, **changes):
        values = self.values(**changes)
        values["use_ssl"] = "on" if values["use_ssl"] else ""
        return values

    def revision(self, account_id=None):
        row = get_user_imap_account(self.alice, account_id or self.account)
        assert row is not None
        return imap_account_revision(row)

    def test_only_own_accounts_are_listed_without_secret_access(self):
        with patch("app.web.connectors.oauth_token_path") as oauth_path:
            page = self.client.get("/connectors")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"alice@mail.invalid", page.data)
        self.assertNotIn(b"bob@mail.invalid", page.data)
        self.assertNotIn(b"fixture-only", page.data)
        self.read_secret.assert_not_called()
        oauth_path.assert_not_called()

    def test_creation_uses_session_owner_and_keeps_password_out_of_sqlite(self):
        response = self.client.post(
            "/connectors/imap/add",
            data={
                **self.form(email="new@mail.invalid", username="new@mail.invalid"),
                "user_id": self.bob,
            },
        )
        self.assertEqual(response.status_code, 303)
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM imap_accounts WHERE email='new@mail.invalid'"
            ).fetchone()
        self.assertEqual(row["user_id"], self.alice)
        self.assertNotIn("fixture-only", repr(tuple(row)))
        self.store.assert_called_once_with(row["id"], "fixture-only")

    def test_oauth_creation_never_uses_keyring_and_does_not_claim_authorization(self):
        response = self.client.post(
            "/connectors/imap/add",
            data=self.form(
                email="alice@gmail.com",
                username="alice@gmail.com",
                provider="gmail",
                auth_method="oauth2",
                password="",
                host="imap.gmail.com",
            ),
        )
        self.assertEqual(response.status_code, 303)
        self.store.assert_not_called()
        page = self.client.get("/connectors")
        self.assertIn("Autorisation OAuth nécessaire", page.text)
        self.assertNotIn("● Connecté", page.text)

    def test_unknown_domain_can_be_configured_without_dns(self):
        with patch("app.web.connectors.detect_provider_smart") as detect:
            response = self.client.post(
                "/connectors/imap/detect", data={"email": "new@campus.invalid"}
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("saisir les paramètres manuellement", response.text)
        self.assertIn('name="host"', response.text)
        detect.assert_not_called()

    def test_known_provider_detection_prefills_fields(self):
        response = self.client.post(
            "/connectors/imap/detect", data={"email": "new@sfr.fr"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("imap.sfr.fr", response.text)
        self.assertIn('value="new@sfr.fr"', response.text)

    def test_other_users_resources_are_not_accessible_or_mutable(self):
        for method, suffix in [
            ("get", "edit"),
            ("post", "edit"),
            ("post", "toggle"),
            ("post", "test"),
        ]:
            with self.subTest(method=method, action=suffix):
                self.assertEqual(
                    getattr(self.client, method)(
                        f"/connectors/imap/{self.bob_account}/{suffix}",
                        data=self.form(),
                    ).status_code,
                    404,
                )
        self.store.assert_not_called()
        self.assertEqual(list_user_jobs(self.alice), [])

    def test_edit_preserves_checkpoint_when_configuration_is_unchanged(self):
        with get_connection() as connection:
            connection.execute(
                "UPDATE imap_accounts SET last_uid=42, uid_validity=777 WHERE id=?",
                (self.account,),
            )
        response = self.client.post(
            f"/connectors/imap/{self.account}/edit",
            data={**self.form(password=""), "revision": self.revision()},
        )
        self.assertEqual(response.status_code, 303)
        row = get_user_imap_account(self.alice, self.account)
        self.assertEqual((row["last_uid"], row["uid_validity"]), (42, 777))
        self.store.assert_not_called()

    def test_edit_changed_folder_resets_checkpoint_without_deleting_email(self):
        import_user_emails(self.alice, [fake_email()])
        with get_connection() as connection:
            connection.execute(
                "UPDATE imap_accounts SET last_uid=42, uid_validity=777 WHERE id=?",
                (self.account,),
            )
        response = self.client.post(
            f"/connectors/imap/{self.account}/edit",
            data={
                **self.form(password="", folder="Applications"),
                "revision": self.revision(),
            },
        )
        self.assertEqual(response.status_code, 303)
        row = get_user_imap_account(self.alice, self.account)
        self.assertEqual(
            (row["folder"], row["last_uid"], row["uid_validity"]),
            ("Applications", 0, None),
        )

        with get_connection() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM emails WHERE user_id=?", (self.alice,)
                ).fetchone()[0],
                1,
            )

    def test_stale_form_is_rejected_before_secret_storage(self):
        old = self.revision()
        self.client.post(
            f"/connectors/imap/{self.account}/toggle", data={"revision": old}
        )
        response = self.client.post(
            f"/connectors/imap/{self.account}/edit",
            data={**self.form(), "revision": old},
        )
        self.assertEqual(response.status_code, 409)
        self.store.assert_not_called()

    def test_toggle_retains_account_and_checkpoint(self):
        with get_connection() as connection:
            connection.execute(
                "UPDATE imap_accounts SET last_uid=42, uid_validity=777 WHERE id=?",
                (self.account,),
            )
        response = self.client.post(
            f"/connectors/imap/{self.account}/toggle",
            data={"revision": self.revision()},
        )
        self.assertEqual(response.status_code, 303)
        self.assertFalse(get_user_imap_account(self.alice, self.account)["enabled"])
        self.assertEqual(
            self.client.post(f"/connectors/imap/{self.account}/test").status_code, 409
        )
        self.client.post(
            f"/connectors/imap/{self.account}/toggle",
            data={"revision": self.revision()},
        )
        self.assertTrue(get_user_imap_account(self.alice, self.account)["enabled"])

        row = get_user_imap_account(self.alice, self.account)
        self.assertEqual((row["last_uid"], row["uid_validity"]), (42, 777))

    def test_invalid_configuration_and_provider_auth_mismatch_are_rejected(self):
        for change in [
            dict(port=0),
            dict(port=65536),
            dict(port="bad"),
            dict(host="https://evil.invalid"),
            dict(auth_method="oauth2"),
            dict(provider="gmail"),
            dict(password=""),
        ]:
            with self.subTest(change=change):
                self.assertEqual(
                    self.client.post(
                        "/connectors/imap/add",
                        data=self.form(email="bad@mail.invalid", **change),
                    ).status_code,
                    400,
                )
        self.store.assert_not_called()

    def test_keyring_failure_rolls_back_and_does_not_leak_exception(self):
        self.store.side_effect = RuntimeError("FIXTURE-SECRET")
        response = self.client.post(
            "/connectors/imap/add", data=self.form(email="new@mail.invalid")
        )
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("FIXTURE-SECRET", response.text)
        with get_connection() as connection:
            self.assertIsNone(
                connection.execute(
                    "SELECT id FROM imap_accounts WHERE email='new@mail.invalid'"
                ).fetchone()
            )

    def test_keyring_failure_during_edit_keeps_previous_configuration(self):
        self.store.side_effect = RuntimeError("FIXTURE-SECRET")
        response = self.client.post(
            f"/connectors/imap/{self.account}/edit",
            data={**self.form(folder="Changed"), "revision": self.revision()},
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            get_user_imap_account(self.alice, self.account)["folder"], "INBOX"
        )
        self.assertNotIn("FIXTURE-SECRET", response.text)

    def test_duplicate_address_does_not_disclose_other_owner(self):
        response = self.client.post(
            "/connectors/imap/add", data=self.form(email="bob@mail.invalid")
        )
        self.assertEqual(response.status_code, 409)
        self.assertNotIn("bob", response.text)
        self.store.assert_not_called()

    def test_running_job_blocks_configuration_change(self):
        job = enqueue_user_job(self.alice, f"test:imap:{self.account}")
        with get_connection() as connection:
            connection.execute("UPDATE jobs SET state='running' WHERE id=?", (job,))
        response = self.client.post(
            f"/connectors/imap/{self.account}/edit",
            data={**self.form(password=""), "revision": self.revision()},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            self.client.post(
                f"/connectors/imap/{self.account}/toggle",
                data={"revision": self.revision()},
            ).status_code,
            409,
        )

    def test_test_job_is_owned_and_deduplicated(self):
        for _ in range(2):
            response = self.client.post(
                f"/connectors/imap/{self.account}/test", data={"user_id": self.bob}
            )
            self.assertEqual(response.status_code, 303)
        self.assertEqual(len(list_user_jobs(self.alice)), 1)
        self.assertEqual(list_user_jobs(self.bob), [])
        self.assertEqual(
            list_user_jobs(self.alice)[0]["kind"], f"test:imap:{self.account}"
        )

    def test_connection_test_never_fetches_emails_or_advances_checkpoint(self):
        with get_connection() as connection:
            connection.execute(
                "UPDATE imap_accounts SET last_uid=42, uid_validity=777 WHERE id=?",
                (self.account,),
            )
        self.client.post(f"/connectors/imap/{self.account}/test")
        connection = MagicMock()
        connection.select.return_value = ("OK", [b"1"])
        with (
            patch("app.connectors.imap.connect_imap", return_value=connection),
            patch("app.owned_scanner.authenticate_owned_imap") as auth,
        ):
            self.assertTrue(run_next_user_job())
        auth.assert_called_once()
        connection.select.assert_called_once_with("INBOX", readonly=True)
        connection.uid.assert_not_called()
        connection.logout.assert_called_once()
        row = get_user_imap_account(self.alice, self.account)
        self.assertEqual(
            (row["last_uid"], row["uid_validity"], row["last_status"]),
            (42, 777, "connected"),
        )
        self.assertEqual(list_user_jobs(self.alice)[0]["state"], "succeeded")

    def test_failed_connection_test_hides_secret_and_records_failure(self):
        self.client.post(f"/connectors/imap/{self.account}/test")
        output = io.StringIO()
        with (
            contextlib.redirect_stdout(output),
            patch(
                "app.connectors.imap.connect_imap",
                side_effect=RuntimeError("FIXTURE-SECRET"),
            ),
        ):
            self.assertTrue(run_next_user_job())
        job = list_user_jobs(self.alice)[0]
        self.assertEqual(job["state"], "failed")
        self.assertNotIn("FIXTURE-SECRET", str(job["error"]))
        self.assertEqual(
            get_user_imap_account(self.alice, self.account)["last_status"], "error"
        )
        self.assertNotIn("FIXTURE-SECRET", output.getvalue())

    def test_worker_rechecks_owner_before_authentication(self):
        self.client.post(f"/connectors/imap/{self.account}/test")
        with get_connection() as connection:
            connection.execute(
                "UPDATE imap_accounts SET user_id=? WHERE id=?",
                (self.bob, self.account),
            )
        with patch("app.connectors.imap.connect_imap") as connect:
            self.assertFalse(run_next_user_job())
        connect.assert_not_called()

    def test_jobs_page_never_shows_other_users_jobs(self):
        own = enqueue_user_job(self.alice, f"test:imap:{self.account}")
        other = enqueue_user_job(self.bob, f"test:imap:{self.bob_account}")
        with get_connection() as connection:
            connection.execute(
                "UPDATE jobs SET error='BOB-PRIVATE' WHERE id=?", (other,)
            )
        self.assertEqual(self.client.get("/jobs").status_code, 200)
        self.assertNotIn("BOB-PRIVATE", self.client.get("/jobs").text)
        self.assertIsNotNone(get_user_job(self.alice, own))
        self.assertIsNone(get_user_job(self.alice, other))

    def test_all_mutations_require_csrf_and_valid_token_allows_creation(self):
        self.app.config["WTF_CSRF_ENABLED"] = True
        for path in [
            "/connectors/imap/add",
            "/connectors/imap/detect",
            f"/connectors/imap/{self.account}/edit",
            f"/connectors/imap/{self.account}/toggle",
            f"/connectors/imap/{self.account}/test",
        ]:
            with self.subTest(path=path):
                self.assertEqual(
                    self.client.post(path, data=self.form()).status_code, 400
                )
        page = self.client.get("/connectors/imap/add")
        token = re.search(r'name="csrf_token"\s+value="([^"]+)"', page.text).group(1)
        response = self.client.post(
            "/connectors/imap/add",
            data={**self.form(email="csrf@mail.invalid"), "csrf_token": token},
        )
        self.assertEqual(response.status_code, 303)

    def test_anonymous_visitors_cannot_access_connectors_or_jobs(self):
        client = self.app.test_client()
        for path in [
            "/connectors",
            "/connectors/imap/add",
            f"/connectors/imap/{self.account}/edit",
            "/jobs",
        ]:
            self.assertEqual(client.get(path).status_code, 302)
