"""HTML hostile, alternatives MIME et contrôle d'accès, sans réseau."""

import unittest
from email.message import EmailMessage
from html.parser import HTMLParser

from app.accounts import create_user
from app.connectors.common import MAX_EMAIL_HTML_LENGTH, get_message_html
from app.database import get_connection
from app.email_rendering import CLEANER, render_email_body
from app.owned_importer import import_user_emails
from tests.helpers import OfflineCase, fake_email


class Frames(HTMLParser):
    def __init__(self):
        super().__init__()
        self.frames = []

    def handle_starttag(self, tag, attrs):
        if tag == "iframe":
            self.frames.append(dict(attrs))


class EmailRenderingTests(unittest.TestCase):
    def test_formatting_survives_without_active_content(self):
        source = """<p id="location" onclick="bad()" style="background:url(https://tracker.invalid)">Bonjour <strong>Alice</strong></p>
        <table><tr><td colspan="2">Poste</td></tr></table>
        <script>secret_script()</script><style>secret_style</style>
        <img src="https://tracker.invalid/pixel"><img src="cid:photo">
        <svg onload="bad()"><text>secret_svg</text></svg>
        <iframe src="https://tracker.invalid"></iframe><form>secret_form</form>
        <meta http-equiv="refresh" content="0;url=https://tracker.invalid"><base href="https://tracker.invalid">"""
        cleaned = CLEANER.clean(source)
        self.assertIn("<strong>Alice</strong>", cleaned)
        self.assertIn('colspan="2"', cleaned)
        for forbidden in (
            "secret_",
            "tracker.invalid",
            "<img",
            "<script",
            "onclick",
            "style=",
            "id=",
            "<svg",
            "<iframe",
            "<form",
            "<meta",
            "<base",
        ):
            self.assertNotIn(forbidden, cleaned)

    def test_links_require_explicit_http_destination(self):
        for url in (
            "javascript:alert(1)",
            "data:text/html,bad",
            "//example.invalid",
            "/logout",
            "https://user:pass@example.invalid",
            "https://example.invalid:bad",
            "https://example.invalid/with space",
        ):
            with self.subTest(url=url):
                self.assertNotIn("href=", CLEANER.clean(f'<a href="{url}">Lien</a>'))
        cleaned = CLEANER.clean(
            '<a href="https://example.invalid/job?a=1&amp;b=2" target="_top" rel="opener">Offre</a>'
        )
        self.assertIn('href="https://example.invalid/job?a=1&amp;b=2"', cleaned)
        self.assertIn('target="_blank"', cleaned)
        self.assertIn('rel="noopener noreferrer"', cleaned)

    def test_plain_legacy_encoded_and_oversized_bodies(self):
        self.assertIsNone(
            render_email_body("Salaire < 3000 et expérience > 2 ans")["html_document"]
        )
        for body in ("<p>Bonjour</p>", "&lt;p&gt;Bonjour&lt;/p&gt;"):
            result = render_email_body(body)
            self.assertIn("<p>Bonjour</p>", result["html_document"])
            self.assertEqual(result["text_body"], body)
        self.assertIsNone(
            render_email_body("Texte", "x" * (MAX_EMAIL_HTML_LENGTH + 1))[
                "html_document"
            ]
        )
        self.assertIsNone(
            render_email_body("Texte", "<script>bad()</script>")["html_document"]
        )

    def test_mime_preserves_html_without_attachments(self):
        message = EmailMessage()
        message.set_content("Texte de classification")
        message.add_alternative("<p>Bonjour <strong>Alice</strong></p>", subtype="html")
        self.assertIn("<strong>Alice</strong>", get_message_html(message))
        attached = EmailMessage()
        attached.set_content("<p>Pièce jointe</p>", subtype="html")
        attached.add_header("Content-Disposition", "attachment", filename="mail.html")
        self.assertEqual(get_message_html(attached), "")
        wrapper = EmailMessage()
        wrapper.set_content("Corps simple")
        wrapper.add_attachment(message)
        self.assertEqual(get_message_html(wrapper), "")

    def test_oversized_html_and_unknown_charset(self):
        message = EmailMessage()
        message.set_content("x" * (MAX_EMAIL_HTML_LENGTH + 1), subtype="html")
        self.assertEqual(get_message_html(message), "")
        message.set_content("<p>Bonjour</p>", subtype="html")
        message.set_param("charset", "unknown-charset")
        self.assertIn("<p>Bonjour</p>", get_message_html(message))


class EmailHtmlWebTests(OfflineCase):
    def test_html_is_isolated_and_foreign_mail_remains_private(self):
        alice = self.login_test_user()
        raw = '<p>Bonjour</p><script>attack()</script><img src="https://pixel.invalid">'
        import_user_emails(alice, [fake_email(html_body=raw)])
        with get_connection() as connection:
            before = dict(connection.execute("SELECT * FROM emails").fetchone())
        path = f"/application/{before['application_id']}"
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        parser = Frames()
        parser.feed(response.text)
        self.assertEqual(len(parser.frames), 1)
        frame = parser.frames[0]
        self.assertEqual(
            set(frame["sandbox"].split()),
            {"allow-popups", "allow-popups-to-escape-sandbox"},
        )
        self.assertEqual(frame["referrerpolicy"], "no-referrer")
        self.assertIn("default-src 'none'", frame["srcdoc"])
        self.assertIn("<p>Bonjour</p>", frame["srcdoc"])
        self.assertNotIn("attack()", frame["srcdoc"])
        self.assertNotIn("pixel.invalid", frame["srcdoc"])
        with get_connection() as connection:
            self.assertEqual(
                dict(connection.execute("SELECT * FROM emails").fetchone()), before
            )
        self.client.post("/logout")
        self.assertEqual(self.client.get(path).status_code, 302)
        self.login_test_user("bob@example.invalid")
        self.assertEqual(self.client.get(path).status_code, 404)

    def test_admin_cannot_view_another_users_email(self):
        alice = self.create_test_user()
        import_user_emails(alice, [fake_email(html_body="<p>Privé</p>")])
        with get_connection() as connection:
            application_id = connection.execute(
                "SELECT application_id FROM emails"
            ).fetchone()[0]
        create_user("admin@example.invalid", "MotDePasseAdmin2026!", role="admin")
        self.client.post(
            "/login",
            data={"email": "admin@example.invalid", "password": "MotDePasseAdmin2026!"},
        )
        self.assertEqual(
            self.client.get(f"/application/{application_id}").status_code, 404
        )
