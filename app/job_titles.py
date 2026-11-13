"""Indices de poste tirés d'une offre enregistrée ou des emails liés, sans réseau."""

import html
import re
from collections.abc import Iterable
from dataclasses import dataclass

from app.connectors.common import html_to_text
from app.extractor import (
    clean_job_title,
    company_key,
    extract_job_title,
    job_title_score,
)


@dataclass(frozen=True)
class JobTitleSuggestion:
    title: str
    source: str


def _candidate(value: str, company: str = "") -> str:
    value = re.split(
        r"\s+(?:missions|lieu|ville|contrat|salaire|référence|reference)\s*:",
        value,
        maxsplit=1,
        flags=re.I,
    )[0]
    title = clean_job_title(value.strip(' "«»“”'))
    if company and title and company_key(title) == company_key(company):
        return ""
    if title.casefold() in {
        "non renseigné",
        "non précisé",
        "à définir",
        "à pourvoir",
        "h/f",
        "f/h",
        "cdi",
        "cdd",
        "stage",
        "alternance",
        "description du poste",
        "job description",
        "reçue",
        "envoyée",
        "enregistrée",
        "bien reçue",
        "candidature reçue",
    } or re.search(
        r"https?://|www\.|@|\b(?:nous|vous|notre|nos|votre|vos|je)\b", title, re.I
    ):
        return ""
    return title


def _role_heading(title: str) -> bool:
    return bool(
        re.search(
            r"\b(?:analyst(?:e)?|d[ée]veloppe(?:ur|use)|administrat(?:eur|rice)|ing[ée]nieur(?:e)?|technicien(?:ne)?|consultant(?:e)?|auditeur|auditrice|responsable|charg[ée](?:e)?|chef(?:fe)?|gestionnaire|juriste|comptable|commercial(?:e)?|manager|direct(?:eur|rice)|architect(?:e)?|developer|administrator|engineer|technician|auditor)\b",
            title,
            re.I,
        )
    )


def extract_offer_job_title(offer_text: str, *, company: str = "") -> str:
    """Privilégie un libellé explicite ; refuse les libellés contradictoires."""
    text = offer_text
    if re.search(r"<(?:html|body|div|p\b|h[1-6]\b|table|li\b)", text, re.I):
        text = re.sub(r"</(?:h[1-6]|div|p|li|tr)\s*>", "\n", text, flags=re.I)
        text = html_to_text(text)
    text = html.unescape(text)
    text = re.sub(r"[\u200b\ufeff]", "", text)
    text = re.split(
        r"(?im)^\s*(?:offres similaires|autres offres|recommandations|vous aimerez aussi|découvrez nos autres offres)\b",
        text,
        maxsplit=1,
    )[0]
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    explicit = []
    for line in lines:
        match = re.match(
            r"^(?:intitul[ée](?: du poste)?|poste(?: proposé)?|titre(?: du poste)?|fonction|job title|position)\s*:\s*(.+)$",
            line,
            re.I,
        )
        if match:
            title = _candidate(match.group(1), company)
            if title:
                explicit.append(title)
    if explicit:
        return explicit[0] if len({title.casefold() for title in explicit}) == 1 else ""
    # Une ligne isolée en tête d'offre est un indice ; une compétence dans le
    # corps de l'annonce ne suffit pas à inventer un poste.
    for line in lines[:6]:
        if re.match(
            r"^(?:missions|profil|compétences|description|à propos)\b", line, re.I
        ):
            break
        title = _candidate(line, company)
        if title and _role_heading(title):
            return title
    for line in lines:
        match = re.search(
            r"nous recherchons\s+(?:un[e]?|un\(e\))\s+(.+?)(?:\s+(?:pour|afin de|au sein de|chez)\b|[.!;]|$)",
            line,
            re.I,
        )
        if match:
            title = _candidate(match.group(1), company)
            if title and _role_heading(title):
                return title
    return ""


def suggest_job_title(
    offer_text: str, emails: Iterable[tuple[str, str]] = (), *, company: str = ""
) -> JobTitleSuggestion | None:
    title = extract_offer_job_title(offer_text, company=company)
    if title:
        return JobTitleSuggestion(title, "offer")
    best = ""
    for subject, body in emails:
        candidate = _candidate(extract_job_title(subject, body), company)
        if candidate and job_title_score(candidate) > job_title_score(best):
            best = candidate
    return JobTitleSuggestion(best, "email") if best else None
