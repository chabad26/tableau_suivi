import mailbox
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone

from app.classifier import decode_text, detect_status, score_message
from app.database import get_connection, update_application_from_analysis
from app.extractor import extract_application_data
from app.scanner import MAILBOXES


@dataclass
class ReclassifyResult:
    scanned: int
    found: int
    changed: int
    applications_updated: int
    missing: int


def reanalyse_email(
    message_id: str, subject: str, sender: str, body: str
) -> tuple[bool, bool, int | None]:
    """
    Recalcule statut + entreprise + poste + source pour un email connu.
    Retourne :
    - True si le statut email a changé
    - True si les détails de la candidature ont changé
    - application_id lié au mail
    """

    new_status = detect_status(subject, body)

    company, job_title, source = extract_application_data(subject, sender, body)

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                application_id,
                detected_status
            FROM emails
            WHERE message_id = ?
            """,
            (message_id,),
        ).fetchone()

        if row is None:
            return False, False, None

        application_id = row["application_id"]

        changed = str(row["detected_status"]) != new_status

        if changed or body:
            connection.execute(
                """
                UPDATE emails
                SET 
                    detected_status = ?,
                    body = ?
                WHERE message_id = ?
                """,
                (new_status, body, message_id),
            )

        connection.commit()

    details_changed = False
    if application_id is not None:
        details_changed = update_application_from_analysis(
            application_id=int(application_id),
            company=company,
            job_title=job_title,
            source=source,
        )

    return (
        changed,
        details_changed,
        int(application_id) if application_id is not None else None,
    )


def get_known_message_ids() -> set[str]:
    """
    Récupère les Message-ID déjà enregistrés dans SQLite.
    """

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT message_id
            FROM emails
            WHERE message_id IS NOT NULL
              AND message_id != ''
            """
        ).fetchall()

    return {str(row["message_id"]) for row in rows}


