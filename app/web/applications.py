"""Routes des candidatures personnelles."""

from flask import Blueprint, abort, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.owned_applications import (
    create_user_application,
    delete_user_application,
    get_user_application,
    get_user_application_emails,
    get_user_applications,
    update_user_application,
)
from app.presentation import (
    application_statistics,
    format_datetime,
    prepare_application_rows,
)
from app.statuses import STATUS_LABELS, STATUS_ORDER


applications_bp = Blueprint("applications", __name__)


def owner_id() -> int:
    """Identifiant provenant de la session, jamais du formulaire."""
    return int(current_user.get_id())


@applications_bp.get("/")
@login_required
def index():
    applications = get_user_applications(owner_id())

    status_filter = request.args.get("status", "").strip()
    search = request.args.get("q", "").strip()
    mailbox_filter = request.args.get("mailbox", "").strip()

    prepared = prepare_application_rows(
        applications,
        status_filter,
        search,
        mailbox_filter,
    )

    stats = application_statistics(applications)

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


@applications_bp.get("/application/<int:application_id>")
@login_required
def application_detail(application_id: int):
    user_id = owner_id()

    application = get_user_application(
        user_id,
        application_id,
    )

    if application is None:
        abort(404)

    emails = get_user_application_emails(
        user_id,
        application_id,
    )

    formatted_emails = []

    for email in emails:
        item = dict(email)

        item["received_at_display"] = format_datetime(
            email["received_at"]
        )

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
        sum(bool(field) for field in completion_fields)
        / len(completion_fields)
        * 100
    )

    effective_status = str(
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
        status_label=STATUS_LABELS.get(
            effective_status,
            effective_status,
        ),
        status_labels=STATUS_LABELS,
        first_seen=first_seen,
        last_update=last_update,
    )


@applications_bp.get("/application/new")
@login_required
def new_application():
    return render_template(
        "new_application.html",
        status_labels=STATUS_LABELS,
    )


@applications_bp.post("/application/new")
@login_required
def create_application_web():
    company = request.form.get("company", "").strip()
    job_title = request.form.get("job_title", "").strip()
    source = request.form.get("source", "").strip()
    status = request.form.get("status", "").strip()
    note = request.form.get("note", "").strip()

    if not company or status not in STATUS_LABELS:
        abort(400)

    application_id = create_user_application(
        user_id=owner_id(),
        company=company,
        job_title=job_title,
        source=source,
        status=status,
        note=note,
    )

    return redirect(
        url_for(
            "applications.application_detail",
            application_id=application_id,
        ),
        code=303,
    )


@applications_bp.post("/application/<int:application_id>/edit")
@login_required
def edit_application_web(application_id: int):
    company = request.form.get("company", "").strip()
    job_title = request.form.get("job_title", "").strip()
    source = request.form.get("source", "").strip()
    status = request.form.get("status", "").strip()
    note = request.form.get("note", "").strip()

    if not company or status not in STATUS_LABELS:
        abort(400)

    updated = update_user_application(
        user_id=owner_id(),
        application_id=application_id,
        company=company,
        job_title=job_title,
        source=source,
        status=status,
        note=note,
    )

    if not updated:
        abort(404)

    return redirect(
        url_for(
            "applications.application_detail",
            application_id=application_id,
        ),
        code=303,
    )


@applications_bp.post("/application/<int:application_id>/delete")
@login_required
def delete_application_web(application_id: int):
    deleted = delete_user_application(
        owner_id(),
        application_id,
    )

    if not deleted:
        abort(404)

    return redirect(
        url_for("applications.index"),
        code=303,
    )