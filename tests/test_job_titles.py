"""Détection explicable du poste : offre, emails et décision manuelle."""

from unittest import TestCase

from app.database import get_connection
from app.job_titles import extract_offer_job_title, suggest_job_title
from app.owned_applications import (
    create_user_application,
    get_user_application,
    update_user_application_offer,
)
from app.owned_importer import import_user_emails
from app.owned_reclassifier import reclassify_user_emails
from tests.helpers import OfflineCase, fake_email


class OfferTitleTests(TestCase):
    def test_known_company_name_is_not_a_title(self):
        self.assertEqual(
            extract_offer_job_title(
                "Consultant GRC\nMissions : audit", company="Consultant GRC"
            ),
            "",
        )
        self.assertIsNone(
            suggest_job_title(
                "Poste : ACME", [("Votre candidature : ACME", "")], company="ACME"
            )
        )

    def test_explicit_labels_cover_multiple_training_domains(self):
        for label, title in (
            ("Intitulé du poste", "Analyste GRC H/F"),
            ("Poste", "Data Analyst"),
            ("Job title", "Compliance Officer"),
            ("Fonction", "Chargé de recrutement"),
        ):
            with self.subTest(label=label):
                self.assertEqual(
                    extract_offer_job_title(
                        f"{label} : {title}\nMissions : accompagnement des équipes"
                    ),
                    title,
                )

    def test_heading_html_and_recruiting_phrase(self):
        examples = [
            (
                "Campus\nTechnicien systèmes et réseaux H/F\nMissions : support",
                "Technicien systèmes et réseaux H/F",
            ),
            (
                "<h1>Data Analyst</h1><p>Analyse des données.</p><script>exfiltrate()</script>",
                "Data Analyst",
            ),
            (
                "Nous recherchons une Consultante GRC pour accompagner nos clients.",
                "Consultante GRC",
            ),
            (
                "Poste : Administrateur réseaux Lieu : Lyon Contrat : CDI",
                "Administrateur réseaux",
            ),
        ]
        for text, expected in examples:
            with self.subTest(text=text):
                self.assertEqual(extract_offer_job_title(text), expected)

    def test_ambiguous_competencies_placeholders_and_recommendations_are_ignored(self):
        for text in (
            "Poste : Data Analyst\nPoste : Auditeur GRC",
            "Poste : Non renseigné",
            "Missions\nTravailler avec un Administrateur réseaux\nCompétences : Python",
            "Réseaux et cybersécurité\nMaîtrise de Linux et de Python.",
            "Entreprise\nDescription\nSupport et maintenance\nOffres similaires\nPoste : Data Analyst",
            "Voir https://example.invalid/technicien-reseaux",
            "",
        ):
            with self.subTest(text=text):
                self.assertEqual(extract_offer_job_title(text), "")

    def test_offer_has_priority_and_email_subject_is_fallback(self):
        emails = [("Votre candidature : Technicien réseaux", "")]
        suggestion = suggest_job_title("Poste : Data Analyst", emails)
        self.assertEqual(
            (suggestion.title, suggestion.source), ("Data Analyst", "offer")
        )
        fallback = suggest_job_title("Description : compétences Python", emails)
        self.assertEqual(
            (fallback.title, fallback.source), ("Technicien réseaux", "email")
        )
        self.assertIsNone(
            suggest_job_title("", [("Merci pour votre candidature", "Merci.")])
        )


