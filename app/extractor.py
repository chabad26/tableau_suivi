import re
from email.utils import parseaddr
from app.classifier import normalize

COMPANY_PREFIX_PATTERNS = [
    r"^équipe de recrutement de\s+",
    r"^equipe de recrutement de\s+",

    r"^équipe rh de\s+",
    r"^equipe rh de\s+",

    r"^service recrutement de\s+",
    r"^service recrutement\s+",

    r"^recrutement\s+",

    r"^talent acquisition\s+",
    r"^human resources\s+",
    r"^hr\s+",
]


COMPANY_SUFFIX_PATTERNS = [
    r"\s+-\s+service recrutement$",
    r"\s+-\s+recrutement$",
    r"\s+talent acquisition$",
    r"\s+human resources$",
    r"\s+rh$",
    r"\s+!$",
]


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

def looks_like_person_name(
    text: str,
) -> bool:
    text = clean_text(text)

    if not text:
        return False

    words = text.split()

    if not 2 <= len(words) <= 4:
        return False

    #
    # On évite de considérer certains mots métier
    # comme des noms de personne.
    #
    business_words = {
        "recrutement",
        "recruitment",
        "team",
        "équipe",
        "equipe",
        "service",
        "rh",
        "hr",
        "talent",
        "resources",
        "human",
    }

    normalized_words = {
        word.casefold()
        for word in words
    }

    if normalized_words & business_words:
        return False

    return all(
        word[0].isalpha()
        for word in words
        if word
    )

def normalize_company_name(
    company: str,
) -> str:
    company = clean_text(company)

    if not company:
        return "Entreprise inconnue"

    #
    # Préfixes techniques de mail
    #
    company = re.sub(
        r"^(?:re|fw|fwd)\s*:\s*",
        "",
        company,
        flags=re.IGNORECASE,
    ).strip()

    #
    # Préfixes génériques RH/recrutement
    #
    for pattern in COMPANY_PREFIX_PATTERNS:
        company = re.sub(
            pattern,
            "",
            company,
            flags=re.IGNORECASE,
        ).strip()

    #
    # Suffixes génériques
    #
    for pattern in COMPANY_SUFFIX_PATTERNS:
        company = re.sub(
            pattern,
            "",
            company,
            flags=re.IGNORECASE,
        ).strip()

    #
    # Cas :
    # "Prénom Nom - Entreprise"
    #
    if " - " in company:
        left, right = company.rsplit(
            " - ",
            1,
        )

        if looks_like_person_name(left):
            company = right.strip()

    #
    # Nettoyage final
    #
    company = re.sub(
        r"\s+",
        " ",
        company,
    ).strip(" -–—")

    return company

def company_key(
    company: str,
) -> str:
    company = normalize_company_name(
        company
    )

    company = normalize(
        company
    )

    company = re.sub(
        r"[^a-z0-9]",
        "",
        company,
    )

    return company

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

