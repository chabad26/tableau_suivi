"""Authentification HTTP avec Flask-Login."""

import sqlite3
from dataclasses import dataclass

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import LoginManager, UserMixin, current_user, login_user, logout_user

from app.accounts import User, authenticate, get_user
from app.owned_imap import get_enabled_user_imap_accounts
from app.owned_jobs import enqueue_user_job

auth_bp = Blueprint("auth", __name__)
login_manager = LoginManager()

# Flask-Login initialise cet attribut à None sans annoter le type str | None.
login_manager.login_view = "auth.login"  # pyright: ignore[reportAttributeAccessIssue]
login_manager.login_message = "Connecte-toi pour continuer."
login_manager.login_message_category = "info"


@dataclass
class LoginUser(UserMixin):
    """Adaptateur entre notre modèle User et Flask-Login."""

    id: int
    email: str
    role: str
    active: bool
    promotion_name: str = ""

    @property
    def is_active(self) -> bool:
        return self.active


def as_login_user(user: User) -> LoginUser:
    return LoginUser(
        id=user.id,
        email=user.email,
        role=user.role,
        active=user.active,
        promotion_name=user.promotion_name,
    )


@login_manager.user_loader
def load_user(user_id: str) -> LoginUser | None:
    try:
        identifier = int(user_id)
    except ValueError:
        return None

    if identifier <= 0:
        return None

    user = get_user(identifier)

    if user is None or not user.active:
        return None

    return as_login_user(user)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("auth.account"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        user = authenticate(email, password)

        if user is None:
            flash("Identifiants invalides.", "error")
        else:
            login_user(as_login_user(user), remember=False)
            session.pop("login_sync_jobs", None)
            if current_app.config.get("AUTO_SYNC_ON_LOGIN", True):
                jobs = []
                try:
                    # Le traitement local passe avant le réseau : il reste disponible
                    # même lorsque les fournisseurs IMAP sont injoignables.
                    jobs.append(enqueue_user_job(user.id, "reclassify"))
                    if get_enabled_user_imap_accounts(user.id):
                        jobs.append(enqueue_user_job(user.id, "scan"))
                except sqlite3.Error, ValueError:
                    current_app.logger.warning(
                        "Synchronisation de connexion indisponible"
                    )
                    flash(
                        "La mise à jour automatique est indisponible. Tes candidatures restent accessibles.",
                        "info",
                    )
                session["login_sync_jobs"] = jobs

            return redirect(url_for("auth.account"), code=303)

    return render_template("login.html")


@auth_bp.post("/logout")
def logout():
    session.pop("login_sync_jobs", None)
    logout_user()

    return redirect(url_for("auth.login"), code=303)


@auth_bp.get("/account")
def account():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))

    return render_template("account.html")
