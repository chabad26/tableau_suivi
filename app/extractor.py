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


def looks_like_person_name(text: str) -> bool:
    text = clean_text(text)

    if not text:
        return False

    words = text.split()

    if not 2 <= len(words) <= 4:
        return False

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

    normalized_words = {word.casefold() for word in words}

    if normalized_words & business_words:
        return False

    return all(word[0].isalpha() for word in words if word)


def normalize_company_name(company: str) -> str:
    company = clean_text(company)

    if not company:
        return "Entreprise inconnue"

    company = re.sub(r"^(?:re|fw|fwd)\s*:\s*", "", company, flags=re.IGNORECASE).strip()

    for pattern in COMPANY_PREFIX_PATTERNS:
        company = re.sub(pattern, "", company, flags=re.IGNORECASE).strip()

    for pattern in COMPANY_SUFFIX_PATTERNS:
        company = re.sub(pattern, "", company, flags=re.IGNORECASE).strip()

    if " - " in company:
        left, right = company.rsplit(" - ", 1)

        if looks_like_person_name(left):
            company = right.strip()

    company = re.sub(r"\s+", " ", company).strip(" -–—")

    return company


def company_key(company: str) -> str:
    company = normalize_company_name(company)

    company = normalize(company)

    company = re.sub(r"[^a-z0-9]", "", company)

    return company


def extract_source(sender: str) -> str:
    sender_lower = sender.casefold()

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
        match = re.search(pattern, subject, flags=re.IGNORECASE)

        if match:
            return clean_text(match.group(1))

    match = re.match(
        r"^(.+?)\s*[-–]\s*merci pour votre candidature", subject, flags=re.IGNORECASE
    )

    if match:
        return clean_text(match.group(1))

    match = re.match(
        r"^(.+?)\s*[-–]\s*(?:invitation|entretien|convocation)",
        subject,
        flags=re.IGNORECASE,
    )

    if match:
        return clean_text(match.group(1))

    match = re.match(r"^(.+?)\.jobs\s*[-–]", subject, flags=re.IGNORECASE)

    if match:
        return clean_text(match.group(1))

    display_name, email_address = parseaddr(sender)

    if display_name:
        company = clean_text(display_name)

        if company:
            return company

    if "@" in email_address:
        domain = email_address.split("@", 1)[1]

        domain = domain.split(".")[0]

        return domain.capitalize()

    return "Entreprise inconnue"


def normalize_job_title_for_scoring(title: str) -> str:
    title = normalize(title)

    # Normalisation de quelques écritures inclusives
    title = re.sub(
        r"([a-z]+)·(?:e|se|te|ne|re|le|ve)\b", r"\1", title, flags=re.IGNORECASE
    )

    title = re.sub(
        r"([a-z]+)\.(?:e|se|te|ne|re|le|ve)\b", r"\1", title, flags=re.IGNORECASE
    )

    title = re.sub(
        r"([a-z]+)-(?:e|se|te|ne|re|le|ve)\b", r"\1", title, flags=re.IGNORECASE
    )

    return title


def clean_job_title(title: str) -> str:
    title = clean_text(title)

    prefixes = [
        r"^l['’]offre\s+",
        r"^le poste\s+",
        r"^poste\s+",
        r"^pour le poste\s+",
        r"^pour l['’]offre\s+",
        r"^candidature pour\s+",
        r"^candidature au poste de\s+",
        r"^merci d['’]avoir postulé pour le poste\s+",
        r"^merci d'avoir postule pour le poste\s+",
        r"^.+?\s+merci d['’]avoir postulé pour le poste\s+",
        r"^.+?\s+merci d'avoir postule pour le poste\s+",
    ]

    cut_patterns = [
        r"\s+et vous contact",
        r"\s+et nous",
        r"\s+nous vous",
        r"\s+merci de",
        r"\s+pour rejoindre",
    ]

    for pattern in cut_patterns:
        title = re.split(pattern, title, maxsplit=1, flags=re.IGNORECASE)[0].strip()

    for pattern in prefixes:
        title = re.sub(pattern, "", title, flags=re.IGNORECASE).strip()

    title = title.strip(" :-–—|.,")

    if len(title) < 4:
        return ""

    if len(title) > 140:
        return ""

    bad_titles = {
        "cette fois",
        "merci",
        "bonjour",
        "votre candidature",
        "candidature",
        "le poste",
        "l'offre",
        "offre",
    }

    if title.casefold() in bad_titles:
        return ""

    # Nettoyage HTML résiduel
    title = re.sub(r"<[^>]+>", " ", title)

    title = re.sub(r"\s+", " ", title).strip()

    return title


