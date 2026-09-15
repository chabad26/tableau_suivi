from __future__ import annotations


JOB_KEYWORDS = {
    "candidature",
    "application",
    "recrutement",
    "recruitment",
    "poste",
    "job",
    "emploi",
    "entretien",
    "interview",
    "candidate",
    "hiring",
    "talent acquisition",
    "offre d'emploi",
    "job offer",
    "application received",
    "your application",
    "merci pour votre candidature",
}


NOISE_KEYWORDS = {
    "relevé de compte",
    "releve de compte",
    "carte bancaire",
    "virement",
    "prélèvement",
    "prelevement",
    "solde",
    "facture",
    "commande",
    "livraison",
    "code de sécurité",
    "code de securite",
    "newsletter",
}


def build_search_text(
    sender: str,
    subject: str,
    body: str,
) -> str:
    return " ".join(
        [
            sender or "",
            subject or "",
            body or "",
        ]
    ).casefold()


def looks_job_related(
    sender: str,
    subject: str,
    body: str,
) -> bool:
    text = build_search_text(
        sender,
        subject,
        body,
    )

    return any(
        keyword in text
        for keyword in JOB_KEYWORDS
    )


def is_obvious_noise(
    sender: str,
    subject: str,
    body: str,
) -> bool:
    text = build_search_text(
        sender,
        subject,
        body,
    )

    return any(
        keyword in text
        for keyword in NOISE_KEYWORDS
    )


def should_analyze_email(
    sender: str,
    subject: str,
    body: str,
) -> bool:
    """
    Retourne True si le message semble suffisamment
    lié à une candidature pour passer dans le moteur.
    """

    if is_obvious_noise(
        sender,
        subject,
        body,
    ):
        return False

    return looks_job_related(
        sender,
        subject,
        body,
    )