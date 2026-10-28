"""Tests de protection CSRF avec authentification."""

import re

from app import database, jobs
from app.owned_applications import get_user_applications
from tests.helpers import OfflineCase


class CSRFTests(OfflineCase):
    def setUp(self):
        super().setUp()

        self.app.config["WTF_CSRF_ENABLED"] = True

    def token(self, page: str) -> str:
        response = self.client.get(page)

        self.assertEqual(response.status_code, 200)

        html = response.get_data(as_text=True)

        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)

        self.assertIsNotNone(match, f"Jeton CSRF manquant dans {page}")

        assert match is not None

        return match.group(1)

    def authenticate(self) -> int:
        login_token = self.token("/login")

        return self.login_test_user(csrf_token=login_token)

    def test_missing_token_refuses_creation(self):
        user_id = self.authenticate()

        response = self.client.post(
            "/application/new", data={"company": "Fausse société", "status": "SENT"}
        )

        self.assertEqual(response.status_code, 400)

        self.assertEqual(get_user_applications(user_id), [])

    def test_valid_token_allows_creation(self):
        user_id = self.authenticate()

        token = self.token("/application/new")

        response = self.client.post(
            "/application/new",
            data={"company": "Entreprise test", "status": "SENT", "csrf_token": token},
        )

        self.assertEqual(response.status_code, 303)

        self.assertEqual(len(get_user_applications(user_id)), 1)

    def test_invalid_token_refuses_scan(self):
        self.authenticate()

        response = self.client.post("/scan", data={"csrf_token": "incorrect"})

        self.assertEqual(response.status_code, 400)

        self.assertEqual(len(jobs.list_jobs()), 0)

    def test_valid_token_does_not_unlock_scan(self):
        self.authenticate()

        token = self.token("/")

        response = self.client.post("/scan", data={"csrf_token": token})

        # Un jeton valide ne donne pas accès à une route
        # qui n'est pas encore sécurisée par utilisateur.
        self.assertEqual(response.status_code, 503)

        self.assertEqual(len(jobs.list_jobs()), 0)

    def test_unmigrated_imap_form_is_blocked(self):
        self.authenticate()

        response = self.client.get("/connectors/imap/add")

        self.assertEqual(response.status_code, 503)

    def test_login_form_contains_token(self):
        self.token("/login")

    def test_logout_requires_csrf(self):
        self.authenticate()

        response = self.client.post("/logout")

        self.assertEqual(response.status_code, 400)

        # Le CSRF invalide ne doit pas déconnecter l'utilisateur.
        self.assertEqual(self.client.get("/account").status_code, 200)
