"""Stockage privé des jetons OAuth par compte IMAP."""

import os
import tempfile
from pathlib import Path

from app import database
from app.accounts import get_user
from app.owned_applications import require_user_id
from app.owned_imap import get_user_imap_account

TOKEN_FILES = {"gmail": "gmail_token.json", "microsoft": "microsoft_cache.json"}


def oauth_account_directory(user_id: int, account_id: int, provider: str) -> Path:
    """
    Vérifie les droits et retourne le dossier OAuth.

    Ne crée pas le dossier et ne lit aucun secret.
    """

    user_id = require_user_id(user_id)

    if type(account_id) is not int or account_id <= 0:
        raise ValueError("Identifiant IMAP invalide.")

    provider = provider.strip().casefold()

    if provider not in TOKEN_FILES:
        raise ValueError("Fournisseur OAuth non reconnu.")

    user = get_user(user_id)

    if user is None or not user.active:
        raise ValueError("Utilisateur inexistant ou désactivé.")

    account = get_user_imap_account(user_id, account_id)

    if account is None:
        raise ValueError("Compte IMAP introuvable.")

    if not bool(account["enabled"]):
        raise ValueError("Compte IMAP désactivé.")

    if str(account["provider"] or "").casefold() != provider:
        raise ValueError("Fournisseur OAuth incorrect.")

    if str(account["auth_method"] or "").casefold() != "oauth2":
        raise ValueError("Ce compte n'utilise pas OAuth2.")

    return database.DATABASE_PATH.parent / "oauth" / "accounts" / str(account_id)


def oauth_token_path(user_id: int, account_id: int, provider: str) -> Path:
    """Chemin du cache OAuth après vérification des droits."""

    directory = oauth_account_directory(user_id, account_id, provider)

    filename = TOKEN_FILES[provider.strip().casefold()]

    return directory / filename


def ensure_private_directory(directory: Path) -> None:
    """Crée un répertoire privé pour les secrets."""

    directory.mkdir(parents=True, exist_ok=True, mode=0o700)

    if directory.is_symlink():
        raise RuntimeError("Répertoire OAuth symbolique interdit.")

    os.chmod(directory, 0o700)


def write_oauth_cache(
    user_id: int, account_id: int, provider: str, content: str
) -> None:
    """
    Enregistre un cache OAuth avec remplacement atomique.

    Le fichier final possède des permissions 0600.
    """

    if not content:
        raise ValueError("Cache OAuth vide.")

    path = oauth_token_path(user_id, account_id, provider)

    ensure_private_directory(path.parent)

    temporary_path: Path | None = None

    try:
        descriptor, name = tempfile.mkstemp(
            prefix=".oauth-", suffix=".tmp", dir=path.parent
        )

        temporary_path = Path(name)

        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())

        os.chmod(temporary_path, 0o600)

        temporary_path.replace(path)

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def read_oauth_cache(user_id: int, account_id: int, provider: str) -> str | None:
    """Lit un cache privé sans suivre de lien symbolique."""

    path = oauth_token_path(user_id, account_id, provider)

    if not path.exists():
        return None

    flags = os.O_RDONLY | os.O_NOFOLLOW

    descriptor = os.open(path, flags)

    with os.fdopen(descriptor, "r", encoding="utf-8") as file:
        return file.read()
