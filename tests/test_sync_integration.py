"""Pipeline réel scan/détection/import/checkpoint, transport IMAP fictif."""

import sqlite3
from unittest.mock import patch

from app.database import get_connection
from app.offline_imap import FakeImap
from app.owned_applications import get_user_application_emails, get_user_applications
from app.owned_imap import get_user_imap_accounts
from app.owned_jobs import execute_user_job
from tests.helpers import OfflineCase


class SyncIntegrationTests(OfflineCase):
    def setUp(self):
        super().setUp()
        self.alice = self.create_test_user("alice@example.invalid")
        self.bob = self.create_test_user("bob@example.invalid")
        self.alice_account = self.account(self.alice, "alice@mail.invalid")
        self.bob_account = self.account(self.bob, "bob@mail.invalid")
        self.servers = {
            self.alice_account: FakeImap("alice@mail.invalid"),
            self.bob_account: FakeImap("bob@mail.invalid"),
        }
        self.stack.enter_context(
            patch("app.owned_scanner.get_imap_password", return_value="fixture-only")
        )
        self.connect = self.stack.enter_context(
            patch(
                "app.connectors.imap.connect_imap",
                side_effect=lambda account: self.servers[account.account_id],
            )
        )
        self.global_auth = self.stack.enter_context(
            patch(
                "app.connectors.imap.authenticate_imap",
                side_effect=AssertionError("Authentification globale interdite"),
            )
        )

    def account(self, user_id, email):
        with get_connection() as connection:
            cursor = connection.execute(
                "INSERT INTO imap_accounts (email, host, username, provider, user_id) VALUES (?, ?, ?, 'ovh', ?)",
                (email, "imap.demo.invalid", email, user_id),
            )
            assert cursor.lastrowid is not None
            return cursor.lastrowid

    def checkpoint(self, account_id):
        with get_connection() as connection:
            row = connection.execute(
                "SELECT last_uid, uid_validity FROM imap_accounts WHERE id = ?",
                (account_id,),
            ).fetchone()
        return tuple(row)

    def test_complete_pipeline_and_isolation(self):
        result = execute_user_job(self.alice, "scan")
        self.assertEqual(result["added"], 3)
        self.assertEqual(self.checkpoint(self.alice_account), (3, 777))
        self.assertEqual(self.checkpoint(self.bob_account), (0, None))
        applications = get_user_applications(self.alice)
        self.assertTrue(applications)
        self.assertEqual(
            sum(
                len(get_user_application_emails(self.alice, row["id"]))
                for row in applications
            ),
            3,
        )
        self.assertEqual(get_user_applications(self.bob), [])
        self.assertEqual(
            [row["id"] for row in get_user_imap_accounts(self.alice)],
            [self.alice_account],
        )
        self.assertEqual(self.servers[self.bob_account].fetched, [])
        for row in applications:
            self.assertEqual(get_user_application_emails(self.bob, row["id"]), [])
        execute_user_job(self.bob, "scan")
        self.assertTrue(get_user_applications(self.bob))
        self.global_auth.assert_not_called()

    def test_sqlite_failure_rolls_back_and_does_not_advance_checkpoint(self):
        with get_connection() as connection:
            connection.execute(
                "CREATE TRIGGER fail_email BEFORE INSERT ON emails WHEN NEW.message_id LIKE '%-2@demo.invalid>' BEGIN SELECT RAISE(ABORT, 'fixture failure'); END"
            )
        with self.assertRaises(sqlite3.IntegrityError):
            execute_user_job(self.alice, "scan")
        self.assertEqual(get_user_applications(self.alice), [])
        self.assertEqual(self.checkpoint(self.alice_account), (0, None))
        with get_connection() as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM emails").fetchone()[0], 0
            )

    def test_uid_failure_is_reported_then_retried_without_duplicates(self):
        server = self.servers[self.alice_account]
        server.failed_uids = {2}
        with self.assertRaisesRegex(RuntimeError, "Synchronisation partielle"):
            execute_user_job(self.alice, "scan")
        self.assertEqual(self.checkpoint(self.alice_account), (1, 777))
        server.failed_uids.clear()
        server.fetched.clear()
        result = execute_user_job(self.alice, "scan")
        self.assertEqual(server.fetched, [2, 3])
        self.assertEqual(result["added"], 1)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(self.checkpoint(self.alice_account), (3, 777))
        with get_connection() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM emails WHERE user_id = ?", (self.alice,)
                ).fetchone()[0],
                3,
            )

    def test_repeated_full_import_does_not_duplicate(self):
        execute_user_job(self.alice, "scan")
        with get_connection() as connection:
            connection.execute(
                "UPDATE imap_accounts SET last_uid = 0 WHERE id = ?",
                (self.alice_account,),
            )
        result = execute_user_job(self.alice, "scan")
        self.assertEqual(result["added"], 0)
        self.assertEqual(result["skipped"], 3)

    def test_disabled_or_reassigned_or_changed_account_refuses_checkpoint(self):
        from app.owned_importer import import_user_emails

        for assignment, value in [
            ("enabled", 0),
            ("user_id", self.bob),
            ("port", 1993),
            ("use_ssl", 0),
            ("last_uid", 99),
        ]:
            with self.subTest(field=assignment):
                with get_connection() as connection:
                    connection.execute(
                        "UPDATE imap_accounts SET enabled=1, user_id=?, port=993, use_ssl=1, last_uid=0, uid_validity=NULL WHERE id=?",
                        (self.alice, self.alice_account),
                    )

                def changed_import(*args, **kwargs):
                    result = import_user_emails(*args, **kwargs)
                    with get_connection() as connection:
                        connection.execute(
                            f"UPDATE imap_accounts SET {assignment} = ? WHERE id = ?",
                            (value, self.alice_account),
                        )
                    return result

                with patch(
                    "app.owned_importer.import_user_emails", side_effect=changed_import
                ):
                    with self.assertRaisesRegex(
                        RuntimeError, "Synchronisation partielle"
                    ):
                        execute_user_job(self.alice, "scan")
                expected = 99 if assignment == "last_uid" else 0
                self.assertEqual(self.checkpoint(self.alice_account), (expected, None))

    def test_partial_mailbox_failure_preserves_other_imports(self):
        extra = self.account(self.alice, "second@mail.invalid")
        self.servers[extra] = FakeImap("second@mail.invalid", unavailable=True)
        with self.assertRaisesRegex(RuntimeError, "Synchronisation partielle"):
            execute_user_job(self.alice, "scan")
        self.assertEqual(self.checkpoint(self.alice_account), (3, 777))
        self.assertEqual(self.checkpoint(extra), (0, None))
        with get_connection() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM emails WHERE user_id = ?", (self.alice,)
                ).fetchone()[0],
                3,
            )

    def test_missing_uidvalidity_imports_but_never_saves_checkpoint(self):
        self.servers[self.alice_account].uid_validity = None
        with self.assertRaisesRegex(RuntimeError, "Synchronisation partielle"):
            execute_user_job(self.alice, "scan")
        self.assertEqual(self.checkpoint(self.alice_account), (0, None))
        self.assertTrue(get_user_applications(self.alice))

    def test_uidvalidity_change_rescans_without_duplicates(self):
        execute_user_job(self.alice, "scan")
        server = self.servers[self.alice_account]
        server.uid_validity = 999
        server.fetched.clear()
        result = execute_user_job(self.alice, "scan")
        self.assertEqual(server.fetched, [1, 2, 3])
        self.assertEqual(result["added"], 0)
        self.assertEqual(self.checkpoint(self.alice_account), (3, 999))

    def test_uid_exception_does_not_leak_secret_to_logs(self):
        import contextlib
        import io

        output = io.StringIO()
        with (
            contextlib.redirect_stdout(output),
            patch(
                "app.connectors.imap.get_message_body",
                side_effect=RuntimeError("FIXTURE-SECRET"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "Synchronisation partielle"):
                execute_user_job(self.alice, "scan")
        self.assertNotIn("FIXTURE-SECRET", output.getvalue())
        self.assertEqual(self.checkpoint(self.alice_account), (0, 777))
