import json

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.owned_jobs import enqueue_user_job, list_user_jobs

jobs_bp = Blueprint("jobs", __name__)


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
def scan_emails_web():
    return submit_job("scan")


@jobs_bp.post("/reclassify")
def reclassify_emails_web():
    abort(503, description="Réanalyse en cours de migration multi-utilisateur.")
