from typing import TypedDict
from flask import flash
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from app.database import (
    create_manual_application,
    get_application,
    get_application_emails,
    get_applications,
    set_manual_status,
    update_application_details,
    delete_application,
)
from app.importer import import_emails
from app.reclassifier import reclassify_emails
from datetime import datetime
from app.statuses import (
    STATUS_LABELS,
    STATUS_ORDER
)
import csv
from io import BytesIO, StringIO
from openpyxl import Workbook

app = Flask(__name__)
app.secret_key = "dev-secret-key"

class PreparedApplication(TypedDict):
    id: int
    company: str
    job_title: str
    source: str
    status: str
    status_label: str
    manual_override: bool
    note: str

def prepare_applications(
    status_filter: str = "",
    search: str = "",
) -> list[dict[str, object]]:
    applications = get_applications()

    prepared: list[dict[str, object]] = []

    search_lower = search.strip().casefold()

    for application in applications:
        effective_status = (
            application["manual_status"]
            if application["manual_override"]
            else application["current_status"]
        )

        company = application["company"] or ""
        job_title = application["job_title"] or ""
        source = application["source"] or ""
        note = application["manual_note"] or ""

        if (
            status_filter
            and effective_status != status_filter
        ):
            continue

        if search_lower:
            haystack = " ".join(
                [
                    company,
                    job_title,
                    source,
                    note,
                ]
            ).casefold()

            if search_lower not in haystack:
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
                "note": note,
                "first_seen": format_datetime(
                    application["first_seen"]
                ),
                "last_update": format_datetime(
                    application["last_update"]
                ),
                "manual_override": bool(
                    application["manual_override"]
                ),
            }
        )

    return prepared

def format_datetime(
    value: str | None,
) -> str:
    if not value:
        return "-"

    try:
        date = datetime.fromisoformat(
            value
        )
    except ValueError:
        return value

    return date.strftime(
        "%d/%m/%Y à %H:%M"
    )

@app.route(
    "/application/<int:application_id>/edit",
    methods=["POST"],
)
def edit_application_web(application_id: int):
    application = get_application(
        application_id
    )

    if application is None:
        abort(404)

    company = request.form.get(
        "company",
        ""
    ).strip()

    job_title = request.form.get(
        "job_title",
        ""
    ).strip()

    source = request.form.get(
        "source",
        ""
    ).strip()

    status = request.form.get(
        "status",
        ""
    ).strip()

    note = request.form.get(
        "note",
        ""
    ).strip()

    if not company:
        abort(400)

    if status not in STATUS_LABELS:
        abort(400)

    update_application_details(
        application_id=application_id,
        company=company,
        job_title=job_title,
        source=source,
    )

    set_manual_status(
        application_id=application_id,
        status=status,
        note=note,
    )

    return redirect(
        url_for(
            "application_detail",
            application_id=application_id,
        )
    )

@app.route(
    "/scan",
    methods=["POST"],
)
def scan_emails_web():
    result = import_emails()

    if result.added:
        flash(
            (
                f"Scan terminé : "
                f"{result.added} nouveau(x) mail(s) importé(s) "
                f"sur {result.detected} détecté(s)."
            ),
            "success",
        )
    else:
        flash(
            (
                f"Scan terminé : aucun nouveau mail. "
                f"{result.detected} mail(s) pertinent(s) détecté(s)."
            ),
            "info",
        )

    return redirect(
        url_for("index")
    )

@app.route(
    "/application/<int:application_id>/delete",
    methods=["POST"],
)
def delete_application_web(
    application_id: int,
):
    application = get_application(
        application_id
    )

    if application is None:
        abort(404)

    delete_application(
        application_id
    )

    return redirect(
        url_for("index")
    )

@app.route(
    "/reclassify",
    methods=["POST"],
)
def reclassify_emails_web():
    result = reclassify_emails()

    if result.changed or result.applications_updated:
        flash(
            (
                f"Reclassification terminée : "
                f"{result.changed} mail(s) reclassifié(s), "
                f"{result.applications_updated} candidature(s) mise(s) à jour."
            ),
            "success",
        )
    else:
        flash(
            (
                f"Reclassification terminée : "
                f"aucun changement sur {result.found} mail(s) retrouvé(s)."
            ),
            "info",
        )

    return redirect(
        url_for("index")
    )