def update_email_status(message_id: str, status: str) -> bool:
    """
    Met à jour le statut détecté d'un email.

    Retourne True si le statut a réellement changé.
    """

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT detected_status
            FROM emails
            WHERE message_id = ?
            """,
            (message_id,),
        ).fetchone()

        if row is None:
            return False

        old_status = str(row["detected_status"])

        if old_status == status:
            return False

        connection.execute(
            """
            UPDATE emails
            SET detected_status = ?
            WHERE message_id = ?
            """,
            (status, message_id),
        )

        connection.commit()

    print(f"  🔄 {old_status:<10} → {status:<10} {message_id[:40]}")

    return True


def recompute_application_statuses() -> int:
    """
    Recalcule le statut automatique de chaque candidature à partir
    de son email associé le plus récent.

    Les overrides manuels ne sont pas supprimés.
    """

    updated = 0

    with get_connection() as connection:
        applications = connection.execute(
            """
            SELECT id, current_status
            FROM applications
            """
        ).fetchall()

        for application in applications:
            application_id = int(application["id"])

            emails = connection.execute(
                """
                SELECT
                    detected_status,
                    received_at
                FROM emails
                WHERE application_id = ?
                """,
                (application_id,),
            ).fetchall()

            if not emails:
                # Candidature créée manuellement.
                continue

            latest_status: str | None = None
            latest_date: datetime | None = None

            for email in emails:
                try:
                    email_date = datetime.fromisoformat(str(email["received_at"]))
                    if email_date.tzinfo is None:
                        email_date = email_date.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue

                if latest_date is None or email_date > latest_date:
                    latest_date = email_date
                    latest_status = str(email["detected_status"])

            if latest_status is None or latest_date is None:
                continue

            old_status = str(application["current_status"])

            if old_status == latest_status:
                continue

            connection.execute(
                """
                UPDATE applications
                SET
                    current_status = ?,
                    last_update = ?
                WHERE id = ?
                """,
                (latest_status, latest_date.isoformat(), application_id),
            )

            updated += 1

        connection.commit()

    return updated


def reclassify_mailboxes() -> ReclassifyResult:
    """
    Recherche les emails connus dans les boîtes Thunderbird
    et leur applique les règles actuelles de detect_status().
    """

    known_message_ids = get_known_message_ids()

    print()
    print("=" * 80)
    print("RECLASSIFICATION DES EMAILS")
    print("=" * 80)
    print(f"Emails connus dans SQLite : {len(known_message_ids)}")

    if not known_message_ids:
        print("Aucun email à reclassifier.")
        return ReclassifyResult(
            scanned=0, found=0, changed=0, applications_updated=0, missing=0
        )

    found_ids: set[str] = set()

    scanned = 0
    found = 0
    changed = 0
    details_changed = 0

    for mailbox_name, path in MAILBOXES.items():
        print()
        print(f"📬 {mailbox_name}")

        if not path.exists():
            print(f"  ⚠ Boîte introuvable : {path}")
            continue

        mbox = mailbox.mbox(str(path), create=False)

        mailbox_scanned = 0
        mailbox_found = 0
        mailbox_changed = 0

        with closing(mbox):
            for message in mbox:
                scanned += 1
                mailbox_scanned += 1

                message_id = decode_text(message.get("Message-ID"))

                if not message_id:
                    continue

                if message_id not in known_message_ids:
                    continue

                found_ids.add(message_id)

                found += 1
                mailbox_found += 1

                subject = decode_text(message.get("Subject"))

                # score_message nous restitue déjà
                # le corps extrait du mail.
                _, _, body = score_message(message)

                sender = decode_text(message.get("From"))

                email_changed, application_changed, __ = reanalyse_email(
                    message_id=message_id, subject=subject, sender=sender, body=body
                )

                if email_changed:
                    changed += 1
                    mailbox_changed += 1

                if application_changed:
                    details_changed += 1

        print(f"  Parcourus     : {mailbox_scanned}")
        print(f"  Emails connus : {mailbox_found}")
        print(f"  Modifiés      : {mailbox_changed}")
        print(f"Candidatures enrichies   : {details_changed}")

    missing = known_message_ids - found_ids

    print()
    print("♻ Recalcul des candidatures...")

    applications_updated = recompute_application_statuses()

    print()
    print("=" * 80)
    print("RECLASSIFICATION TERMINÉE")
    print("=" * 80)
    print(f"Messages parcourus       : {scanned}")
    print(f"Messages retrouvés       : {found}")
    print(f"Emails reclassifiés      : {changed}")
    print(f"Candidatures mises à jour: {applications_updated}")
    print(f"Messages non retrouvés   : {len(missing)}")

    return ReclassifyResult(
        scanned=scanned,
        found=found,
        changed=changed,
        applications_updated=applications_updated,
        missing=len(missing),
    )


def reclassify_emails() -> ReclassifyResult:
    """Réanalyse le contenu archivé de toutes les sources, sans OAuth.

    Les anciens messages sans corps sont recherchés dans les mbox en secours.
    Les messages sans contenu récupérable sont comptés comme manquants.
    """
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT message_id, subject, sender, body FROM emails ORDER BY received_at, id"
        ).fetchall()
    pending = {str(row["message_id"]) for row in rows if not row["body"]}
    recovered: dict[str, tuple[str, str, str]] = {}
    if pending:
        for path in MAILBOXES.values():
            if not path.exists():
                continue
            with closing(mailbox.mbox(str(path), create=False)) as messages:
                for message in messages:
                    message_id = decode_text(message.get("Message-ID"))
                    if message_id in pending and message_id not in recovered:
                        _, _, body = score_message(message)
                        if body:
                            recovered[message_id] = (
                                decode_text(message.get("Subject")),
                                decode_text(message.get("From")),
                                body,
                            )
    found = changed = 0
    for row in rows:
        message_id = str(row["message_id"])
        if row["body"]:
            content = (
                str(row["subject"] or ""),
                str(row["sender"] or ""),
                str(row["body"]),
            )
        elif message_id in recovered:
            content = recovered[message_id]
        else:
            continue
        found += 1
        status_changed, _, _ = reanalyse_email(message_id, *content)
        changed += int(status_changed)
    updated = recompute_application_statuses()
    return ReclassifyResult(len(rows), found, changed, updated, len(rows) - found)
