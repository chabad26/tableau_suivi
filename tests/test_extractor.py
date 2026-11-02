import unittest

from app.connectors.common import extract_html_preheader, html_to_text
from app.extractor import (
    company_key,
    extract_application_data,
    extract_job_title,
    normalize_company_name,
    normalize_email_body,
)

company_samples = [
    "Équipe de recrutement de Sopra Steria",
    "Sopra Steria",
    "Équipe RH de QOTID",
    "Recrutement LYNRED",
    "Jean Dupont - TechCorp",
    "AK Recrutement",
    "AK-Recrutement",
    "Re: Arturia",
]


job_samples = [
    ("Votre candidature : Développeur Full Stack Php Symfony Vue JS - Freelance", ""),
    ("Entretien téléphonique - Développeur IT (H/F)", ""),
    (
        "Merci pour votre candidature spontanée",
        "Nous avons bien reçu votre candidature au poste de Technicien systèmes et réseaux (F/H).",
    ),
    ("Application received", "Job title: Senior Backend Developer"),
    (
        "Votre candidature",
        "Vous avez postulé au poste de Administrateur Systèmes et Réseaux.",
    ),
]


class ExtractorTests(unittest.TestCase):
    def test_hidden_html_preheader_is_extracted(self):

        html_body = """
        <html>
            <body>
                <div
                    style="
                        display:none;
                        max-height:0;
                        overflow:hidden;
                    "
                    aria-hidden="true"
                >
                    Merci d'avoir postulé pour le poste
                    Administrateur système et réseaux h/f
                    chez WIDIP.
                </div>

                <p>
                    Votre candidature n'a pas été retenue.
                </p>
            </body>
        </html>
        """

        preheader = extract_html_preheader(html_body)

        self.assertIn("Administrateur système et réseaux h/f", preheader)

        normalized = html_to_text(html_body)

        self.assertIn("Administrateur système et réseaux h/f", normalized)

    def test_indeed_html_extracts_company_job_and_source(self):
        subject = "Des nouvelles de votre candidature pour WIDIP"

        sender = "Indeed <notifications@indeed.com>"

        body = """
        <!doctype html>
        <html>
            <body>
                <h1>
                    Des nouvelles de votre candidature
                    pour WIDIP
                </h1>

                <p>
                    Merci d'avoir postulé pour le poste
                    Administrateur système et réseaux h/f
                    chez WIDIP.
                </p>

                <p>
                    Malheureusement, WIDIP est désormais
                    à l'étape suivante de son processus
                    de recrutement et votre candidature
                    n'a pas été retenue.
                </p>
            </body>
        </html>
        """

        company, job_title, source = extract_application_data(subject, sender, body)

        self.assertEqual(company, "WIDIP")

        self.assertEqual(job_title, "Administrateur système et réseaux h/f")

        self.assertEqual(source, "Indeed")

    def test_html_body_is_normalized_before_extraction(self):
        body = """
        <html>
            <head>
                <style>
                    p { color: red; }
                </style>
            </head>
            <body>
                <p>
                    Merci d'avoir postulé pour le poste
                    Administrateur DevOps chez ACME.
                </p>
            </body>
        </html>
        """

        normalized = normalize_email_body(body)

        self.assertNotIn("<p>", normalized)

        self.assertNotIn("color: red", normalized)

        self.assertIn("Administrateur DevOps", normalized)

        self.assertEqual(extract_job_title("", body), "Administrateur DevOps")


class ApplicationReceiptTitleTests(unittest.TestCase):
    def test_recorded_application_extracts_quoted_title(self):
        subject = "Votre candidature est arrivée chez GERARD PERRIER INDUSTRIE"
        body = (
            "votre candidature est enregistrée. "
            '"ingénieur cybersécurité industrielle h/f" '
            "pour l'entreprise gerard perrier industrie"
        )
        company, title, _ = extract_application_data(
            subject, "Notifications <notifications@example.invalid>", body
        )
        self.assertEqual(company, "GERARD PERRIER INDUSTRIE")
        self.assertEqual(title, "ingénieur cybersécurité industrielle h/f")

    def test_linkedin_receipt_separates_title_company_city_and_link(self):
        subject = "Camille, votre candidature a été envoyée à XEFI"
        body = (
            "votre candidature a été envoyée à xefi "
            "technicien systeme et reseau (h/f) xefi bourgoin-jallieu "
            "voir l’offre d’emploi : https://www.linkedin.com/comm/jobs/view/0000000000/"
        )
        self.assertEqual(
            extract_application_data(
                subject, "LinkedIn <notifications@linkedin.com>", body
            ),
            ("XEFI", "technicien systeme et reseau (h/f)", "LinkedIn"),
        )

    def test_quoted_title_accepts_french_quotes_and_html(self):
        body = (
            "<p>Votre candidature est enregistrée.</p>"
            "<p>&laquo; Ingénieur cybersécurité industrielle H/F &raquo; "
            "pour l’entreprise ACME</p>"
        )
        self.assertEqual(
            extract_job_title("Votre candidature", body),
            "Ingénieur cybersécurité industrielle H/F",
        )

    def test_sent_receipt_is_not_specific_to_xefi_or_one_gender_marker(self):
        for marker in ("H/F", "F/H", "H / F"):
            with self.subTest(marker=marker):
                subject = "Votre candidature a été envoyée à ACME (France)"
                body = f"Votre candidature a été envoyée à ACME (France) Développeur C++ ({marker}) ACME (France) Grenoble Voir l’offre d’emploi"
                self.assertEqual(
                    extract_job_title(subject, body), f"Développeur C++ ({marker})"
                )

    def test_employer_only_subjects_do_not_invent_titles(self):
        for subject in (
            "Votre candidature est arrivée chez GERARD PERRIER INDUSTRIE",
            "Votre candidature a été envoyée à XEFI",
        ):
            with self.subTest(subject=subject):
                self.assertEqual(extract_job_title(subject), "")
                self.assertEqual(
                    extract_job_title(subject, "Merci pour votre candidature."), ""
                )

    def test_sent_receipt_requires_matching_employer_and_title_boundary(self):
        subject = "Votre candidature a été envoyée à XEFI"
        for body in (
            "Votre candidature a été envoyée à XEFI. Voir l’offre d’emploi : https://example.invalid",
            "Votre candidature a été envoyée à ACME Technicien réseaux (H/F) ACME Grenoble",
            "Votre candidature a été envoyée à XEFI Technicien réseaux (H/F) Grenoble",
        ):
            with self.subTest(body=body):
                self.assertEqual(extract_job_title(subject, body), "")

    def test_explicit_subject_title_keeps_priority_over_receipt_body(self):
        self.assertEqual(
            extract_job_title(
                "Votre candidature : Administrateur réseaux",
                'Votre candidature est enregistrée. "Ingénieur sécurité H/F" pour l’entreprise ACME',
            ),
            "Administrateur réseaux",
        )


def main() -> None:
    print()
    print("=" * 90)
    print("TEST ENTREPRISES")
    print("=" * 90)

    for company in company_samples:
        normalized = normalize_company_name(company)
        key = company_key(company)

        print(f"{company:<45} → {normalized:<25} → {key}")

    print()
    print("=" * 90)
    print("TEST POSTES")
    print("=" * 90)

    for subject, body in job_samples:
        job_title = extract_job_title(subject, body)

        print(f"Sujet : {subject}")
        print(f"Poste : {job_title or '-'}")
        print("-" * 90)


if __name__ == "__main__":
    main()
