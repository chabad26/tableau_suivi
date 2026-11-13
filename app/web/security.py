"""Configuration des protections HTTP de l'application."""

import os

from flask import Flask, request

from app.documents import MAX_DOCUMENT_BYTES


def configure_security(app: Flask) -> None:
    https_enabled = os.getenv("APP_HTTPS", "false").lower() == "true"

    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=https_enabled,
        SESSION_COOKIE_NAME="job_tracker_session",
        PERMANENT_SESSION_LIFETIME=3600,
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
    )

    @app.before_request
    def document_upload_limit():
        if request.endpoint in {
            "documents.upload_document_web",
            "documents.upload_version_web",
        }:
            request.max_content_length = MAX_DOCUMENT_BYTES + 1024 * 1024

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )

        response.headers["Cache-Control"] = "no-store"

        return response
