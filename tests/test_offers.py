"""Offres : conservation du contenu et des droits, sans téléchargement réseau."""

import re
import sqlite3
from contextlib import closing
from unittest import TestCase
from unittest.mock import patch

from app import database
from app.database import get_connection, init_database
from app.extractor import extract_application_data
from app.offers import MAX_OFFER_TEXT_LENGTH, OfferInputError, validate_offer
from app.owned_applications import (
    create_user_application,
    get_user_application,
    get_user_applications,
    update_user_application_offer,
)
from app.owned_importer import import_user_emails
from app.owned_reclassifier import reclassify_user_emails
from tests.helpers import OfflineCase, fake_email


class OfferValidationTests(TestCase):
    def test_optional_fields_and_http_links(self):
        self.assertEqual(validate_offer(), ("", ""))
        text = "Poste : Technicien réseaux\n\nMissions : support et maintenance."
        self.assertEqual(
            validate_offer(f" {text} ", " https://example.invalid/job?q=1&x=2 "),
            (text, "https://example.invalid/job?q=1&x=2"),
        )
        self.assertEqual(
            validate_offer("", "http://example.invalid/jobs")[1],
            "http://example.invalid/jobs",
        )

    def test_invalid_or_active_url_schemes_are_rejected(self):
        for url in (
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "file:///etc/passwd",
            "ftp://example.invalid/job",
            "//example.invalid/job",
            "https://",
            "https://user:password@example.invalid/job",
            "https://exa mple.invalid",
            "https://example.invalid/job\nx",
            "https://example.invalid/job\x7fx",
            "https://example.invalid\\evil",
            "https://example.invalid:65536/job",
        ):
            with self.subTest(url=url), self.assertRaises(OfferInputError):
                validate_offer("", url)

    def test_length_limits_are_enforced_server_side(self):
        self.assertEqual(
            len(validate_offer("x" * MAX_OFFER_TEXT_LENGTH)[0]), MAX_OFFER_TEXT_LENGTH
        )
        for text, url in (
            ("x" * (MAX_OFFER_TEXT_LENGTH + 1), ""),
            ("", "https://example.invalid/" + "x" * 2048),
        ):
            with self.assertRaises(OfferInputError):
                validate_offer(text, url)


