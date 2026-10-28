"""Tests de protection des actions HTTP contre les requêtes CSRF."""

import re

from app import database, jobs
from tests.helpers import OfflineCase


class CSRFTests(OfflineCase):
    def setUp(self):
        super().setUp()
        self.app.config.update(WTF_CSRF_ENABLED=True)

    def token(self, page: str) -> str:
        response = self.client.get(page)
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
        self.assertIsNotNone(match, f"Jeton CSRF manquant dans {page}")
        assert match is not None
        return match.group(1)

    def test_missing_token_refuses_creation(self):
        response = self.client.post(
            "/application/new", data={"company": "Fausse société", "status": "SENT"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(database.get_applications(), [])

    def test_invalid_token_refuses_scan(self):
        response = self.client.post("/scan", data={"csrf_token": "incorrect"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(jobs.list_jobs()), 0)

    def test_valid_token_allows_creation(self):
        token = self.token("/application/new")
        response = self.client.post(
            "/application/new",
            data={"company": "Entreprise test", "status": "SENT", "csrf_token": token},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(database.get_applications()), 1)

    def test_valid_token_allows_scan(self):
        token = self.token("/")
        response = self.client.post("/scan", data={"csrf_token": token})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(len(jobs.list_jobs()), 1)

    def test_imap_form_contains_token(self):
        self.token("/connectors/imap/add")
