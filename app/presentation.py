"""Préparation des candidatures pour les pages et les exports, sans accès SQLite."""

import sqlite3
from collections.abc import Sequence
from datetime import datetime
from typing import TypedDict

from app.statuses import STATUS_LABELS, STATUS_ORDER


class PreparedApplication(TypedDict):
    id: int
    company: str
    job_title: str
    source: str
    status: str
    status_label: str
    manual_override: bool
    note: str
    first_seen: str
    last_update: str


def format_datetime(value: str | None) -> str:
    if not value:
        return "-"
    try:
        date = datetime.fromisoformat(value)
    except ValueError:
        return value
    return date.strftime("%d/%m/%Y à %H:%M")


def effective_status(application: sqlite3.Row) -> str:
    status = (
        application["manual_status"]
        if application["manual_override"]
        else application["current_status"]
    )
    return str(status or "OTHER")


def prepare_application_rows(
    applications: Sequence[sqlite3.Row], status_filter: str = "", search: str = ""
) -> list[PreparedApplication]:
    prepared: list[PreparedApplication] = []
    search_lower = search.strip().casefold()
    for application in applications:
        status = effective_status(application)
        company = application["company"] or ""
        job_title = application["job_title"] or ""
        source = application["source"] or ""
        note = application["manual_note"] or ""
        if status_filter and status != status_filter:
            continue
        haystack = " ".join([company, job_title, source, note]).casefold()
        if search_lower and search_lower not in haystack:
            continue
        prepared.append(
            PreparedApplication(
                id=application["id"],
                company=company,
                job_title=job_title,
                source=source,
                status=status,
                status_label=STATUS_LABELS.get(status, status),
                manual_override=bool(application["manual_override"]),
                note=note,
                first_seen=format_datetime(application["first_seen"]),
                last_update=format_datetime(application["last_update"]),
            )
        )
    return prepared

def application_statistics(
    applications: Sequence[sqlite3.Row],
) -> dict[str, int]:

    """Conserve les clés historiques en majuscules et en minuscules."""

    stats = dict.fromkeys(
        STATUS_ORDER,
        0,
    )

    legacy_statuses = {
        "SENT",
        "RECEIVED",
        "INTERVIEW",
        "REJECTED",
        "OFFER",
    }

    stats.update(
        dict.fromkeys(
            [
                *(
                    status.lower()
                    for status in legacy_statuses
                ),
                "other",
            ],
            0,
        )
    )

    stats["total"] = len(applications)

    for application in applications:
        status = effective_status(application)

        if status in stats:
            stats[status] += 1

        legacy_key = (
            status.lower()
            if status in legacy_statuses
            else "other"
        )

        stats[legacy_key] += 1

    return stats