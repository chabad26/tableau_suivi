from app.extractor import (
    company_key,
    extract_job_title,
    normalize_company_name,
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
    (
        "Votre candidature : Développeur Full Stack Php Symfony Vue JS - Freelance",
        "",
    ),
    (
        "Entretien téléphonique - Développeur IT (H/F)",
        "",
    ),
    (
        "Merci pour votre candidature spontanée",
        "Nous avons bien reçu votre candidature au poste de Technicien systèmes et réseaux (F/H).",
    ),
    (
        "Application received",
        "Job title: Senior Backend Developer",
    ),
    (
        "Votre candidature",
        "Vous avez postulé au poste de Administrateur Systèmes et Réseaux.",
    ),
]


print()
print("=" * 90)
print("TEST ENTREPRISES")
print("=" * 90)

for company in company_samples:
    normalized = normalize_company_name(company)
    key = company_key(company)

    print(
        f"{company:<45}"
        f" → {normalized:<25}"
        f" → {key}"
    )


print()
print("=" * 90)
print("TEST POSTES")
print("=" * 90)

for subject, body in job_samples:
    job_title = extract_job_title(
        subject,
        body,
    )

    print(f"Sujet : {subject}")
    print(f"Poste : {job_title or '-'}")
    print("-" * 90)