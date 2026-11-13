"""Backoffice : autorisation administrateur, secrets, création et désactivation."""

import re
from unittest.mock import patch

from app.accounts import authenticate, create_user, get_user, set_user_active
from app.admin_accounts import (
    create_managed_user,
    list_managed_users,
    set_managed_user_active,
)
from app.database import get_connection
from app.owned_applications import create_user_application
from tests.helpers import OfflineCase


class AdminAccountTests(OfflineCase):
    def setUp(self):
        super().setUp()
        self.password = "FixtureAccountPassword2026!"
        self.admin = create_user("admin@campus.invalid", self.password, "admin")
        self.student = create_user("student@campus.invalid", self.password, "student")
        self.trainer = create_user("trainer@campus.invalid", self.password, "trainer")
        self.sign_in("admin@campus.invalid")

    def sign_in(self, email, client=None):
        client = client or self.client
        self.assertEqual(
            client.post(
                "/login", data={"email": email, "password": self.password}
            ).status_code,
            303,
        )

    def creation_form(self, **changes):
        values = dict(
            email="new@campus.invalid",
            role="student",
            password="NewFixturePassword2026!",
            password_confirm="NewFixturePassword2026!",
        )
        values.update(changes)
        return values

    def users_count(self):
        with get_connection() as connection:
            return connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    def test_admin_list_shows_metadata_without_passwords_or_hashes(self):
        page = self.client.get("/admin/users")
        self.assertEqual(page.status_code, 200)
        self.assertIn("student@campus.invalid", page.text)
        self.assertIn("Formateur", page.text)
        self.assertNotIn(self.password, page.text)
        self.assertNotIn("scrypt:", page.text)
        self.assertNotIn("password_hash", page.text)
        for user in list_managed_users(self.admin):
            self.assertNotIn("password_hash", user.keys())

    def test_admin_navigation_link_and_creation_form(self):
        self.assertIn('href="/admin/users"', self.client.get("/account").text)
        page = self.client.get("/admin/users/new")
        self.assertEqual(page.status_code, 200)
        self.assertIn('name="csrf_token"', page.text)
        self.assertIn('value="student" selected', page.text)
        self.assertNotIn(self.password, page.text)

    def test_admin_creates_active_account_with_hashed_password(self):
        values = self.creation_form(email="  NEW@CAMPUS.INVALID ")
        response = self.client.post("/admin/users", data=values)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["Location"], "/admin/users")
        user = authenticate("new@campus.invalid", values["password"])
        self.assertIsNotNone(user)
        self.assertEqual(user.role, "student")
        self.assertTrue(user.active)
        with get_connection() as connection:
            row = connection.execute(
                "SELECT password_hash FROM users WHERE id=?", (user.id,)
            ).fetchone()
        self.assertNotEqual(row["password_hash"], values["password"])
        self.assertTrue(row["password_hash"].startswith("scrypt:"))
        self.assertNotIn(values["password"], response.text)
        self.assertNotIn(values["password"], self.client.get("/admin/users").text)

    def test_all_supported_roles_can_be_created_by_admin(self):
        for role in ("student", "admin"):
            with self.subTest(role=role):
                response = self.client.post(
                    "/admin/users",
                    data=self.creation_form(
                        email=f"new-{role}@campus.invalid", role=role
                    ),
                )
                self.assertEqual(response.status_code, 303)
                self.assertEqual(
                    authenticate(
                        f"new-{role}@campus.invalid", "NewFixturePassword2026!"
                    ).role,
                    role,
                )

    def test_non_admin_users_cannot_access_or_mutate_accounts(self):
        count = self.users_count()
        for email in ("student@campus.invalid", "trainer@campus.invalid"):
            client = self.app.test_client()
            self.sign_in(email, client)
            with self.subTest(role=email):
                self.assertEqual(client.get("/admin/users").status_code, 403)
                self.assertEqual(client.get("/admin/users/new").status_code, 403)
                self.assertEqual(
                    client.post(
                        "/admin/users", data=self.creation_form(role="admin")
                    ).status_code,
                    403,
                )
                self.assertEqual(
                    client.post(
                        f"/admin/users/{self.admin}/active", data={"active": "0"}
                    ).status_code,
                    403,
                )
                self.assertNotIn('href="/admin/users"', client.get("/account").text)
        self.assertEqual(self.users_count(), count)
        self.assertTrue(get_user(self.admin).active)

    def test_anonymous_users_cannot_access_or_create_accounts(self):
        client = self.app.test_client()
        self.assertEqual(client.get("/admin/users").status_code, 302)
        self.assertEqual(client.get("/admin/users/new").status_code, 302)
        self.assertEqual(
            client.post(
                "/admin/users", data=self.creation_form(role="admin")
            ).status_code,
            302,
        )
        self.assertEqual(
            client.post(
                f"/admin/users/{self.student}/active", data={"active": "0"}
            ).status_code,
            302,
        )
        self.assertEqual(self.users_count(), 3)

    def test_service_also_rejects_non_admin_actors(self):
        for actor in (self.student, self.trainer, 99999):
            with self.subTest(actor=actor):
                with self.assertRaises(PermissionError):
                    list_managed_users(actor)
                with self.assertRaises(PermissionError):
                    create_managed_user(
                        actor, "forbidden@campus.invalid", self.password, "admin"
                    )
                with self.assertRaises(PermissionError):
                    set_managed_user_active(actor, self.student, False)
        self.assertEqual(self.users_count(), 3)

    def test_disabled_admin_loses_access_and_cannot_create(self):
        set_user_active(self.admin, False)
        self.assertEqual(self.client.get("/admin/users").status_code, 302)
        with self.assertRaises(PermissionError):
            create_managed_user(self.admin, "forbidden@campus.invalid", self.password)
        self.assertEqual(self.users_count(), 3)

    def test_role_demotion_is_checked_on_next_request(self):
        with get_connection() as connection:
            connection.execute(
                "UPDATE users SET role='trainer' WHERE id=?", (self.admin,)
            )
        self.assertEqual(self.client.get("/admin/users").status_code, 403)
        self.assertEqual(
            self.client.post("/admin/users", data=self.creation_form()).status_code, 403
        )
        self.assertEqual(self.users_count(), 3)

    def test_permissions_are_rechecked_after_password_hashing(self):
        from werkzeug.security import generate_password_hash

        def revoke_then_hash(password, **kwargs):
            set_user_active(self.admin, False)
            return generate_password_hash(password, **kwargs)

        with patch(
            "app.admin_accounts.generate_password_hash", side_effect=revoke_then_hash
        ):
            with self.assertRaises(PermissionError):
                create_managed_user(
                    self.admin, "forbidden@campus.invalid", self.password
                )
        self.assertEqual(self.users_count(), 3)

    def test_duplicate_email_returns_conflict_without_password_echo(self):
        values = self.creation_form(email="STUDENT@CAMPUS.INVALID")
        response = self.client.post("/admin/users", data=values)
        self.assertEqual(response.status_code, 409)
        self.assertIn("utilise déjà cette adresse", response.text)
        self.assertNotIn(values["password"], response.text)
        self.assertNotIn("scrypt:", response.text)
        self.assertEqual(self.users_count(), 3)
        self.assertIsNotNone(authenticate("student@campus.invalid", self.password))

    def test_invalid_inputs_create_nothing_and_password_fields_stay_empty(self):
        for changes in (
            {"email": "invalid"},
            {"email": "bad @campus.invalid"},
            {"email": "bad@invalid"},
            {"password": "short", "password_confirm": "short"},
            {"password": "x" * 257, "password_confirm": "x" * 257},
            {"password_confirm": "DifferentFixturePassword!"},
            {"role": "superadmin"},
        ):
            with self.subTest(fields=tuple(changes)):
                values = self.creation_form(**changes)
                response = self.client.post("/admin/users", data=values)
                self.assertEqual(response.status_code, 400)
                self.assertNotIn(values["password"], response.text)
                self.assertIsNone(
                    re.search(r'type="password"[^>]*\bvalue=', response.text)
                )
        self.assertEqual(self.users_count(), 3)

    def test_csrf_required_and_valid_tokens_allow_creation_and_activation(self):
        self.app.config["WTF_CSRF_ENABLED"] = True
        self.assertEqual(
            self.client.post("/admin/users", data=self.creation_form()).status_code, 400
        )
        self.assertEqual(
            self.client.post(
                "/admin/users", data={**self.creation_form(), "csrf_token": "invalid"}
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                f"/admin/users/{self.student}/active", data={"active": "0"}
            ).status_code,
            400,
        )
        self.assertEqual(self.users_count(), 3)
        page = self.client.get("/admin/users/new")
        token = re.search(r'name="csrf_token"\s+value="([^"]+)"', page.text).group(1)
        self.assertEqual(
            self.client.post(
                "/admin/users", data={**self.creation_form(), "csrf_token": token}
            ).status_code,
            303,
        )
        page = self.client.get("/admin/users")
        token = re.search(r'name="csrf_token"\s+value="([^"]+)"', page.text).group(1)
        self.assertEqual(
            self.client.post(
                f"/admin/users/{self.student}/active",
                data={"active": "0", "csrf_token": token},
            ).status_code,
            303,
        )
        self.assertFalse(get_user(self.student).active)

    def test_disable_revokes_existing_session_without_deleting_data(self):
        student_client = self.app.test_client()
        self.sign_in("student@campus.invalid", student_client)
        application = create_user_application(
            self.student, "Entreprise conservée", "Poste conservé"
        )
        self.assertEqual(student_client.get("/").status_code, 200)
        response = self.client.post(
            f"/admin/users/{self.student}/active", data={"active": "0"}
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(student_client.get("/").status_code, 302)
        self.assertIsNone(authenticate("student@campus.invalid", self.password))
        with get_connection() as connection:
            self.assertIsNotNone(
                connection.execute(
                    "SELECT id FROM applications WHERE id=? AND user_id=?",
                    (application, self.student),
                ).fetchone()
            )
        self.assertEqual(
            self.client.post(
                f"/admin/users/{self.student}/active", data={"active": "1"}
            ).status_code,
            303,
        )
        self.assertIsNotNone(authenticate("student@campus.invalid", self.password))

    def test_activation_is_idempotent_and_does_not_accept_role_changes(self):
        for _ in range(2):
            self.assertEqual(
                self.client.post(
                    f"/admin/users/{self.student}/active",
                    data={"active": "0", "role": "admin"},
                ).status_code,
                303,
            )
        user = get_user(self.student)
        self.assertFalse(user.active)
        self.assertEqual(user.role, "student")

    def test_admin_cannot_disable_own_account_or_last_admin(self):
        self.assertEqual(
            self.client.post(
                f"/admin/users/{self.admin}/active", data={"active": "0"}
            ).status_code,
            409,
        )
        self.assertTrue(get_user(self.admin).active)
        self.assertEqual(self.client.get("/admin/users").status_code, 200)

    def test_invalid_activation_or_missing_user_is_rejected(self):
        for state in ("yes", "-1", "2", ""):
            self.assertEqual(
                self.client.post(
                    f"/admin/users/{self.student}/active", data={"active": state}
                ).status_code,
                400,
            )
        self.assertEqual(
            self.client.post(
                "/admin/users/99999/active", data={"active": "0"}
            ).status_code,
            404,
        )
        self.assertTrue(get_user(self.student).active)

    def test_admin_role_does_not_grant_access_to_other_users_applications(self):
        application = create_user_application(
            self.student, "Entreprise privée", "Poste privé"
        )
        self.assertEqual(
            self.client.get(f"/application/{application}").status_code, 404
        )
        self.assertNotIn("Entreprise privée", self.client.get("/").text)

    def test_client_supplied_actor_id_cannot_override_authenticated_role(self):
        client = self.app.test_client()
        self.sign_in("student@campus.invalid", client)
        self.assertEqual(
            client.post(
                "/admin/users",
                data={**self.creation_form(role="admin"), "actor_id": self.admin},
            ).status_code,
            403,
        )
        self.assertEqual(self.users_count(), 3)

    def test_hashing_failure_never_exposes_exception_or_password(self):
        with patch(
            "app.admin_accounts.generate_password_hash",
            side_effect=ValueError("SECRET-FIXTURE-HASH"),
        ):
            response = self.client.post("/admin/users", data=self.creation_form())
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("SECRET-FIXTURE-HASH", response.text)
        self.assertNotIn("NewFixturePassword2026!", response.text)
        self.assertEqual(self.users_count(), 3)

    def test_disabled_admin_cannot_disable_remaining_admin(self):
        second = create_user("second-admin@campus.invalid", self.password, "admin")
        self.assertTrue(set_managed_user_active(self.admin, second, False))
        with self.assertRaises(PermissionError):
            set_managed_user_active(second, self.admin, False)
        self.assertTrue(get_user(self.admin).active)
        self.assertFalse(get_user(second).active)
