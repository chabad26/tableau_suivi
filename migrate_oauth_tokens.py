#!/usr/bin/env python3
"""Migration contrôlée des anciens caches OAuth vers les comptes IMAP."""

from __future__ import annotations

import argparse
import imaplib
import json
import ssl
from pathlib import Path

import msal
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2.credentials import Credentials

from app.connectors.gmail import SCOPES as GMAIL_SCOPES
from app.connectors.imap_auth import xoauth2_string
from app.connectors.microsoft import SCOPES as MICROSOFT_SCOPES
from app.oauth_store import oauth_token_path, write_oauth_cache
from app.owned_imap import get_user_imap_account
from app.settings import (
    GMAIL_TOKEN_FILE,
    MICROSOFT_AUTHORITY,
    MICROSOFT_CLIENT_ID,
    MICROSOFT_TOKEN_CACHE_FILE,
)

LEGACY_FILES = {
    "gmail": GMAIL_TOKEN_FILE,
    "microsoft": MICROSOFT_TOKEN_CACHE_FILE,
}


def normalize_email(value: str) -> str:
    return value.strip().casefold()


def get_target(
    user_id: int,
    account_id: int,
    provider: str,
):
    """Vérifie le propriétaire et la configuration OAuth."""

    row = get_user_imap_account(user_id, account_id)

    if row is None:
        raise ValueError("Compte IMAP introuvable pour cet utilisateur.")

    if not bool(row["enabled"]):
        raise ValueError("Compte IMAP désactivé.")

    if normalize_email(str(row["provider"] or "")) != provider:
        raise ValueError("Fournisseur différent de celui demandé.")

    if normalize_email(str(row["auth_method"] or "")) != "oauth2":
        raise ValueError("Le compte n'utilise pas OAuth2.")

    username = normalize_email(str(row["username"]))

    if not username:
        raise ValueError("Identifiant IMAP vide.")

    # Par prudence, on refuse une configuration dans laquelle
    # l'adresse affichée et l'identifiant IMAP diffèrent.
    if normalize_email(str(row["email"])) != username:
        raise ValueError(
            "Adresse de boîte et identifiant IMAP différents. "
            "Vérification manuelle nécessaire."
        )

    return row


def read_legacy_file(path: Path) -> str:
    """Lit un ancien cache sans modifier son contenu."""

    if not path.is_file() or path.is_symlink():
        raise ValueError("Ancien cache absent ou chemin non autorisé.")

    return path.read_text(encoding="utf-8")


def check_gmail_format(content: str) -> None:
    """Contrôle uniquement le format en simulation."""

    info = json.loads(content)

    if not isinstance(info, dict):
        raise ValueError("Format du cache Gmail invalide.")

    Credentials.from_authorized_user_info(
        info,
        GMAIL_SCOPES,
    )


def verify_gmail_identity(
    content: str,
    expected_email: str,
) -> None:
    """Vérifie réellement le compte Google associé au jeton."""

    info = json.loads(content)

    credentials = Credentials.from_authorized_user_info(
        info,
        GMAIL_SCOPES,
    )

    if credentials.expired:
        if not credentials.refresh_token:
            raise RuntimeError("Jeton Gmail expiré sans refresh token.")

        try:
            credentials.refresh(Request())
        except RefreshError as error:
            raise RuntimeError(
                "Impossible de rafraîchir le jeton Gmail."
            ) from error

    if not credentials.valid or not credentials.token:
        raise RuntimeError("Jeton Gmail invalide.")

    with AuthorizedSession(credentials) as session:
        response = session.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/profile",
            timeout=15,
        )
        response.raise_for_status()
        profile = response.json()

    actual_email = normalize_email(
        str(profile.get("emailAddress", ""))
    )

    if actual_email != expected_email:
        raise RuntimeError(
            "Le jeton Gmail appartient à une autre boîte."
        )


def load_microsoft_accounts(
    content: str,
) -> tuple[msal.PublicClientApplication, list[dict]]:
    """Construit un client MSAL à partir du cache historique."""

    if not MICROSOFT_CLIENT_ID:
        raise RuntimeError("MICROSOFT_CLIENT_ID non configuré.")

    cache = msal.SerializableTokenCache()
    cache.deserialize(content)

    application = msal.PublicClientApplication(
        client_id=MICROSOFT_CLIENT_ID,
        authority=MICROSOFT_AUTHORITY,
        token_cache=cache,
    )

    return application, application.get_accounts()