def job_title_score(title: str) -> int:
    title = clean_job_title(title)

    if not title:
        return 0

    score = 1

    words = title.split()

    if 2 <= len(words) <= 12:
        score += 2

    useful_words = {
        "développeur",
        "developpeur",
        "developer",
        "administrateur",
        "administrator",
        "ingénieur",
        "ingenieur",
        "engineer",
        "technicien",
        "technician",
        "devops",
        "cybersécurité",
        "cybersecurity",
        "fullstack",
        "backend",
        "frontend",
        "lead",
        "architecte",
        "architect",
        "système",
        "systeme",
        "system",
        "réseau",
        "reseau",
        "network",
    }

    normalized_title = normalize_job_title_for_scoring(title)

    normalized_words = {word.strip("()/-") for word in normalized_title.split()}

    if normalized_words & useful_words:
        score += 3

    return score


def extract_job_title(subject: str, body: str = "") -> str:
    subject = clean_text(subject)

    body = clean_text(body)

    subject_patterns = [
        r"votre candidature\s*:\s*(.+)$",
        (
            r"candidature au poste de\s+(.+?)"
            r"(?:\s+n['’]est pas retenue"
            r"|\s+n['’]a pas été retenue|$)"
        ),
        r"merci de votre candidature pour être\s+(.+)$",
        r"confirmation de votre candidature\s+(.+)$",
        (
            r"candidature pour l['’]offre\s+(.+?)"
            r"(?:\s+référence|\s+reference|$)"
        ),
        r"entretien téléphonique\s*[-–—]\s*(.+)$",
        r"entretien telephonique\s*[-–—]\s*(.+)$",
        r"entretien technique\s*[-–—]\s*(.+)$",
        # English
        r"application for\s+(.+)$",
        r"your application for\s+(.+)$",
        r"interview\s*[-–—]\s*(.+)$",
        r"application received\s*[-–—]\s*(.+)$",
    ]

    for pattern in subject_patterns:
        match = re.search(pattern, subject, flags=re.IGNORECASE)

        if match:
            title = clean_job_title(match.group(1))

            if title:
                return title

    body_patterns = [
        r"intitulé du poste\s*:\s*(.{3,120}?)(?:\.|\||référence|reference|$)",
        r"intitule du poste\s*:\s*(.{3,120}?)(?:\.|\||reference|$)",
        r"poste\s*:\s*(.{3,120}?)(?:\.|\||référence|reference|$)",
        r"poste de\s+(.{3,120}?)(?:\.|,|référence|reference|$)",
        (
            r"candidature au poste de\s+(.{3,120}?)"
            r"(?:\.|,|référence|reference|$)"
        ),
        (
            r"vous avez postulé(?:e)? "
            r"(?:au poste de|à l['’]offre)\s+"
            r"(.{3,120}?)(?:\.|,|référence|reference|$)"
        ),
        (
            r"votre candidature pour\s+(.{3,120}?)"
            r"(?:\.|,|référence|reference|$)"
        ),
        # English
        r"job title\s*:\s*(.{3,120}?)(?:\.|\||reference|$)",
        r"position\s*:\s*(.{3,120}?)(?:\.|\||reference|$)",
        r"role\s*:\s*(.{3,120}?)(?:\.|\||reference|$)",
        r"you applied for\s+(.{3,120}?)(?:\.|,|reference|$)",
        r"your application for\s+(.{3,120}?)(?:\.|,|reference|$)",
        (
            r"application for the position of\s+"
            r"(.{3,120}?)(?:\.|,|reference|$)"
        ),
    ]

    for pattern in body_patterns:
        match = re.search(pattern, body, flags=re.IGNORECASE)

        if match:
            title = clean_job_title(match.group(1))

            if title:
                return title

    return ""


def extract_application_data(
    subject: str, sender: str, body: str = ""
) -> tuple[str, str, str]:
    company = extract_company(subject, sender)

    company = normalize_company_name(company)

    job_title = extract_job_title(subject, body)

    source = extract_source(sender)

    return (company, job_title, source)
