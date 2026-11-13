"""Gestion des seules boîtes IMAP de la session, sans synchronisation HTTP."""

import sqlite3

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.mail_providers import MAIL_PROVIDERS, detect_provider_smart, get_provider
from app.oauth_store import oauth_token_path
from app.owned_imap import (
    ImapConfigurationConflict,
    ImapConfigurationError,
    ImapSecretStorageError,
    create_user_imap_account,
    get_user_imap_account,
    get_user_imap_accounts,
    imap_account_revision,
    toggle_user_imap_account,
    update_user_imap_account,
)
from app.presentation import format_datetime
from app.web.jobs import submit_job

connectors_bp = Blueprint("connectors", __name__)


def owner_id() -> int:
    return int(current_user.get_id())


def owned_account(account_id: int):
    account = get_user_imap_account(owner_id(), account_id)
    if account is None:
        abort(404)
    return account


def form_configuration() -> dict:
    try:
        port = int(request.form.get("port", "993"))
    except ValueError:
        raise ImapConfigurationError("Port IMAP invalide.") from None
    return {
        "email": request.form.get("email", ""),
        "provider": request.form.get("provider", "imap"),
        "host": request.form.get("host", ""),
        "port": port,
        "use_ssl": request.form.get("use_ssl") == "on",
        "username": request.form.get("username", ""),
        "folder": request.form.get("folder", "INBOX"),
        "auth_method": request.form.get("auth_method", "password"),
        "password": request.form.get("password", ""),
    }


def save_error(error: Exception):
    if isinstance(error, ImapConfigurationError):
        abort(400, description=str(error))
    if isinstance(error, ImapConfigurationConflict):
        abort(409, description=str(error))
    if isinstance(error, ImapSecretStorageError):
        abort(
            503,
            description="Gestionnaire de secrets indisponible. Paramètres SQLite non enregistrés.",
        )
    abort(409, description="Impossible d’enregistrer cette boîte avec ces paramètres.")


@connectors_bp.get("/connectors")
@login_required
def connectors_page():
    accounts = []
    for row in get_user_imap_accounts(owner_id()):
        account = dict(row)
        account["revision"] = imap_account_revision(row)
        account["last_checked_display"] = (
            format_datetime(row["last_checked_at"])
            if row["last_checked_at"]
            else "Jamais"
        )
        account["oauth_cache_present"] = False
        if (
            row["auth_method"] == "oauth2"
            and row["enabled"]
            and row["provider"] in {"gmail", "microsoft"}
        ):
            account["oauth_cache_present"] = oauth_token_path(
                owner_id(), int(row["id"]), str(row["provider"])
            ).is_file()
        accounts.append(account)
    return render_template("connectors.html", imap_accounts=accounts)


@connectors_bp.get("/connectors/imap/add")
@login_required
def add_imap_account():
    return render_template(
        "imap_add.html", detected=None, email_address="", providers=MAIL_PROVIDERS
    )


@connectors_bp.post("/connectors/imap/detect")
@login_required
def detect_imap_account():
    email_address = request.form.get("email", "").strip()
    if not email_address or len(email_address) > 254 or "@" not in email_address:
        abort(400, description="Adresse email invalide.")
    # Les domaines réservés aux exemples ne nécessitent jamais de requête DNS.
    provider = (
        None
        if email_address.casefold().endswith(".invalid")
        else detect_provider_smart(email_address)
    )
    return render_template(
        "imap_add.html",
        detected=provider,
        email_address=email_address,
        providers=MAIL_PROVIDERS,
    )


@connectors_bp.post("/connectors/imap/add")
@login_required
def save_imap_account():
    try:
        create_user_imap_account(owner_id(), **form_configuration())
    except (
        ImapConfigurationError,
        ImapConfigurationConflict,
        ImapSecretStorageError,
        sqlite3.IntegrityError,
    ) as error:
        return save_error(error)
    flash("Boîte IMAP ajoutée à votre compte.", "success")
    return redirect(url_for("connectors.connectors_page"), code=303)


@connectors_bp.get("/connectors/imap/<int:account_id>/edit")
@login_required
def edit_imap_account(account_id: int):
    account = owned_account(account_id)
    return render_template(
        "imap_edit.html",
        account=account,
        revision=imap_account_revision(account),
        providers=MAIL_PROVIDERS,
    )


@connectors_bp.post("/connectors/imap/<int:account_id>/edit")
@login_required
def update_imap_account_web(account_id: int):
    owned_account(account_id)
    revision = request.form.get("revision", "")
    if not revision:
        abort(
            400,
            description="Version de configuration absente. Recharger le formulaire.",
        )
    try:
        changed = update_user_imap_account(
            owner_id(), account_id, revision=revision, **form_configuration()
        )
    except (
        ImapConfigurationError,
        ImapConfigurationConflict,
        ImapSecretStorageError,
        sqlite3.IntegrityError,
    ) as error:
        return save_error(error)
    if not changed:
        abort(404)
    flash("Boîte IMAP mise à jour.", "success")
    return redirect(url_for("connectors.connectors_page"), code=303)


@connectors_bp.post("/connectors/imap/<int:account_id>/toggle")
@login_required
def toggle_imap_account(account_id: int):
    owned_account(account_id)
    revision = request.form.get("revision", "")
    if not revision:
        abort(400)
    try:
        changed = toggle_user_imap_account(owner_id(), account_id, revision)
    except (ImapConfigurationError, ImapConfigurationConflict) as error:
        return save_error(error)
    if not changed:
        abort(404)
    flash("Activation de la boîte mise à jour.", "success")
    return redirect(url_for("connectors.connectors_page"), code=303)


@connectors_bp.post("/connectors/imap/<int:account_id>/test")
@login_required
def test_imap_account_web(account_id: int):
    account = owned_account(account_id)
    if not account["enabled"]:
        abort(409, description="Activer la boîte avant de la tester.")
    try:
        return submit_job(f"test:imap:{account_id}")
    except ValueError:
        abort(409, description="La configuration a changé. Actualiser la page.")
