"""Anciennes URL d'export, conservées sans lecture de données."""

from flask import Blueprint, abort
from flask_login import login_required

exports_bp = Blueprint("exports", __name__)


@exports_bp.get("/export/csv")
@exports_bp.get("/export/xlsx")
@login_required
def unavailable_export():
    abort(503, description="Les exports ne sont pas disponibles dans cette version.")
