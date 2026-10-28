from pathlib import Path

from flask import Flask
from flask_wtf.csrf import CSRFProtect

from app.database import init_database
from app.jobs import init_jobs
from app.settings import SECRET_KEY
from app.web.applications import applications_bp
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
    init_jobs()

    CSRFProtect(app)

    register_blueprints(app)

    return app
