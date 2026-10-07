import json

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    url_for,
)

from app.jobs import (
    enqueue,
    list_jobs,
)


jobs_bp = Blueprint(
    "jobs",
    __name__,
)


def submit_job(
    kind: str,
):
    enqueue(kind)

    flash(
        (
            "Travail enregistré. "
            "Son avancement est disponible ci-dessous."
        ),
        "info",
    )

    return redirect(
        url_for(
            "jobs.jobs_page"
        ),
        code=303,
    )


@jobs_bp.get("/jobs")
def jobs_page():
    jobs = [
        dict(row)
        for row in list_jobs()
    ]

    for job in jobs:
        job["result"] = (
            json.loads(
                job["result"]
            )
            if job["result"]
            else {}
        )

    return render_template(
        "jobs.html",
        jobs=jobs,
    )


@jobs_bp.post("/scan")
def scan_emails_web():
    return submit_job(
        "scan"
    )


@jobs_bp.post("/reclassify")
def reclassify_emails_web():
    return submit_job(
        "reclassify"
    )