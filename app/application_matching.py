"""Rapprochement de conversations, toujours dans l'espace d'un propriétaire."""

import re
import sqlite3
from datetime import timedelta, timezone
from email.utils import parseaddr

from app.extractor import clean_job_title, clean_text
from app.models import DetectedEmail

REPLY_PREFIX = re.compile(r"^\s*(?:re|fw|fwd|tr|rép)\s*(?:\[\d+\])?\s*:\s*", re.I)
GENERIC_SUBJECTS = frozenset(
    {
        "votre candidature",
        "merci pour votre candidature",
        "candidature",
        "entretien",
        "confirmation de candidature",
        "confirmation de votre candidature",
        "stage",
    }
)


def _subject(value: str) -> tuple[str, bool]:
    reply = False
    while REPLY_PREFIX.match(value):
        reply = True
        value = REPLY_PREFIX.sub("", value, count=1)
    return clean_text(value).casefold().strip(" .!?"), reply


def _compatible(existing: str, incoming: str) -> bool:
    left, right = (
        clean_job_title(existing).casefold(),
        clean_job_title(incoming).casefold(),
    )
    return not left or not right or left == right


def _message_ids(value: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"<[^<>\s]{1,998}>", value[-8192:])))[-30:]


def find_conversation_application(
    connection: sqlite3.Connection, user_id: int, email: DetectedEmail, job_title: str
) -> int | None:
    # Le parent direct est prioritaire. Des références contradictoires ne sont
    # pas départagées arbitrairement entre plusieurs candidatures.
    for header in (email.in_reply_to, email.references):
        identifiers = _message_ids(header)
        if not identifiers:
            continue
        placeholders = ",".join("?" for _ in identifiers)
        rows = connection.execute(
            f"SELECT DISTINCT a.id,a.job_title FROM emails e JOIN applications a ON a.id=e.application_id AND a.user_id=e.user_id WHERE e.user_id=? AND e.message_id IN ({placeholders})",
            [user_id, *identifiers],
        ).fetchall()
        if rows:
            if len(rows) == 1 and _compatible(
                str(rows[0]["job_title"] or ""), job_title
            ):
                return int(rows[0]["id"])
            return None

    subject, incoming_reply = _subject(email.subject)
    address = parseaddr(email.sender)[1].strip().casefold()
    if (
        not address
        or "@" not in address
        or len(subject) < 12
        or subject in GENERIC_SUBJECTS
    ):
        return None
    if email.date.tzinfo is None:
        raise ValueError("Date d'email sans fuseau horaire.")
    date = email.date.astimezone(timezone.utc)
    rows = connection.execute(
        """SELECT a.id,a.job_title,e.sender,e.subject FROM emails e
           JOIN applications a ON a.id=e.application_id AND a.user_id=e.user_id
           WHERE e.user_id=? AND julianday(e.received_at) BETWEEN julianday(?) AND julianday(?)""",
        (
            user_id,
            (date - timedelta(days=90)).isoformat(),
            (date + timedelta(days=90)).isoformat(),
        ),
    ).fetchall()
    candidates = set()
    for row in rows:
        old_subject, old_reply = _subject(str(row["subject"] or ""))
        if (
            (incoming_reply or old_reply)
            and old_subject == subject
            and parseaddr(str(row["sender"] or ""))[1].strip().casefold() == address
            and _compatible(str(row["job_title"] or ""), job_title)
        ):
            candidates.add(int(row["id"]))
    return next(iter(candidates)) if len(candidates) == 1 else None
