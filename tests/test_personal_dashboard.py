"""Tests HTTP d'isolation entre utilisateurs."""

from app.accounts import create_user
from app.owned_applications import create_user_application, get_user_application
from tests.helpers import OfflineCase


class PersonalDashboardTests(OfflineCase):

    def setUp(self):
        super().setUp()

        # Les tests CSRF sont dans tests/test_csrf.py.
        self.app.config["WTF_CSRF_ENABLED"] = False

        self.alice_id = create_user(
            email="alice@example.invalid",
            password="MotDePasseAlice2026!",
            role="student",
        )

        self.bob_id = create_user(
            email="bob@example.invalid",
            password="MotDePasseBob2026!",
            role="student",
        )

        self.alice_application = create_user_application(
            self.alice_id,
            "Entreprise Alice",
            "Développeuse Python",
        )

        self.bob_application = create_user_application(
            self.bob_id,
            "Entreprise Bob",
            "Administrateur réseau",
        )

    def login_as_alice(self):
        response = self.client.post(
            "/login",
            data={
                "email": "alice@example.invalid",
                "password": "MotDePasseAlice2026!",
            },
        )

        self.assertEqual(response.status_code, 303)

    def test_dashboard_requires_login(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 302)

    def test_alice_sees_only_her_applications(self):
        self.login_as_alice()

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)

        html = response.get_data(as_text=True)

        self.assertIn("Entreprise Alice", html)
        self.assertNotIn("Entreprise Bob", html)

    def test_alice_cannot_view_bob_application(self):
        self.login_as_alice()

        response = self.client.get(
            f"/application/{self.bob_application}"
        )

        self.assertEqual(response.status_code, 404)

    def test_alice_cannot_edit_bob_application(self):
        self.login_as_alice()

        response = self.client.post(
            f"/application/{self.bob_application}/edit",
            data={
                "company": "Entreprise piratée",
                "job_title": "Administrateur réseau",
                "source": "Test",
                "status": "REJECTED",
                "note": "Modification interdite",
            },
        )

        self.assertEqual(response.status_code, 404)

        application = get_user_application(
            self.bob_id,
            self.bob_application,
        )

        assert application is not None

        self.assertEqual(
            application["company"],
            "Entreprise Bob",
        )

    def test_alice_cannot_delete_bob_application(self):
        self.login_as_alice()

        response = self.client.post(
            f"/application/{self.bob_application}/delete"
        )

        self.assertEqual(response.status_code, 404)

        self.assertIsNotNone(
            get_user_application(
                self.bob_id,
                self.bob_application,
            )
        )

    def test_alice_can_create_her_application(self):
        self.login_as_alice()

        response = self.client.post(
            "/application/new",
            data={
                "company": "Nouvelle entreprise Alice",
                "job_title": "Développeuse Flask",
                "source": "Campus",
                "status": "SENT",
                "note": "Candidature spontanée",
            },
        )

        self.assertEqual(response.status_code, 303)

        html = self.client.get("/").get_data(as_text=True)

        self.assertIn("Nouvelle entreprise Alice", html)

    def test_alice_can_delete_her_application(self):
        self.login_as_alice()

        response = self.client.post(
            f"/application/{self.alice_application}/delete"
        )

        self.assertEqual(response.status_code, 303)

        self.assertIsNone(
            get_user_application(
                self.alice_id,
                self.alice_application,
            )
        )

    def test_legacy_exports_and_jobs_stay_blocked(self):
        self.login_as_alice()

        self.assertEqual(
            self.client.get("/export/csv").status_code,
            503,
        )

        self.assertEqual(
            self.client.get("/jobs").status_code,
            503,
        )

        self.assertEqual(
            self.client.get("/connectors").status_code,
            503,
        )