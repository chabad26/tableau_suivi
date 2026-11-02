"""Backoffice des comptes ; toutes les vues sont réservées aux administrateurs."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.accounts import UserInputError
from app.admin_accounts import (
    AdminAccountConflict,
    AdminAccountStorageError,
    create_managed_user,
    list_managed_users,
    set_managed_user_active,
)
from app.web.auth import login_manager

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
ROLE_LABELS = {
    "student": "Apprenant",
    "trainer": "Formateur",
    "admin": "Administrateur",
}


@admin_bp.before_request
def require_admin():
    if not current_user.is_authenticated:
        return login_manager.unauthorized()
    if current_user.role != "admin":
        abort(403, description="Cette page est réservée aux administrateurs.")
    return None


@admin_bp.get("/users")
def users_page():
    try:
        users = list_managed_users(int(current_user.get_id()))
    except PermissionError:
        abort(403)
    return render_template("admin/users.html", users=users, role_labels=ROLE_LABELS)


@admin_bp.get("/users/new")
def new_user():
    return render_template(
        "admin/user_new.html",
        email="",
        selected_role="student",
        role_labels=ROLE_LABELS,
        error=None,
    )


@admin_bp.post("/users")
def create_user_web():
    email = request.form.get("email", "").strip()
    role = request.form.get("role", "student")
    password = request.form.get("password", "")
    confirmation = request.form.get("password_confirm", "")
    try:
        if password != confirmation:
            raise UserInputError("Les mots de passe ne correspondent pas.")
        create_managed_user(int(current_user.get_id()), email, password, role)
    except PermissionError:
        abort(403)
    except AdminAccountStorageError:
        abort(
            503, description="Création momentanément indisponible. Réessayer plus tard."
        )
    except (UserInputError, AdminAccountConflict) as error:
        return render_template(
            "admin/user_new.html",
            email=email,
            selected_role=role,
            role_labels=ROLE_LABELS,
            error=str(error),
        ), 409 if isinstance(error, AdminAccountConflict) else 400
    flash("Compte utilisateur créé.", "success")
    return redirect(url_for("admin.users_page"), code=303)


@admin_bp.post("/users/<int:user_id>/active")
def set_user_active_web(user_id: int):
    state = request.form.get("active")
    if state not in {"0", "1"}:
        abort(400, description="État de compte invalide.")
    try:
        changed = set_managed_user_active(
            int(current_user.get_id()), user_id, state == "1"
        )
    except PermissionError:
        abort(403)
    except AdminAccountConflict as error:
        abort(409, description=str(error))
    except ValueError:
        abort(400)
    if not changed:
        abort(404)
    flash("Activation du compte mise à jour. Ses données sont conservées.", "success")
    return redirect(url_for("admin.users_page"), code=303)
