from dataclasses import dataclass

from app.database import (
    get_or_create_application,
    save_email,
    update_application,
)
from app.extractor import extract_application_data
from app.scanner import scan_all_mailboxes


@dataclass
class ImportResult:
    detected: int
    added: int
    processed: int


def import_emails() -> ImportResult:
    detected_emails = scan_all_mailboxes()

    added = 0
    processed = 0

    for email in detected_emails:
        company, job_title, source = extract_application_data(
            email.subject,
            email.sender,
            email.body,
        )

        application_id = get_or_create_application(
            company=company,
            job_title=job_title,
            source=source,
            status=email.status,
            date=email.date,
        )

        inserted = save_email(
            email=email,
            application_id=application_id,
        )

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
    )