class OfferApplicationTests(OfflineCase):
    def setUp(self):
        super().setUp()
        self.alice = self.login_test_user("alice@example.invalid")
        self.bob = self.create_test_user("bob@example.invalid")
        self.application = create_user_application(
            self.alice, "Entreprise Alice", "Technicien réseaux"
        )
        self.foreign = create_user_application(
            self.bob, "Entreprise Bob", "Ingénieur sécurité"
        )
        self.route = f"/application/{self.application}/offer"

    def test_legacy_schema_migration_preserves_rows_and_is_idempotent(self):
        path = self.root / "legacy-offers.sqlite3"
        with closing(sqlite3.connect(path)) as connection, connection:
            connection.execute(
                "CREATE TABLE applications (id INTEGER PRIMARY KEY, company TEXT NOT NULL, job_title TEXT, source TEXT, first_seen TEXT NOT NULL, last_update TEXT NOT NULL, current_status TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO applications VALUES (5, 'Entreprise historique', 'Technicien', 'Manuel', '2020-01-01', '2020-01-02', 'RECEIVED')"
            )
        with patch.object(database, "DATABASE_PATH", path):
            init_database()
            init_database()
            with get_connection() as connection:
                row = connection.execute(
                    "SELECT * FROM applications WHERE id=5"
                ).fetchone()
                self.assertEqual(
                    (
                        row["company"],
                        row["job_title"],
                        row["last_update"],
                        row["current_status"],
                    ),
                    ("Entreprise historique", "Technicien", "2020-01-02", "RECEIVED"),
                )
                self.assertEqual((row["offer_text"], row["offer_url"]), ("", ""))
                names = [
                    r["name"]
                    for r in connection.execute("PRAGMA table_info(applications)")
                ]
                self.assertEqual(names.count("offer_text"), 1)
                self.assertEqual(names.count("offer_url"), 1)

    def test_create_from_web_stores_both_fields_for_session_owner(self):
        text = "Missions\nSupport réseau\n\nCompétences : Linux"
        response = self.client.post(
            "/application/new",
            data={
                "company": "ACME",
                "job_title": "Technicien",
                "status": "RECEIVED",
                "offer_url": "https://example.invalid/jobs/1",
                "offer_text": text,
                "user_id": self.bob,
            },
        )
        self.assertEqual(response.status_code, 303)
        identifier = int(response.headers["Location"].rsplit("/", 1)[1])
        row = get_user_application(self.alice, identifier)
        self.assertEqual(
            (row["offer_text"], row["offer_url"]),
            (text, "https://example.invalid/jobs/1"),
        )
        self.assertIsNone(get_user_application(self.bob, identifier))

    def test_offer_edit_changes_no_status_details_notes_or_timestamps(self):
        with get_connection() as connection:
            connection.execute(
                "UPDATE applications SET manual_override=0, manual_status=NULL WHERE id=?",
                (self.application,),
            )
        before = dict(get_user_application(self.alice, self.application))
        response = self.client.post(
            self.route,
            data={
                "offer_text": "Texte d'offre",
                "offer_url": "https://example.invalid/job",
                "status": "REJECTED",
                "job_title": "À ignorer",
                "user_id": self.bob,
            },
        )
        self.assertEqual(response.status_code, 303)
        after = dict(get_user_application(self.alice, self.application))
        for field in set(before) - {"offer_text", "offer_url"}:
            self.assertEqual(after[field], before[field], field)
        self.assertEqual(after["offer_text"], "Texte d'offre")
        self.assertEqual(
            self.client.post(
                self.route, data={"offer_text": "", "offer_url": ""}
            ).status_code,
            303,
        )
        row = get_user_application(self.alice, self.application)
        self.assertEqual((row["offer_text"], row["offer_url"]), ("", ""))

    def test_foreign_offers_cannot_be_seen_or_changed(self):
        self.assertEqual(
            self.client.post(
                f"/application/{self.foreign}/offer", data={"offer_text": "Forbidden"}
            ).status_code,
            404,
        )
        self.assertFalse(
            update_user_application_offer(self.alice, self.foreign, "Forbidden", "")
        )
        self.assertEqual(
            self.client.get(f"/application/{self.foreign}").status_code, 404
        )
        self.assertEqual(get_user_application(self.bob, self.foreign)["offer_text"], "")
        anonymous = self.app.test_client()
        self.assertEqual(
            anonymous.post(self.route, data={"offer_text": "Forbidden"}).status_code,
            302,
        )

    def test_failed_edit_preserves_stored_offer_and_input(self):
        update_user_application_offer(
            self.alice,
            self.application,
            "Offre initiale",
            "https://example.invalid/old",
        )
        response = self.client.post(
            self.route,
            data={
                "offer_text": "Nouveau texte conservé dans le formulaire",
                "offer_url": "javascript:alert(1)",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Nouveau texte conservé dans le formulaire", response.text)
        self.assertNotIn('href="javascript:', response.text)
        self.assertEqual(
            get_user_application(self.alice, self.application)["offer_text"],
            "Offre initiale",
        )

    def test_failed_creation_preserves_input_and_creates_no_application(self):
        before = len(get_user_applications(self.alice))
        response = self.client.post(
            "/application/new",
            data={
                "company": "ACME",
                "job_title": "Technicien",
                "status": "RECEIVED",
                "note": "Note à conserver",
                "offer_text": "Texte à conserver",
                "offer_url": "invalid",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(get_user_applications(self.alice)), before)
        for value in ("ACME", "Technicien", "Note à conserver", "Texte à conserver"):
            self.assertIn(value, response.text)

    def test_plain_text_and_url_are_escaped_and_link_opens_separately(self):
        text = '</textarea><script>alert("offer")</script>\nSeconde ligne'
        url = 'https://example.invalid/job?q="test"&a=2'
        update_user_application_offer(self.alice, self.application, text, url)
        response = self.client.get(f"/application/{self.application}")
        self.assertNotIn('<script>alert("offer")</script>', response.text)
        self.assertIn("&lt;script&gt;", response.text)
        self.assertIn('target="_blank" rel="noopener noreferrer"', response.text)
        self.assertIn("&amp;a=2", response.text)
        self.assertEqual(
            get_user_application(self.alice, self.application)["offer_text"], text
        )

    def test_offer_edit_requires_csrf_and_accepts_valid_form_token(self):
        self.app.config["WTF_CSRF_ENABLED"] = True
        self.assertEqual(
            self.client.post(self.route, data={"offer_text": "Blocked"}).status_code,
            400,
        )
        html = self.client.get(f"/application/{self.application}").text
        token = re.search(r'name="csrf_token"\s+value="([^"]+)"', html).group(1)
        self.assertEqual(
            self.client.post(
                self.route, data={"offer_text": "Valid", "csrf_token": token}
            ).status_code,
            303,
        )

    def test_import_and_reanalysis_preserve_saved_offer(self):
        message = fake_email("<offer@example.invalid>")
        company, title, source = extract_application_data(
            message.subject, message.sender, message.body
        )
        identifier = create_user_application(
            self.alice,
            company,
            title,
            source,
            offer_text="Offre conservée",
            offer_url="https://example.invalid/archive",
        )
        import_user_emails(self.alice, [message])
        reclassify_user_emails(self.alice)
        row = get_user_application(self.alice, identifier)
        self.assertEqual(
            (row["offer_text"], row["offer_url"]),
            ("Offre conservée", "https://example.invalid/archive"),
        )
