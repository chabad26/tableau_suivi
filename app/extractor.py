import re
from email.utils import parseaddr


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_source(sender: str) -> str:
    sender_lower = sender.lower()

    if "hellowork" in sender_lower:
        return "Hellowork"

    if "linkedin" in sender_lower:
        return "LinkedIn"

    if "indeed" in sender_lower:
        return "Indeed"

    if "malt" in sender_lower:
        return "Malt"

    if "free-work" in sender_lower:
        return "Free-Work"

    if "teamtailor" in sender_lower:
        return "Teamtailor"

    if "beetween" in sender_lower:
        return "Beetween"

    if "recruitee" in sender_lower:
        return "Recruitee"

    if "icims" in sender_lower:
        return "iCIMS"

    if "digitalrecruiters" in sender_lower:
        return "DigitalRecruiters"

    return "Direct"

def extract_company(subject: str, sender: str) -> str:
    subject = clean_text(subject)

    patterns = [
        r"candidature est arrivée chez (.+)$",
        r"candidature est arrivee chez (.+)$",
        r"réception de votre candidature chez (.+)$",
        r"reception de votre candidature chez (.+)$",
        r"candidature a été envoyée à (.+)$",
        r"candidature a ete envoyee a (.+)$",
        r"merci pour votre candidature chez (.+)$",
        r"merci d'avoir envoyé votre candidature chez (.+)$",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            subject,
            flags=re.IGNORECASE
        )

        if match:
            return clean_text(match.group(1))

    # Exemple :
    # "Volvo Group - Merci pour votre candidature!"
    match = re.match(
        r"^(.+?)\s*[-–]\s*merci pour votre candidature",
        subject,
        flags=re.IGNORECASE
    )

    if match:
        return clean_text(match.group(1))

    # Exemple :
    # "Arturia - Invitation à un entretien téléphonique - Développeur IT"
    match = re.match(
        r"^(.+?)\s*[-–]\s*(?:invitation|entretien|convocation)",
        subject,
        flags=re.IGNORECASE
    )

    if match:
        return clean_text(match.group(1))

    # Exemple :
    # "Orange.jobs - merci pour votre candidature"
    match = re.match(
        r"^(.+?)\.jobs\s*[-–]",
        subject,
        flags=re.IGNORECASE
    )

    if match:
        return clean_text(match.group(1))

    # Fallback : nom affiché de l'expéditeur
    display_name, email_address = parseaddr(sender)

    if display_name:
        company = clean_text(display_name)

        suffixes = [
            " - Service recrutement",
            " Talent Acquisition",
            " Candidature",
            " RH",
            " Recrutement",
        ]

        for suffix in suffixes:
            if company.endswith(suffix):
                company = company.removesuffix(suffix)

        if company:
            return company

    # Dernier recours : domaine
    if "@" in email_address:
        domain = email_address.split("@", 1)[1]
        domain = domain.split(".")[0]

        return domain.capitalize()

    return "Entreprise inconnue"

def extract_job_title(subject: str) -> str:
    subject = clean_text(subject)

    patterns = [
        r"Votre candidature\s*:\s*(.+)$",
        r"candidature au poste de (.+?)(?: n'est pas retenue| n’est pas retenue|$)",
        r"Merci de votre candidature pour être (.+)$",
        r"Confirmation de votre candidature\s+(.+)$",
        r"candidature pour l'offre (.+?)(?: référence|$)",
        r"candidature pour l’offre (.+?)(?: référence|$)",
        r"entretien téléphonique\s*[-–]\s*(.+)$",
        r"entretien telephonique\s*[-–]\s*(.+)$",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            subject,
            flags=re.IGNORECASE
        )

        if match:
            return clean_text(match.group(1))

    return ""


def extract_application_data(
    subject: str,
    sender: str
) -> tuple[str, str, str]:

    company = extract_company(
        subject,
        sender
    )

    company = normalize_company_name(
        company
    )

    job_title = extract_job_title(
        subject
    )

    source = extract_source(
        sender
    )

    return company, job_title, source

def normalize_company_name(company: str) -> str:
    company = clean_text(company)

    # Nettoyage des préfixes de réponse
    prefixes = [
        "re: ",
        "fw: ",
        "fwd: ",
    ]

    lowered = company.lower()

    for prefix in prefixes:
        if lowered.startswith(prefix):
            company = company[len(prefix):].strip()
            lowered = company.lower()

    # Nettoyage de quelques suffixes/bruits fréquents
    suffixes = [
        " - Service recrutement",
        " - service recrutement",
        " Talent Acquisition",
        " Candidature",
        " Recrutement",
        " RH",
        " !",
    ]

    for suffix in suffixes:
        if company.endswith(suffix):
            company = company.removesuffix(suffix).strip()

    # Cas "Prénom Nom - Entreprise"
    if " - " in company:
        _, right = company.rsplit(" - ", 1)

        # Si la partie droite ressemble plus à une entreprise
        # que la partie gauche, on garde la droite
        if len(right) >= 3 and not right.lower().startswith(
            ("service", "recrutement", "rh")
        ):
            company = right.strip()

    # Cas spécifiques de noms techniques
    replacements = {
        "ak-recrutement": "AK Recrutement",
        "orange.jobs": "Orange",
        "cea": "CEA",
        "hellowork": "HelloWork",
        "free-work": "Free-Work",
    }

    key = company.lower()

    if key in replacements:
        return replacements[key]

    # Capitalisation conservée au mieux
    return company
