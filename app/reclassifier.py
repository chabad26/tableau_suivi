from datetime import datetime
import mailbox
from app.classifier import (
    decode_text,
    detect_status,
    score_message,
)
from app.database import get_connection
from app.scanner import MAILBOXES
from dataclasses import dataclass

@dataclass
class ReclassifyResult:
    scanned: int
    found: int
    changed: int
    applications_updated: int
    missing: int

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

    return {
        str(row["message_id"])
        for row in rows
    }


def update_email_status(
    message_id: str,
    status: str,
) -> bool:
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
            (
                status,
                message_id,
            ),
        )

        connection.commit()

    print(
        f"  🔄 {old_status:<10} → {status:<10} "
        f"{message_id[:40]}"
    )

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
                    email_date = datetime.fromisoformat(
                        str(email["received_at"])
                    )
                except ValueError:
                    continue

                if (
                    latest_date is None
                    or email_date > latest_date
                ):
                    latest_date = email_date
                    latest_status = str(
                        email["detected_status"]
                    )

            if (
                latest_status is None
                or latest_date is None
            ):
                continue

            old_status = str(
                application["current_status"]
            )

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
                (
                    latest_status,
                    latest_date.isoformat(),
                    application_id,
                ),
            )

            updated += 1

        connection.commit()

    return updated


def reclassify_emails() -> ReclassifyResult:
    """
    Recherche les emails connus dans les boîtes Thunderbird
    et leur applique les règles actuelles de detect_status().
    """

    known_message_ids = get_known_message_ids()

    print()
    print("=" * 80)
    print("RECLASSIFICATION DES EMAILS")
    print("=" * 80)
    print(
        f"Emails connus dans SQLite : "
        f"{len(known_message_ids)}"
    )

    if not known_message_ids:
        print("Aucun email à reclassifier.")
        return ReclassifyResult(
            scanned=0,
            found=0,
            changed=0,
            applications_updated=0,
            missing=0,
        )

    found_ids: set[str] = set()

    scanned = 0
    found = 0
    changed = 0

    for mailbox_name, path in MAILBOXES.items():

        print()
        print(f"📬 {mailbox_name}")

        if not path.exists():
            print(
                f"  ⚠ Boîte introuvable : {path}"
            )
            continue

        mbox = mailbox.mbox(
            str(path),
            create=False,
        )

        mailbox_scanned = 0
        mailbox_found = 0
        mailbox_changed = 0

        for message in mbox:
            scanned += 1
            mailbox_scanned += 1

            message_id = decode_text(
                message.get("Message-ID")
            )

            if not message_id:
                continue

            if message_id not in known_message_ids:
                continue

            found_ids.add(message_id)

            found += 1
            mailbox_found += 1

            subject = decode_text(
                message.get("Subject")
            )

            # score_message nous restitue déjà
            # le corps extrait du mail.
            _, _, body = score_message(
                message
            )

            new_status = detect_status(
                subject,
                body,
            )

            if update_email_status(
                message_id,
                new_status,
            ):
                changed += 1
                mailbox_changed += 1

        print(
            f"  Parcourus     : {mailbox_scanned}"
        )
        print(
            f"  Emails connus : {mailbox_found}"
        )
        print(
            f"  Modifiés      : {mailbox_changed}"
        )

    missing = known_message_ids - found_ids

    print()
    print("♻ Recalcul des candidatures...")

    applications_updated = (
        recompute_application_statuses()
    )

    print()
    print("=" * 80)
    print("RECLASSIFICATION TERMINÉE")
    print("=" * 80)
    print(f"Messages parcourus       : {scanned}")
    print(f"Messages retrouvés       : {found}")
    print(f"Emails reclassifiés      : {changed}")
    print(
        f"Candidatures mises à jour: "
        f"{applications_updated}"
    )
    print(
        f"Messages non retrouvés   : "
        f"{len(missing)}"
    )

    return ReclassifyResult(
        scanned=scanned,
        found=found,
        changed=changed,
        applications_updated=applications_updated,
        missing=len(missing),
    )
