"""Tests de connexion et de contrôle d'accès."""

from app.accounts import create_user, set_user_active
from tests.helpers import OfflineCase


class AuthenticationTests(OfflineCase):

    def setUp(self):
        super().setUp()

        self.app.config["WTF_CSRF_ENABLED"] = False

        self.user_id = create_user(
            email="alice@example.invalid",
            password="MotDePasseDeTest2026!",
            role="student",
        )

    def login(self, password="MotDePasseDeTest2026!"):
        return self.client.post(
            "/login",
            data={
                "email": "alice@example.invalid",
                "password": password,
            },
        )

    def test_login_page_is_public(self):
        response = self.client.get("/login")

        self.assertEqual(response.status_code, 200)

    def test_private_routes_require_login(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 302)

        self.assertIn("/login", response.headers["Location"])

    def test_valid_login(self):
        response = self.login()

        self.assertEqual(response.status_code, 303)

        account = self.client.get("/account")

        self.assertEqual(account.status_code, 200)

        self.assertIn(
            b"alice@example.invalid",
            account.data,
        )

    def test_invalid_password(self):
        response = self.login("mot-de-passe-invalide")

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            self.client.get("/").status_code,
            302,
        )

    def test_disabled_user_cannot_login(self):
        set_user_active(self.user_id, False)

        response = self.login()

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            self.client.get("/account").status_code,
            302,
        )

    def test_disabled_user_loses_access(self):
        self.login()

        set_user_active(self.user_id, False)

        response = self.client.get("/account")

        self.assertEqual(response.status_code, 302)

    def test_logout(self):
        self.login()

        response = self.client.post("/logout")

        self.assertEqual(response.status_code, 303)

        self.assertEqual(
            self.client.get("/account").status_code,
            302,
        )

    def test_legacy_routes_are_blocked_after_login(self):
        self.login()

        response = self.client.get("/")

        self.assertEqual(response.status_code, 503)