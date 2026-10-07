from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from app.connectors.status import get_connector_statuses
from app.database import (
    create_imap_account,
    create_manual_application,
    delete_application,
    get_application,
    get_application_emails,
    get_applications,
    get_imap_accounts,
    update_imap_account,
    init_database,
    set_manual_status,
    update_application_details,
)
from app.mail_providers import detect_provider_smart
from app.maintenance import (
    expire_stale_applications,
)
from app.secrets import set_imap_password
from app.jobs import init_jobs
from app.presentation import (
    PreparedApplication,
    application_statistics,
    prepare_application_rows,
)
from app.presentation import format_datetime as _format_datetime
from app.settings import SECRET_KEY
from app.statuses import STATUS_LABELS, STATUS_ORDER
from app.web import (
    register_blueprints,
)
from app.web.jobs import (
    submit_job,
)
app = Flask(__name__)
app.secret_key = SECRET_KEY

register_blueprints(app)

app.secret_key = SECRET_KEY

"""Compatibilité : charge les données, puis délègue leur présentation."""

def prepare_applications(
    status_filter: str = "", search: str = "", mailbox_filter: str = "",

) -> list[PreparedApplication]:
    """Compatibilité : charge les données, puis délègue leur présentation."""
    return prepare_application_rows(get_applications(), status_filter, search, mailbox_filter)


def format_datetime(value: str | None) -> str:
    return _format_datetime(value)


def get_imap_account(account_id: int):
    """Return the configured IMAP account identified by ``account_id``."""
    for account in get_imap_accounts():
        if int(account["id"]) == account_id:
            return account
    return None


# Consultation
@app.post(
    "/connectors/imap/<int:account_id>/test"
)
def test_imap_account_web(
    account_id: int,
):
    account = get_imap_account(
        account_id
    )

    if account is None:
        abort(404)

    return submit_job(
        f"test:imap:{account_id}"
    )

@app.get("/connectors/imap/add")
def add_imap_account():
    return render_template(
        "imap_add.html",
        detected=None,
        email_address="",
    )

@app.post("/connectors/imap/detect")
def detect_imap_account():
    email_address = (
        request.form.get(
            "email",
            "",
        )
        .strip()
    )

    provider = detect_provider_smart(
        email_address
    )

    return render_template(
        "imap_add.html",
        detected=provider,
        email_address=email_address,
    )

@app.post("/connectors/imap/add")
def save_imap_account():
    email_address = request.form.get(
        "email",
        "",
    ).strip()

    provider_key = request.form.get(
        "provider",
        "",
    ).strip()

    auth_method = (
        request.form.get(
            "auth_method",
            "password",
        )
        .strip()
        .casefold()
    )

    host = request.form.get(
        "host",
        "",
    ).strip()

    username = request.form.get(
        "username",
        "",
    ).strip()

    password = request.form.get(
        "password",
        "",
    )

    folder = (
        request.form.get(
            "folder",
            "INBOX",
        ).strip()
        or "INBOX"
    )

    try:
        port = int(
            request.form.get(
                "port",
                "993",
            )
        )
    except ValueError:
        abort(400)

    use_ssl = (
        request.form.get(
            "use_ssl"
        )
        == "on"
    )

    if not email_address:
        abort(400)

    if not host:
        abort(400)

    if not username:
        abort(400)

    if (
        auth_method == "password"
        and not password
    ):
        abort(400)

    if auth_method not in {
        "password",
        "oauth2",
    }:
        abort(400)

    account_id = create_imap_account(
        email=email_address,
        provider=provider_key,
        host=host,
        port=port,
        use_ssl=use_ssl,
        username=username,
        folder=folder,
        auth_method=auth_method,
    )

    if (
        auth_method == "password"
        and password
    ):
        set_imap_password(
            account_id,
            password,
        )

    flash(
        "Boîte IMAP ajoutée.",
        "success",
    )

    return redirect(
        url_for(
            "connectors_page"
        )
    )

@app.route("/")
def index() -> str:
    applications = get_applications()

    status_filter = request.args.get(
        "status",
        "",
    ).strip()

    search = request.args.get(
        "q",
        "",
    ).strip()

    mailbox_filter = request.args.get(
        "mailbox",
        "",
    ).strip()

    prepared = prepare_application_rows(
        applications,
        status_filter,
        search,
        mailbox_filter,
    )

    stats = application_statistics(
        applications
    )

    mailboxes = sorted(
        {
            str(application["mailbox"]).strip()
            for application in applications
            if application["mailbox"]
        }
    )

    return render_template(
        "index.html",
        applications=prepared,
        stats=stats,
        mailboxes=mailboxes,
        total=stats["total"],
        status_filter=status_filter,
        mailbox_filter=mailbox_filter,
        search=search,
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

@app.get("/connectors/imap/<int:account_id>/edit")
def edit_imap_account(account_id: int):
    account = get_imap_account(
        account_id
    )

    if account is None:
        abort(404)

    return render_template(
        "imap_edit.html",
        account=account,
    )


@app.post("/connectors/imap/<int:account_id>/edit")
def update_imap_account_web(
    account_id: int,
):
    account = get_imap_account(
        account_id
    )

    if account is None:
        abort(404)

    email_address = request.form.get(
        "email",
        "",
    ).strip()

    provider = request.form.get(
        "provider",
        "",
    ).strip()

    host = request.form.get(
        "host",
        "",
    ).strip()

    username = request.form.get(
        "username",
        "",
    ).strip()

    password = request.form.get(
        "password",
        "",
    )

    auth_method = (
        request.form.get(
            "auth_method",
            "password",
        )
        .strip()
        .casefold()
    )

    folder = (
        request.form.get(
            "folder",
            "INBOX",
        ).strip()
        or "INBOX"
    )

    try:
        port = int(
            request.form.get(
                "port",
                "993",
            )
        )
    except ValueError:
        abort(400)

    use_ssl = (
        request.form.get("use_ssl")
        == "on"
    )

    if not email_address:
        abort(400)

    if not host:
        abort(400)

    if not username:
        abort(400)

    update_imap_account(
        account_id=account_id,
        email=email_address,
        provider=provider,
        host=host,
        port=port,
        use_ssl=use_ssl,
        username=username,
        folder=folder,
        auth_method=auth_method,
    )

    # Vide = on conserve l'ancien mot de passe.
    if (
        auth_method == "password"
        and password
    ):
        set_imap_password(
            account_id,
            password,
        )

    flash(
        "Boîte IMAP mise à jour.",
        "success",
    )

    return redirect(
        url_for("connectors_page")
    )

# Import et réanalyse


@app.before_request
def ensure_storage():
    init_database()
    init_jobs()
    expire_stale_applications()

# Connecteurs

@app.get("/connectors")
def connectors_page():
    connectors = get_connector_statuses()

    imap_accounts = []

    for row in get_imap_accounts():
        account = dict(row)

        account["last_checked_display"] = (
            format_datetime(
                row["last_checked_at"]
            )
            if row["last_checked_at"]
            else "Jamais"
        )

        imap_accounts.append(account)

    return render_template(
        "connectors.html",
        connectors=connectors,
        imap_accounts=imap_accounts,
    )

if __name__ == "__main__":
    init_database()
    app.run(host="127.0.0.1", port=5000, debug=True)