def check_microsoft_identity(
    content: str,
    expected_email: str,
) -> None:
    """Refuse les caches ambigus ou associés à une autre identité."""

    _, accounts = load_microsoft_accounts(content)

    if len(accounts) != 1:
        raise RuntimeError(
            "Le cache Microsoft doit contenir exactement un compte."
        )

    username = normalize_email(
        str(accounts[0].get("username", ""))
    )

    if username != expected_email:
        raise RuntimeError(
            "Le compte Microsoft du cache ne correspond pas "
            "à la boîte IMAP configurée."
        )


def verify_microsoft_imap(
    content: str,
    expected_email: str,
    host: str,
    port: int,
) -> None:
    """
    Vérifie l'autorisation Microsoft par une connexion IMAP réelle.

    Aucun email n'est téléchargé.
    """

    application, accounts = load_microsoft_accounts(content)

    if len(accounts) != 1:
        raise RuntimeError("Cache Microsoft ambigu.")

    result = application.acquire_token_silent(
        scopes=MICROSOFT_SCOPES,
        account=accounts[0],
    )

    if not result or not result.get("access_token"):
        raise RuntimeError(
            "Jeton Microsoft indisponible. "
            "Une nouvelle autorisation est nécessaire."
        )

    token = str(result["access_token"])

    context = ssl.create_default_context()

    connection = imaplib.IMAP4_SSL(
        host,
        port,
        ssl_context=context,
        timeout=15,
    )

    try:
        connection.authenticate(
            "XOAUTH2",
            lambda _: xoauth2_string(expected_email, token),
        )

    finally:
        try:
            connection.logout()
        except Exception:
            pass


def migrate(
    user_id: int,
    account_id: int,
    provider: str,
    apply: bool,
) -> None:
    provider = provider.strip().casefold()

    if provider not in LEGACY_FILES:
        raise ValueError("Fournisseur non pris en charge.")

    row = get_target(user_id, account_id, provider)

    expected_email = normalize_email(str(row["username"]))

    source = LEGACY_FILES[provider]

    destination = oauth_token_path(
        user_id,
        account_id,
        provider,
    )

    content = read_legacy_file(source)

    if destination.is_symlink() or destination.exists():
        raise RuntimeError(
            "Un cache privé existe déjà. Migration refusée."
        )

    if provider == "gmail":
        check_gmail_format(content)
    else:
        check_microsoft_identity(content, expected_email)

    print()
    print("=" * 60)
    print("           MIGRATION OAUTH")
    print("=" * 60)

    print(f"Fournisseur : {provider}")
    print(f"Utilisateur : {user_id}")
    print(f"Compte IMAP : {account_id}")
    print(f"Adresse     : {expected_email}")
    print(f"Source      : {source}")
    print(f"Destination : {destination}")

    if not apply:
        print()
        print("🧪 SIMULATION")
        print("Format et configuration cohérents.")
        print("Identité réelle non encore vérifiée.")
        print("Aucun fichier modifié.")
        return

    print()
    print("🔎 Vérification de l'identité OAuth...")

    if provider == "gmail":
        verify_gmail_identity(
            content,
            expected_email,
        )

    else:
        if not bool(row["use_ssl"]):
            raise RuntimeError(
                "La vérification Microsoft exige IMAP SSL."
            )

        verify_microsoft_imap(
            content,
            expected_email,
            str(row["host"]),
            int(row["port"]),
        )

    # Nouvelle vérification juste avant l'écriture.
    get_target(user_id, account_id, provider)

    if destination.is_symlink() or destination.exists():
        raise RuntimeError(
            "Un cache privé est apparu pendant la migration."
        )

    write_oauth_cache(
        user_id,
        account_id,
        provider,
        content,
        overwrite=False,
    )

    print()
    print("✅ Cache privé créé.")
    print("✅ Ancien cache conservé.")
    print("🔐 Aucun jeton affiché.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migration sécurisée des anciens jetons OAuth."
    )

    parser.add_argument(
        "--user-id",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--account-id",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--provider",
        choices=("gmail", "microsoft"),
        required=True,
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Vérifie réellement l'identité et copie le cache.",
    )

    args = parser.parse_args()

    if args.apply:
        confirmation = input(
            "Saisis MIGRER pour confirmer : "
        ).strip()

        if confirmation != "MIGRER":
            print("Migration annulée.")
            return

    migrate(
        user_id=args.user_id,
        account_id=args.account_id,
        provider=args.provider,
        apply=args.apply,
    )


if __name__ == "__main__":
    main()