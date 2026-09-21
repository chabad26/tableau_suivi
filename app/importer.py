from dataclasses import dataclass, field
from app.connectors.registry import scan_external_connectors
from app.database import (
    email_exists,
    get_or_create_application,
    save_email,
    update_application,
)
from app.extractor import extract_application_data
from app.models import DetectedEmail
from app.settings import API_START_DATE

START_DATE = API_START_DATE

@dataclass
class ImportResult:
    detected: int
    added: int
    processed: int
    unavailable_sources: list[str] = field(default_factory=list)


def deduplicate_emails(emails: list[DetectedEmail]) -> list[DetectedEmail]:

    unique: dict[str, DetectedEmail] = {}

    for email in emails:
        key = email.message_id.strip()

        if not key:
            continue

        #
        # Premier connecteur gagnant.
        #
        # Ça évite qu'un même mail vu par
        # plusieurs connecteurs soit traité
        # plusieurs fois pendant la même passe.
        #
        if key not in unique:
            unique[key] = email

    return list(unique.values())


def import_emails() -> ImportResult:

    detected_emails: list[DetectedEmail] = []


    # 1. APIs / connecteurs externes
    #
    errors: list[str] = []
    detected_emails.extend(scan_external_connectors(START_DATE, errors=errors))

    #
    # 2. Déduplication inter-connecteurs
    #
    detected_emails = deduplicate_emails(detected_emails)

    added = 0
    processed = 0

    for email in detected_emails:
        if email_exists(email.message_id):
            continue

        company, job_title, source = extract_application_data(
            email.subject, email.sender, email.body
        )

        application_id = get_or_create_application(
            company=company,
            job_title=job_title,
            source=source,
            date=email.date,
            status=email.status,
        )

        inserted = save_email(email, application_id=application_id)

        if not inserted:
            continue

        update_application(
            application_id=application_id,
            status=email.status,
            date=email.date,
            job_title=job_title,
        )

        added += 1
        processed += 1

    return ImportResult(
        detected=len(detected_emails),
        added=added,
        processed=processed,
        unavailable_sources=errors,
    )
