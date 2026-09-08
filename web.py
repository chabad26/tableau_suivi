from typing import TypedDict

from flask import Flask, abort, render_template, request

from app.database import (
    get_application,
    get_application_emails,
    get_applications,
)


app = Flask(__name__)


STATUS_LABELS = {
    "SENT": "Envoyée",
    "RECEIVED": "Reçue",
    "INTERVIEW": "Entretien",
    "REJECTED": "Refus",
    "TEST": "Test technique",
    "OFFER": "Offre",
    "OTHER": "À analyser",
}


class PreparedApplication(TypedDict):
    id: int
    company: str
    job_title: str
    source: str
    status: str
    status_label: str
    manual_override: bool
    note: str


@app.route("/")
def index() -> str:
    applications = get_applications()

    status_filter = request.args.get("status", "").strip()
    search = request.args.get("q", "").strip().lower()

    prepared: list[PreparedApplication] = []

    for application in applications:
        effective_status: str = str(
            (
                application["manual_status"]
                if application["manual_override"]
                else application["current_status"]
            ) or "OTHER"
        )

        company = application["company"] or ""
        job_title = application["job_title"] or ""
        source = application["source"] or ""

        if status_filter and effective_status != status_filter:
            continue

        if search:
            haystack = " ".join(
                [
                    company.lower(),
                    job_title.lower(),
                    source.lower(),
                ]
            )

            if search not in haystack:
                continue

        prepared.append(
            {
                "id": application["id"],
                "company": company,
                "job_title": job_title,
                "source": source,
                "status": effective_status,
                "status_label": STATUS_LABELS.get(
                    effective_status,
                    effective_status,
                ),
                "manual_override": bool(
                    application["manual_override"]
                ),
                "note": application["manual_note"] or "",
            }
        )

    stats = {
        "total": len(applications),
        "sent": 0,
        "received": 0,
        "interview": 0,
        "rejected": 0,
        "offer": 0,
        "other": 0,
    }

    for application in applications:
        effective_status: str = str(
            (
                application["manual_status"]
                if application["manual_override"]
                else application["current_status"]
            ) or "OTHER"
        )

        if effective_status == "SENT":
            stats["sent"] += 1

        elif effective_status == "RECEIVED":
            stats["received"] += 1

        elif effective_status == "INTERVIEW":
            stats["interview"] += 1

        elif effective_status == "REJECTED":
            stats["rejected"] += 1

        elif effective_status == "OFFER":
            stats["offer"] += 1

        else:
            stats["other"] += 1

    return render_template(
        "index.html",
        applications=prepared,
        stats=stats,
        status_filter=status_filter,
        search=request.args.get("q", ""),
        status_labels=STATUS_LABELS,
    )

@app.route("/application/<int:application_id>")
def application_detail(application_id: int):
    application = get_application(
        application_id
    )

    if application is None:
        abort(404)

    emails = get_application_emails(
        application_id
    )

    effective_status: str = str(
        (
            application["manual_status"]
            if application["manual_override"]
            else application["current_status"]
        ) or "OTHER"
    )

    return render_template(
        "application.html",
        application=application,
        emails=emails,
        effective_status=effective_status,
        status_label=STATUS_LABELS.get(
            effective_status,
            effective_status,
        ),
        status_labels=STATUS_LABELS,
    )

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
    )
