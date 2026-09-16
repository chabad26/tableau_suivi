import csv
from datetime import datetime
from io import BytesIO, StringIO
from zoneinfo import ZoneInfo

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
from openpyxl import Workbook
from openpyxl.styles import Font

from app.connectors.gmail import TOKEN_FILE, scan_gmail
from app.connectors.microsoft import TOKEN_CACHE_FILE, scan_microsoft
from app.connectors.status import get_connector_statuses
from app.database import (
    create_manual_application,
    delete_application,
    get_application,
    get_application_emails,
    get_applications,
    init_database,
    set_manual_status,
    update_application_details,
)
from app.exports import EXPORT_COLUMN_WIDTHS, EXPORT_HEADERS, application_export_row
from app.importer import import_emails
from app.presentation import (
    PreparedApplication,
    application_statistics,
    prepare_application_rows,
)
from app.presentation import format_datetime as _format_datetime
from app.reclassifier import reclassify_emails
from app.scanner import scan_all_mailboxes
from app.settings import API_START_DATE
from app.statuses import STATUS_LABELS, STATUS_ORDER

app = Flask(__name__)

app.secret_key = "dev-secret-key"

CONNECTOR_TEST_START_DATE = API_START_DATE


# Préparation et compatibilité


def prepare_applications(
    status_filter: str = "", search: str = ""
) -> list[PreparedApplication]:
    """Compatibilité : charge les données, puis délègue leur présentation."""
    return prepare_application_rows(get_applications(), status_filter, search)


def format_datetime(value: str | None) -> str:
    return _format_datetime(value)


# Consultation


@app.route("/")
def index() -> str:
    applications = get_applications()
    status_filter = request.args.get("status", "").strip()
    search = request.args.get("q", "").strip()
    prepared = prepare_application_rows(applications, status_filter, search)
    stats = application_statistics(applications)
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
    application = get_application(application_id)

    if application is None:
        abort(404)

    emails = get_application_emails(application_id)

    formatted_emails: list[dict[str, object]] = []

    for email in emails:
        item: dict[str, object] = dict(email)

        item["received_at_display"] = format_datetime(email["received_at"])

        formatted_emails.append(item)

    first_seen = format_datetime(application["first_seen"])

    last_update = format_datetime(application["last_update"])

    completion_fields = [
        application["company"],
        application["job_title"],
        application["source"],
        application["current_status"],
    ]

    completion = round(
        sum(bool(field) for field in completion_fields) / len(completion_fields) * 100
    )

    effective_status: str = str(
        (
            application["manual_status"]
            if application["manual_override"]
            else application["current_status"]
        )
        or "OTHER"
    )

    return render_template(
        "application.html",
        application=application,
        emails=formatted_emails,
        completion=completion,
        effective_status=effective_status,
        status_label=STATUS_LABELS.get(effective_status, effective_status),
        status_labels=STATUS_LABELS,
        first_seen=first_seen,
        last_update=last_update,
    )


@app.route("/application/new")
def new_application():
    return render_template("new_application.html", status_labels=STATUS_LABELS)


# Création et modification


@app.route("/application/new", methods=["POST"])
def create_application_web():
    company = request.form.get("company", "").strip()

    job_title = request.form.get("job_title", "").strip()

    source = request.form.get("source", "").strip()

    status = request.form.get("status", "").strip()

    note = request.form.get("note", "").strip()

    if not company:
        abort(400)

    if status not in STATUS_LABELS:
        abort(400)

    if not source:
        source = "Manuel"

    application_id = create_manual_application(
        company=company, job_title=job_title, source=source, status=status, note=note
    )

    return redirect(url_for("application_detail", application_id=application_id))


@app.route("/application/<int:application_id>/edit", methods=["POST"])
def edit_application_web(application_id: int):
    application = get_application(application_id)

    if application is None:
        abort(404)

    company = request.form.get("company", "").strip()

    job_title = request.form.get("job_title", "").strip()

    source = request.form.get("source", "").strip()

    status = request.form.get("status", "").strip()

    note = request.form.get("note", "").strip()

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

    set_manual_status(application_id=application_id, status=status, note=note)

    return redirect(url_for("application_detail", application_id=application_id))


