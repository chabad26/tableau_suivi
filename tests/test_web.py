from app import database, jobs
from app.owned_applications import create_user_application, get_user_application
from app.presentation import application_statistics, format_datetime
from tests.helpers import OfflineCase


class WebTests(OfflineCase):
    def test_dashboard_displays_each_application_once(self):
        application_id = self.owned_application()
        html = self.client.get("/").get_data(as_text=True)
        self.assertEqual(html.count(f'href="/application/{application_id}"'), 1)
        self.assertEqual(html.count("<!DOCTYPE html>"), 1)

    def test_search_and_status_filters(self):
        selected = self.owned_application("École Fictive")

        self.owned_application("Autre Entreprise")

        from app.owned_applications import set_user_application_status

        changed = set_user_application_status(
            self.user_id, selected, "INTERVIEW", "Rappel UNIQUE"
        )

        self.assertTrue(changed)

        query = "?q=unique&status=INTERVIEW"

        response = self.client.get("/" + query)

        self.assertEqual(response.status_code, 200)

        html = response.get_data(as_text=True)

        self.assertIn("École Fictive", html)
        self.assertNotIn("Autre Entreprise", html)

    def test_exports_remain_blocked(self):
        self.assertEqual(self.client.get("/export/csv").status_code, 503)

        self.assertEqual(self.client.get("/export/xlsx").status_code, 503)

    def test_detail_and_create_edit_delete_routes(self):
        response = self.client.post(
            "/application/new",
            data={
                "company": "Entreprise Fictive",
                "job_title": "Développeur Python",
                "status": "SENT",
                "note": "Note fictive",
            },
        )
        self.assertEqual(response.status_code, 303)
        application_id = int(response.headers["Location"].rsplit("/", 1)[1])
        detail = self.client.get(response.headers["Location"])
        self.assertEqual(detail.status_code, 200)
        self.assertIn(b"application.js", detail.data)
        response = self.client.post(
            f"/application/{application_id}/edit",
            data={
                "company": "Entreprise Modifiée",
                "job_title": "Développeur Python",
                "source": "Fixture",
                "status": "INTERVIEW",
                "note": "Nouvelle note",
            },
        )
        self.assertEqual(response.status_code, 303)
        application = get_user_application(self.user_id, application_id)
        if application is None:
            self.fail("Application was not found after creation")
        self.assertEqual(application["manual_status"], "INTERVIEW")
        self.assertEqual(
            self.client.post(f"/application/{application_id}/delete").status_code, 303
        )
        self.assertEqual(
            self.client.get(f"/application/{application_id}").status_code, 404
        )

    def test_invalid_forms_and_missing_application(self):
        self.assertEqual(
            self.client.post(
                "/application/new", data={"company": "", "status": "SENT"}
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                "/application/new", data={"company": "Fixture", "status": "INVALID"}
            ).status_code,
            400,
        )
        self.assertEqual(self.client.get("/application/9999").status_code, 404)
        self.assertEqual(self.client.get("/application/new").status_code, 200)

    def test_imap_test_route_is_blocked(self):
        account_id = database.create_imap_account(
            email="test@example.invalid",
            provider="imap",
            host="imap.example.invalid",
            port=993,
            use_ssl=True,
            username="test@example.invalid",
            folder="INBOX",
            auth_method="password",
        )

        response = self.client.post(f"/connectors/imap/{account_id}/test")

        self.assertEqual(response.status_code, 503)

        self.assertEqual(len(jobs.list_jobs()), 0)

    def test_scan_and_reclassify_routes_are_blocked(self):
        scan_response = self.client.post("/scan")
        reclassify_response = self.client.post("/reclassify")

        self.assertEqual(scan_response.status_code, 503)
        self.assertEqual(reclassify_response.status_code, 503)

        self.assertEqual(len(jobs.list_jobs()), 0)

    def test_statistics_and_date_fallback(self):
        application_id = self.application()

        database.set_manual_status(application_id, "INTERVIEW", "")

        stats = application_statistics(database.get_applications())

        self.assertEqual((stats["total"], stats["INTERVIEW"]), (1, 1))

        self.assertEqual(format_datetime(None), "-")

        self.assertEqual(format_datetime("date invalide"), "date invalide")

    def setUp(self):
        super().setUp()

        self.user_id = self.login_test_user()

    def owned_application(
        self,
        company: str = "Entreprise Fictive",
        job_title: str = "Développeur Python",
        status: str = "RECEIVED",
    ) -> int:
        return create_user_application(
            user_id=self.user_id, company=company, job_title=job_title, status=status
        )