@app.route("/export/csv")
def export_csv():
    status_filter = request.args.get(
        "status",
        ""
    ).strip()

    search = request.args.get(
        "q",
        ""
    ).strip()

    applications = prepare_applications(
        status_filter=status_filter,
        search=search,
    )

    output = StringIO()

    writer = csv.writer(
        output,
        delimiter=";",
    )

    writer.writerow(
        [
            "Entreprise",
            "Poste",
            "Source",
            "Statut",
            "Note",
            "Première détection",
            "Dernière mise à jour",
            "Modification manuelle",
        ]
    )

    for application in applications:
        writer.writerow(
            [
                application["company"],
                application["job_title"],
                application["source"],
                application["status_label"],
                application["note"],
                application["first_seen"],
                application["last_update"],
                (
                    "Oui"
                    if application["manual_override"]
                    else "Non"
                ),
            ]
        )

    csv_content = output.getvalue()

    output.close()

    response = app.response_class(
        "\ufeff" + csv_content,
        mimetype="text/csv; charset=utf-8",
    )

    response.headers[
        "Content-Disposition"
    ] = (
        "attachment; "
        "filename=candidatures.csv"
    )

    return response

@app.route("/export/xlsx")
def export_xlsx():
    status_filter = request.args.get(
        "status",
        ""
    ).strip()

    search = request.args.get(
        "q",
        ""
    ).strip()

    applications = prepare_applications(
        status_filter=status_filter,
        search=search,
    )

    workbook = Workbook()

    sheet = workbook.active
    if sheet is None:
        sheet = workbook.create_sheet()
    sheet.title = "Candidatures"

    headers = [
        "Entreprise",
        "Poste",
        "Source",
        "Statut",
        "Note",
        "Première détection",
        "Dernière mise à jour",
        "Modification manuelle",
    ]

    sheet.append(
        headers
    )
    from openpyxl.styles import Font
    for cell in sheet[1]:
        cell.font = Font(
            bold=True
        )
        
    for application in applications:
        sheet.append(
            [
                application["company"],
                application["job_title"],
                application["source"],
                application["status_label"],
                application["note"],
                application["first_seen"],
                application["last_update"],
                (
                    "Oui"
                    if application["manual_override"]
                    else "Non"
                ),
            ]
        )

    sheet.freeze_panes = "A2"

    sheet.auto_filter.ref = (
        sheet.dimensions
    )

    widths = {
        "A": 28,
        "B": 50,
        "C": 25,
        "D": 20,
        "E": 45,
        "F": 22,
        "G": 22,
        "H": 22,
    }

    for column, width in widths.items():
        sheet.column_dimensions[
            column
        ].width = width

    output = BytesIO()

    workbook.save(
        output
    )

    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="candidatures.xlsx",
        mimetype=(
            "application/"
            "vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )

@app.route("/")
def index() -> str:
    applications = get_applications()

    status_filter = request.args.get(
        "status",
        ""
    ).strip()

    search = request.args.get(
        "q",
        ""
    ).strip()

    prepared = prepare_applications(
        status_filter=status_filter,
        search=search,
    )

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
        status: 0
        for status in STATUS_ORDER
    }
    stats["total"] = len(applications)
    stats.update({
        status: 0
        for status in (
            "sent", "received", "interview", "rejected", "offer", "other"
        )
    })

    for application in applications:
        effective_status = (
            application["manual_status"]
            if application["manual_override"]
            else application["current_status"]
        )

        if effective_status in stats:
            stats[effective_status] += 1

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
        total=stats["total"],
        status_filter=status_filter,
        search=request.args.get("q", ""),
        status_labels=STATUS_LABELS,
        status_order=STATUS_ORDER,
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

    first_seen = format_datetime(
        application["first_seen"]
    )

    last_update = format_datetime(
        application["last_update"]
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
        first_seen=first_seen,
        last_update=last_update,
    )
@app.route("/application/new")
def new_application():
    return render_template(
        "new_application.html",
        status_labels=STATUS_LABELS,
    )


@app.route(
    "/application/new",
    methods=["POST"],
)
def create_application_web():
    company = request.form.get(
        "company",
        ""
    ).strip()

    job_title = request.form.get(
        "job_title",
        ""
    ).strip()

    source = request.form.get(
        "source",
        ""
    ).strip()

    status = request.form.get(
        "status",
        ""
    ).strip()

    note = request.form.get(
        "note",
        ""
    ).strip()

    if not company:
        abort(400)

    if status not in STATUS_LABELS:
        abort(400)

    if not source:
        source = "Manuel"

    application_id = create_manual_application(
        company=company,
        job_title=job_title,
        source=source,
        status=status,
        note=note,
    )

    return redirect(
        url_for(
            "application_detail",
            application_id=application_id,
        )
    )

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
    )
