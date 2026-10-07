from flask import Flask

from app.web.exports import (
    exports_bp,
)
from app.web.jobs import (
    jobs_bp,
)


def register_blueprints(
    app: Flask,
) -> None:
    app.register_blueprint(
        exports_bp
    )

    app.register_blueprint(
        jobs_bp
    )