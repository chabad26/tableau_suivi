from flask import (
    Blueprint,
    abort,
    redirect,
    render_template,
    request,
    url_for,
)

from app.database import (
    create_manual_application,
    delete_application,
    get_application,
    get_application_emails,
    get_applications,
    set_manual_status,
    update_application_details,
)
from app.presentation import (
    application_statistics,
    format_datetime,
    prepare_application_rows,
)
from app.statuses import (
    STATUS_LABELS,
    STATUS_ORDER,
)


applications_bp = Blueprint(
    "applications",
    __name__,
)


@applications_bp.get("/")
def index():
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
            str(
                application["mailbox"]
            ).strip()
            for application
            in applications
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


@applications_bp.get(
    "/application/<int:application_id>"
)
def application_detail(
    application_id: int,
):
    application = get_application(
        application_id
    )

    if application is None:
        abort(404)

    emails = get_application_emails(
        application_id
    )

    formatted_emails = []

    for email in emails:
        item = dict(email)

        item[
            "received_at_display"
        ] = format_datetime(
            email["received_at"]
        )

        formatted_emails.append(
            item
        )

    first_seen = format_datetime(
        application["first_seen"]
    )

    last_update = format_datetime(
        application["last_update"]
    )

    completion_fields = [
        application["company"],
        application["job_title"],
        application["source"],
        application["current_status"],
    ]

    completion = round(
        (
            sum(
                bool(field)
                for field
                in completion_fields
            )
            / len(completion_fields)
        )
        * 100
    )

    effective_status = str(
        (
            application[
                "manual_status"
            ]
            if application[
                "manual_override"
            ]
            else application[
                "current_status"
            ]
        )
        or "OTHER"
    )

    return render_template(
        "application.html",
        application=application,
        emails=formatted_emails,
        completion=completion,
        effective_status=(
            effective_status
        ),
        status_label=(
            STATUS_LABELS.get(
                effective_status,
                effective_status,
            )
        ),
        status_labels=STATUS_LABELS,
        first_seen=first_seen,
        last_update=last_update,
    )


@applications_bp.get(
    "/application/new"
)
def new_application():
    return render_template(
        "new_application.html",
        status_labels=STATUS_LABELS,
    )


@applications_bp.post(
    "/application/new"
)
def create_application_web():
    company = request.form.get(
        "company",
        "",
    ).strip()

    job_title = request.form.get(
        "job_title",
        "",
    ).strip()

    source = request.form.get(
        "source",
        "",
    ).strip()

    status = request.form.get(
        "status",
        "",
    ).strip()

    note = request.form.get(
        "note",
        "",
    ).strip()

    if not company:
        abort(400)

    if status not in STATUS_LABELS:
        abort(400)

    if not source:
        source = "Manuel"

    application_id = (
        create_manual_application(
            company=company,
            job_title=job_title,
            source=source,
            status=status,
            note=note,
        )
    )

    return redirect(
        url_for(
            "applications.application_detail",
            application_id=(
                application_id
            ),
        )
    )


@applications_bp.post(
    "/application/"
    "<int:application_id>/edit"
)
def edit_application_web(
    application_id: int,
):
    application = get_application(
        application_id
    )

    if application is None:
        abort(404)

    company = request.form.get(
        "company",
        "",
    ).strip()

    job_title = request.form.get(
        "job_title",
        "",
    ).strip()

    source = request.form.get(
        "source",
        "",
    ).strip()

    status = request.form.get(
        "status",
        "",
    ).strip()

    note = request.form.get(
        "note",
        "",
    ).strip()

    if not company:
        abort(400)

    if status not in STATUS_LABELS:
        abort(400)

    update_application_details(
        application_id=(
            application_id
        ),
        company=company,
        job_title=job_title,
        source=source,
    )

    set_manual_status(
        application_id=(
            application_id
        ),
        status=status,
        note=note,
    )

    return redirect(
        url_for(
            "applications.application_detail",
            application_id=(
                application_id
            ),
        )
    )


@applications_bp.post(
    "/application/"
    "<int:application_id>/delete"
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
        url_for(
            "applications.index"
        )
    )