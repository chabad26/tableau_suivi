"""Backoffice des comptes ; toutes les vues sont réservées aux administrateurs."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.accounts import UserInputError
from app.admin_accounts import (
    AdminAccountConflict,
    AdminAccountStorageError,
    create_managed_promotion,
    create_managed_user,
    list_managed_promotions,
    list_managed_users,
    set_managed_user_active,
    set_managed_user_promotion,
)
from app.web.auth import login_manager

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
ROLE_LABELS = {
    "student": "Apprenant",
    "trainer": "Formateur",
    "admin": "Équipe pédagogique",
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
        promotions = list_managed_promotions(int(current_user.get_id()))
    except PermissionError:
        abort(403)
    return render_template(
        "admin/users.html", users=users, promotions=promotions, role_labels=ROLE_LABELS
    )


def _promotion_id(value: str) -> int | None:
    if not value:
        return None
    try:
        identifier = int(value)
    except ValueError:
        raise UserInputError("Promotion invalide.") from None
    if not 0 < identifier < 2**63:
        raise UserInputError("Promotion invalide.")
    return identifier


def _user_form(**values):
    try:
        promotions = list_managed_promotions(int(current_user.get_id()))
    except PermissionError:
        abort(403)
    return render_template(
        "admin/user_new.html",
        promotions=promotions,
        role_labels={role: ROLE_LABELS[role] for role in ("student", "admin")},
        **values,
    )


@admin_bp.get("/users/new")
def new_user():
    return _user_form(
        email="", selected_role="student", selected_promotion="", error=None
    )


@admin_bp.post("/users")
def create_user_web():
    email = request.form.get("email", "").strip()
    role = request.form.get("role", "student")
    password = request.form.get("password", "")
    confirmation = request.form.get("password_confirm", "")
    promotion = request.form.get("promotion_id", "").strip()
    try:
        if password != confirmation:
            raise UserInputError("Les mots de passe ne correspondent pas.")
        create_managed_user(
            int(current_user.get_id()),
            email,
            password,
            role,
            promotion_id=_promotion_id(promotion),
        )
    except PermissionError:
        abort(403)
    except AdminAccountStorageError:
        abort(
            503, description="Création momentanément indisponible. Réessayer plus tard."
        )
    except (UserInputError, AdminAccountConflict) as error:
        return _user_form(
            email=email,
            selected_role=role,
            selected_promotion=promotion,
            error=str(error),
        ), 409 if isinstance(error, AdminAccountConflict) else 400
    flash("Compte utilisateur créé.", "success")
    return redirect(url_for("admin.users_page"), code=303)


@admin_bp.post("/promotions")
def create_promotion_web():
    try:
        create_managed_promotion(
            int(current_user.get_id()), request.form.get("name", "")
        )
    except PermissionError:
        abort(403)
    except (UserInputError, AdminAccountConflict) as error:
        flash(str(error), "error")
        return users_page(), 409 if isinstance(error, AdminAccountConflict) else 400
    flash("Promotion créée. Vous pouvez l'affecter aux comptes.", "success")
    return redirect(url_for("admin.users_page"), code=303)


@admin_bp.post("/users/<int:user_id>/promotion")
def set_user_promotion_web(user_id: int):
    try:
        changed = set_managed_user_promotion(
            int(current_user.get_id()),
            user_id,
            _promotion_id(request.form.get("promotion_id", "").strip()),
        )
    except PermissionError:
        abort(403)
    except UserInputError as error:
        abort(400, description=str(error))
    except ValueError:
        abort(400)
    if not changed:
        abort(404)
    flash("Promotion du compte mise à jour.", "success")
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
