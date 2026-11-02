"""Réanalyse atomique des emails archivés d'un seul utilisateur, sans réseau."""

from datetime import datetime, timezone

from app.classifier import detect_status
from app.database import get_connection
from app.extractor import clean_job_title, extract_application_data, job_title_score
from app.owned_applications import require_user_id
from app.reclassifier import ReclassifyResult


def _message_date(value: str) -> datetime | None:
    try:
        date = datetime.fromisoformat(value)
    except ValueError:
        return None
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return date.astimezone(timezone.utc)


def reclassify_user_emails(user_id: int) -> ReclassifyResult:
    """Recalcule les analyses sans réimport, suppression, fusion ni accès IMAP."""
    user_id = require_user_id(user_id)
    found = changed = missing = 0
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        if (
            connection.execute(
                "SELECT 1 FROM users WHERE id=? AND active=1", (user_id,)
            ).fetchone()
            is None
        ):
            raise ValueError("Utilisateur inexistant ou désactivé.")

        rows = connection.execute(
            "SELECT id, application_id, subject, sender, body, detected_status, received_at FROM emails WHERE user_id=? ORDER BY id",
            (user_id,),
        ).fetchall()
        originals = {
            int(row["id"]): dict(row)
            for row in connection.execute(
                "SELECT * FROM applications WHERE user_id=?", (user_id,)
            ).fetchall()
        }
        candidates = {key: dict(value) for key, value in originals.items()}
        # Les dates ISO peuvent contenir des décalages horaires différents.
        ordered = sorted(
            rows,
            key=lambda row: (
                _message_date(str(row["received_at"]))
                or datetime.min.replace(tzinfo=timezone.utc),
                int(row["id"]),
            ),
        )
        for row in ordered:
            body = str(row["body"] or "")
            status = str(row["detected_status"])
            candidate = candidates.get(row["application_id"])
            if not body.strip():
                missing += 1
            else:
                found += 1
                status = detect_status(str(row["subject"] or ""), body)
                if status != str(row["detected_status"]):
                    connection.execute(
                        "UPDATE emails SET detected_status=? WHERE id=? AND user_id=?",
                        (status, row["id"], user_id),
                    )
                    changed += 1
                if candidate is not None and not candidate["manual_override"]:
                    company, title, source = extract_application_data(
                        str(row["subject"] or ""), str(row["sender"] or ""), body
                    )
                    candidate["company"] = company.strip() or candidate["company"]
                    candidate["source"] = source.strip() or candidate["source"]
                    current_title = clean_job_title(str(candidate["job_title"] or ""))
                    new_title = clean_job_title(title)
                    candidate["job_title"] = (
                        new_title or current_title
                        if job_title_score(new_title) >= job_title_score(current_title)
                        else current_title
                    )

            date = _message_date(str(row["received_at"]))
            if candidate is not None and date is not None:
                candidate["current_status"] = status
                candidate["last_update"] = date.isoformat()

        updated = 0
        fields = ("company", "job_title", "source", "current_status", "last_update")
        for application_id, candidate in candidates.items():
            values = tuple(candidate[key] for key in fields)
            if values == tuple(originals[application_id][key] for key in fields):
                continue
            connection.execute(
                "UPDATE applications SET company=?, job_title=?, source=?, current_status=?, last_update=? WHERE id=? AND user_id=?",
                (*values, application_id, user_id),
            )
            updated += 1

    return ReclassifyResult(
        scanned=len(rows),
        found=found,
        changed=changed,
        applications_updated=updated,
        missing=missing,
    )