@app.route("/application/<int:application_id>/delete", methods=["POST"])
def delete_application_web(application_id: int):
    application = get_application(application_id)

    if application is None:
        abort(404)

    delete_application(application_id)

    return redirect(url_for("index"))


# Import et réanalyse


@app.route("/scan", methods=["POST"])
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

    return redirect(url_for("index"))


@app.route("/reclassify", methods=["POST"])
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

    return redirect(url_for("index"))


# Exports


@app.route("/export/csv")
def export_csv():
    applications = prepare_applications(
        status_filter=request.args.get("status", "").strip(),
        search=request.args.get("q", "").strip(),
    )
    with StringIO() as output:
        writer = csv.writer(output, delimiter=";")
        writer.writerow(EXPORT_HEADERS)
        writer.writerows(
            application_export_row(application) for application in applications
        )
        csv_content = output.getvalue()
    response = app.response_class(
        "\ufeff" + csv_content, mimetype="text/csv; charset=utf-8"
    )
    response.headers["Content-Disposition"] = "attachment; filename=candidatures.csv"
    return response


@app.route("/export/xlsx")
def export_xlsx():
    applications = prepare_applications(
        status_filter=request.args.get("status", "").strip(),
        search=request.args.get("q", "").strip(),
    )
    workbook = Workbook()
    sheet = workbook.active
    if sheet is None:
        sheet = workbook.create_sheet()
    sheet.title = "Candidatures"
    sheet.append(list(EXPORT_HEADERS))
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for application in applications:
        sheet.append(application_export_row(application))
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column, width in EXPORT_COLUMN_WIDTHS.items():
        sheet.column_dimensions[column].width = width
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name="candidatures.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# Connecteurs


@app.get("/connectors")
def connectors_page():
    connectors = get_connector_statuses()

    return render_template("connectors.html", connectors=connectors)


@app.post("/connectors/<connector_key>/test")
def test_connector(connector_key: str):
    try:
        if connector_key == "thunderbird":
            emails = scan_all_mailboxes()

            flash(
                (
                    "Thunderbird opérationnel : "
                    f"{len(emails)} mail(s) pertinent(s) détecté(s)."
                ),
                "success",
            )

        elif connector_key == "gmail":
            emails = scan_gmail(CONNECTOR_TEST_START_DATE)

            flash(
                (
                    "Gmail opérationnel : "
                    f"{len(emails)} mail(s) pertinent(s) détecté(s)."
                ),
                "success",
            )

        elif connector_key == "microsoft":
            emails = scan_microsoft(CONNECTOR_TEST_START_DATE)

            flash(
                (
                    "Microsoft Graph opérationnel : "
                    f"{len(emails)} mail(s) pertinent(s) détecté(s)."
                ),
                "success",
            )

        else:
            flash("Connecteur inconnu.", "info")

    except Exception as error:
        flash((f"Erreur avec {connector_key} : {error}"), "error")

    return redirect(url_for("connectors_page"))


@app.post("/connectors/<connector_key>/reconnect")
def reconnect_connector(connector_key: str):
    try:
        if connector_key == "gmail":
            TOKEN_FILE.unlink(missing_ok=True)

            emails = scan_gmail(CONNECTOR_TEST_START_DATE)

            flash(
                (f"Gmail reconnecté avec succès : {len(emails)} mail(s) pertinent(s)."),
                "success",
            )

        elif connector_key == "microsoft":
            TOKEN_CACHE_FILE.unlink(missing_ok=True)

            emails = scan_microsoft(CONNECTOR_TEST_START_DATE)

            flash(
                (
                    "Microsoft reconnecté avec succès : "
                    f"{len(emails)} mail(s) pertinent(s)."
                ),
                "success",
            )

        else:
            flash("Ce connecteur ne nécessite pas de reconnexion.", "info")

    except Exception as error:
        flash((f"Reconnexion impossible : {error}"), "error")

    return redirect(url_for("connectors_page"))


if __name__ == "__main__":
    init_database()
    app.run(host="127.0.0.1", port=5000, debug=True)
