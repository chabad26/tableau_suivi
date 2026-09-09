import re
from dataclasses import dataclass


@dataclass
class DiscordProposal:
    company: str
    job_title: str
    url: str
    raw_message: str


def extract_url(text: str) -> str:
    match = re.search(
        r"https?://[^\s<>]+",
        text,
    )

    if match:
        return match.group(0)

    return ""


def parse_proposal(
    text: str,
) -> DiscordProposal:
    clean = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    company = ""
    job_title = ""

    patterns_company = [
        r"entreprise\s*:\s*([^|]+)",
        r"société\s*:\s*([^|]+)",
        r"societe\s*:\s*([^|]+)",
        r"chez\s+([A-Za-z0-9À-ÿ&'.\- ]+)",
    ]

    for pattern in patterns_company:
        match = re.search(
            pattern,
            clean,
            flags=re.IGNORECASE,
        )

        if match:
            company = match.group(1).strip()
            break

    patterns_job = [
        r"poste\s*:\s*([^|]+)",
        r"alternance\s*:\s*([^|]+)",
        r"recherche\s+(?:un|une)\s+([^|]+)",
    ]

    for pattern in patterns_job:
        match = re.search(
            pattern,
            clean,
            flags=re.IGNORECASE,
        )

        if match:
            job_title = match.group(1).strip()
            break

    url = extract_url(clean)

    if not company:
        company = "Entreprise à préciser"

    if not job_title:
        job_title = "Poste à préciser"

    return DiscordProposal(
        company=company,
        job_title=job_title,
        url=url,
        raw_message=text,
    )