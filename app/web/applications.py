"""Routes des candidatures personnelles."""

from flask import Blueprint, abort, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.job_titles import suggest_job_title
from app.offers import OfferInputError
from app.owned_applications import (
    create_user_application,
    delete_user_application,
    get_user_application,
    get_user_application_emails,
    get_user_applications,
    update_user_application,
    update_user_application_offer,
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
        applications, status_filter, search, mailbox_filter
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
    return _render_application(application_id)


def _render_application(
    application_id: int,
    offer_values: dict[str, str] | None = None,
    offer_error: str | None = None,
):
    user_id = owner_id()

    application = get_user_application(user_id, application_id)

    if application is None:
        abort(404)

    emails = get_user_application_emails(user_id, application_id)
    suggestion = suggest_job_title(
        str(application["offer_text"] or ""),
        ((str(email["subject"] or ""), str(email["body"] or "")) for email in emails),
        company=str(application["company"] or ""),
    )
    if (
        suggestion
        and suggestion.title.strip().casefold()
        == str(application["job_title"] or "").strip().casefold()
    ):
        suggestion = None

    formatted_emails = []

    for email in emails:
        item = dict(email)

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
        status_label=STATUS_LABELS.get(effective_status, effective_status),
        status_labels=STATUS_LABELS,
        first_seen=first_seen,
        last_update=last_update,
        offer_values=offer_values
        if offer_values is not None
        else {
            "offer_url": str(application["offer_url"]),
            "offer_text": str(application["offer_text"]),
        },
        offer_error=offer_error,
        job_title_suggestion=suggestion,
    )


@applications_bp.get("/application/new")
@login_required
def new_application():
    return render_template("new_application.html", status_labels=STATUS_LABELS)


@applications_bp.post("/application/new")
@login_required
def create_application_web():
    company = request.form.get("company", "").strip()
    job_title = request.form.get("job_title", "").strip()
    source = request.form.get("source", "").strip()
    status = request.form.get("status", "").strip()
    note = request.form.get("note", "").strip()
    offer_text = request.form.get("offer_text", "")
    offer_url = request.form.get("offer_url", "")

    if not company or status not in STATUS_LABELS:
        abort(400)

    try:
        application_id = create_user_application(
            user_id=owner_id(),
            company=company,
            job_title=job_title,
            source=source,
            status=status,
            note=note,
            offer_text=offer_text,
            offer_url=offer_url,
        )
    except OfferInputError as error:
        return render_template(
            "new_application.html",
            status_labels=STATUS_LABELS,
            values={
                "company": company,
                "job_title": job_title,
                "source": source,
                "status": status,
                "note": note,
                "offer_text": offer_text,
                "offer_url": offer_url,
            },
            error=str(error),
        ), 400

    return redirect(
        url_for("applications.application_detail", application_id=application_id),
        code=303,
    )


@applications_bp.post("/application/<int:application_id>/offer")
@login_required
def edit_offer_web(application_id: int):
    values = {
        "offer_text": request.form.get("offer_text", ""),
        "offer_url": request.form.get("offer_url", ""),
    }
    if get_user_application(owner_id(), application_id) is None:
        abort(404)
    try:
        updated = update_user_application_offer(owner_id(), application_id, **values)
    except OfferInputError as error:
        return _render_application(application_id, values, str(error)), 400
    if not updated:
        abort(404)
    return redirect(
        url_for("applications.application_detail", application_id=application_id),
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
        url_for("applications.application_detail", application_id=application_id),
        code=303,
    )


@applications_bp.post("/application/<int:application_id>/delete")
@login_required
def delete_application_web(application_id: int):
    deleted = delete_user_application(owner_id(), application_id)

    if not deleted:
        abort(404)

    return redirect(url_for("applications.index"), code=303)
