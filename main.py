from app.database import (
    get_or_create_application,
    init_database,
    save_email,
    update_application,
)
from app.extractor import extract_application_data
from app.scanner import scan_all_mailboxes


def main() -> None:
    init_database()

    detected_emails = scan_all_mailboxes()

    created_or_linked = 0
    saved_emails = 0

    for email in detected_emails:

        company, job_title, source = (
            extract_application_data(
                email.subject,
                email.sender,
            )
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
            # Mail déjà connu dans SQLite
            continue

        update_application(
            application_id=application_id,
            status=email.status,
            date=email.date,
            job_title=job_title,
        )

        created_or_linked += 1
        saved_emails += 1

        print(
            f"[{application_id}] "
            f"{company} | "
            f"{job_title or 'Poste inconnu'} | "
            f"{email.status}"
        )

    print()
    print("=" * 80)
    print("IMPORT TERMINÉ")
    print("=" * 80)
    print(f"Mails détectés       : {len(detected_emails)}")
    print(f"Mails ajoutés         : {saved_emails}")
    print(f"Candidatures traitées : {created_or_linked}")


if __name__ == "__main__":
    main()