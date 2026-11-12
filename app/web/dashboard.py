"""Dashboard uniquement chiffré, avec autorisation vérifiée dans le service."""

from flask import Blueprint, abort, render_template, request
from flask_login import current_user, login_required

from app.dashboard import dashboard_statistics
from app.presentation import format_datetime
from app.statuses import STATUS_LABELS, STATUS_ORDER

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/dashboard")
@login_required
def dashboard_page():
    try:
        data = dashboard_statistics(
            int(current_user.get_id()),
            scope=request.args.get(
                "scope", "campus" if current_user.role == "admin" else "personal"
            ),
            promotion=request.args.get("promotion", ""),
            months=int(request.args.get("months", "6")),
        )
    except PermissionError:
        abort(403)
    except ValueError:
        abort(400, description="Filtres du dashboard invalides.")
    return render_template(
        "dashboard.html",
        dashboard=data,
        status_labels=STATUS_LABELS,
        status_order=STATUS_ORDER,
        history_started_at=format_datetime(data["history_started_at"]),
    )
