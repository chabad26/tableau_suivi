from pathlib import Path

from flask import Flask, abort, redirect, request, url_for
from flask_login import current_user
from flask_wtf.csrf import CSRFProtect

from app.accounts import init_users
from app.database import init_database
from app.jobs import init_jobs
from app.ownership import init_ownership
from app.settings import SECRET_KEY
from app.web.applications import applications_bp
from app.web.auth import auth_bp, login_manager
from app.web.connectors import connectors_bp
from app.web.exports import exports_bp
from app.web.jobs import jobs_bp
from app.web.security import configure_security

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(applications_bp)
    app.register_blueprint(connectors_bp)
    app.register_blueprint(exports_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(auth_bp)


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(PROJECT_ROOT / "templates"),
        static_folder=str(PROJECT_ROOT / "static"),
    )

    app.secret_key = SECRET_KEY

    configure_security(app)

    # Initialisation au démarrage, pas à chaque requête.
    init_database()
    init_users()
    init_jobs()
    init_ownership()
    login_manager.init_app(app)
    CSRFProtect(app)

    register_blueprints(app)

    @app.before_request
    def protect_routes():
        # Fichiers statiques et authentification.
        if request.endpoint in {"static", "auth.login", "auth.logout", "auth.account"}:
            return None

        # Toutes les autres routes nécessitent une session.
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))

        # Les routes des candidatures utilisent maintenant
        # les requêtes SQL avec contrôle du propriétaire.
        allowed_endpoints = {
            "applications.index",
            "applications.application_detail",
            "applications.new_application",
            "applications.create_application_web",
            "applications.edit_application_web",
            "applications.delete_application_web",
        }

        if request.endpoint in allowed_endpoints:
            return None

        # Connecteurs, exports et jobs :
        # toujours bloqués pendant la migration.
        abort(503, description="Module en cours de migration multi-utilisateur.")

    return app