class JobTitleIntegrationTests(OfflineCase):
    def setUp(self):
        super().setUp()
        self.alice = self.login_test_user("alice@example.invalid")
        self.bob = self.create_test_user("bob@example.invalid")
        self.message = fake_email("<job-title@example.invalid>")
        import_user_emails(self.alice, [self.message])
        with get_connection() as connection:
            self.application = connection.execute(
                "SELECT id FROM applications WHERE user_id=?", (self.alice,)
            ).fetchone()[0]

    def test_reanalysis_uses_offer_even_without_emails_and_is_idempotent(self):
        no_email = create_user_application(self.alice, "ACME", "")
        with get_connection() as connection:
            connection.execute(
                "UPDATE applications SET manual_override=0 WHERE id=?", (no_email,)
            )
        update_user_application_offer(
            self.alice, no_email, "Intitulé du poste : Analyste GRC", ""
        )
        result = reclassify_user_emails(self.alice)
        self.assertGreaterEqual(result.applications_updated, 1)
        row = get_user_application(self.alice, no_email)
        self.assertEqual(row["job_title"], "Analyste GRC")
        date = row["last_update"]
        reclassify_user_emails(self.alice)
        self.assertEqual(
            get_user_application(self.alice, no_email)["last_update"], date
        )
        self.assertEqual(reclassify_user_emails(self.alice).applications_updated, 0)

    def test_offer_wins_over_email_and_other_users_are_untouched(self):
        update_user_application_offer(
            self.alice,
            self.application,
            "Poste : Data Analyst",
            "https://example.invalid/job",
        )
        other = create_user_application(
            self.bob, "ACME Bob", "Poste privé", offer_text="Poste : Auditeur GRC"
        )
        before = dict(get_user_application(self.bob, other))
        reclassify_user_emails(self.alice)
        self.assertEqual(
            get_user_application(self.alice, self.application)["job_title"],
            "Data Analyst",
        )
        self.assertEqual(dict(get_user_application(self.bob, other)), before)

    def test_manual_title_is_only_suggested_never_replaced(self):
        with get_connection() as connection:
            connection.execute(
                "UPDATE applications SET job_title='Choix manuel', manual_override=1, manual_status='INTERVIEW', manual_note='Note conservée' WHERE id=?",
                (self.application,),
            )
        update_user_application_offer(
            self.alice, self.application, "Poste : Data Analyst", ""
        )
        reclassify_user_emails(self.alice)
        row = get_user_application(self.alice, self.application)
        self.assertEqual(
            (row["job_title"], row["manual_status"], row["manual_note"]),
            ("Choix manuel", "INTERVIEW", "Note conservée"),
        )
        page = self.client.get(f"/application/{self.application}")
        self.assertIn('data-job-title="Data Analyst"', page.text)
        self.assertIn("Utiliser ce poste", page.text)

    def test_explicit_manual_choice_can_replace_equal_or_higher_scored_title(self):
        for title in ("Auditeur GRC", "Juriste", ""):
            response = self.client.post(
                f"/application/{self.application}/edit",
                data={
                    "company": "ACME",
                    "job_title": title,
                    "source": "Manuel",
                    "status": "RECEIVED",
                    "note": "Choix explicite",
                },
            )
            self.assertEqual(response.status_code, 303)
            self.assertEqual(
                get_user_application(self.alice, self.application)["job_title"], title
            )
            reclassify_user_emails(self.alice)
            self.assertEqual(
                get_user_application(self.alice, self.application)["job_title"], title
            )

    def test_new_import_preserves_manual_title_and_offer(self):
        update_user_application_offer(
            self.alice, self.application, "Poste : Analyste GRC", ""
        )
        # Le sujet est volontairement générique : il se rattache à la fiche déjà
        # présente, sans fusionner deux intitulés distincts du même employeur.
        incoming = fake_email(
            "<next-title@example.invalid>", subject="Merci pour votre candidature"
        )
        import_user_emails(self.alice, [incoming])
        self.assertEqual(
            get_user_application(self.alice, self.application)["job_title"],
            "Analyste GRC",
        )
        with get_connection() as connection:
            connection.execute(
                "UPDATE applications SET manual_override=1, job_title='Choix manuel' WHERE id=?",
                (self.application,),
            )
        import_user_emails(
            self.alice,
            [
                fake_email(
                    "<manual-title@example.invalid>",
                    subject="Merci pour votre candidature",
                )
            ],
        )
        self.assertEqual(
            get_user_application(self.alice, self.application)["job_title"],
            "Choix manuel",
        )

    def test_subject_can_recover_title_without_archived_body(self):
        with get_connection() as connection:
            connection.execute(
                "UPDATE applications SET job_title='' WHERE id=?", (self.application,)
            )
            connection.execute(
                "UPDATE emails SET body='', subject='Votre candidature : Auditeur GRC' WHERE user_id=?",
                (self.alice,),
            )
        result = reclassify_user_emails(self.alice)
        self.assertEqual(result.missing, 1)
        self.assertEqual(
            get_user_application(self.alice, self.application)["job_title"],
            "Auditeur GRC",
        )
