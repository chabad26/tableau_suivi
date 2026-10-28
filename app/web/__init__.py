from pathlib import Path

from flask import Flask

from app.database import init_database
from app.jobs import init_jobs
from app.maintenance import expire_stale_applications
from app.settings import SECRET_KEY
from app.web.applications import applications_bp
from app.web.connectors import connectors_bp
from app.web.exports import exports_bp
from app.web.jobs import jobs_bp

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

    register_blueprints(app)

    @app.before_request
    def ensure_storage():
        init_database()
        init_jobs()
        expire_stale_applications()

    return app
