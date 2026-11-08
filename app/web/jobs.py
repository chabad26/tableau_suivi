import json

from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    session,
    url_for,
)
from flask_login import current_user, login_required

from app.owned_jobs import enqueue_user_job, get_user_job, list_user_jobs

jobs_bp = Blueprint("jobs", __name__)


@jobs_bp.get("/jobs/login-sync")
@login_required
def login_sync_status():
    """Expose uniquement l'avancement des jobs de cette session et de son propriétaire."""
    user_id = int(current_user.get_id())
    states = []
    for job_id in session.get("login_sync_jobs", []):
        job = get_user_job(user_id, job_id)
        states.append(str(job["state"]) if job is not None else "failed")
    pending = any(state in {"queued", "running"} for state in states)
    failed = "failed" in states
    if not pending:
        session.pop("login_sync_jobs", None)
    return jsonify(pending=pending, failed=failed, queued="queued" in states)


def submit_job(kind: str):
    enqueue_user_job(int(current_user.get_id()), kind)

    flash(("Travail enregistré. Son avancement est disponible ci-dessous."), "info")

    return redirect(url_for("jobs.jobs_page"), code=303)


@jobs_bp.get("/jobs")
@login_required
def jobs_page():
    jobs = [dict(row) for row in list_user_jobs(int(current_user.get_id()))]

    for job in jobs:
        job["result"] = json.loads(job["result"]) if job["result"] else {}

    return render_template("jobs.html", jobs=jobs)


@jobs_bp.post("/scan")
@login_required
def scan_emails_web():
    return submit_job("scan")


@jobs_bp.post("/reclassify")
@login_required
def reclassify_emails_web():
    return submit_job("reclassify")
