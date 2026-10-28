from tests.helpers import OfflineCase


class HttpSecurityTests(OfflineCase):
    def test_security_headers(self):
        response = self.client.get("/login")

        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

        self.assertEqual(response.headers["X-Frame-Options"], "DENY")

        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_session_configuration(self):
        self.assertTrue(self.app.config["SESSION_COOKIE_HTTPONLY"])

        self.assertEqual(self.app.config["SESSION_COOKIE_SAMESITE"], "Lax")
