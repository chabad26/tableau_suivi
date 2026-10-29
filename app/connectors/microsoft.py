from __future__ import annotations

from typing import Any

import msal

from app.oauth_store import locked_oauth_account, read_oauth_cache, write_oauth_cache
from app.settings import (
    MICROSOFT_AUTHORITY,
    MICROSOFT_CLIENT_ID,
    MICROSOFT_TOKEN_CACHE_FILE,
)

AUTHORITY = MICROSOFT_AUTHORITY

SCOPES = ["https://outlook.office.com/IMAP.AccessAsUser.All"]

TOKEN_CACHE_FILE = MICROSOFT_TOKEN_CACHE_FILE


def load_cache() -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()

    if TOKEN_CACHE_FILE.exists():
        cache.deserialize(TOKEN_CACHE_FILE.read_text(encoding="utf-8"))

    return cache


def save_cache(cache: msal.SerializableTokenCache) -> None:
    if not cache.has_state_changed:
        return

    TOKEN_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    TOKEN_CACHE_FILE.write_text(cache.serialize(), encoding="utf-8")


def get_access_token() -> str:
    if not MICROSOFT_CLIENT_ID:
        raise RuntimeError("MICROSOFT_CLIENT_ID non configuré.")

    cache = load_cache()

    app = msal.PublicClientApplication(
        client_id=MICROSOFT_CLIENT_ID, authority=AUTHORITY, token_cache=cache
    )

    result: dict[str, Any] | None = None

    accounts = app.get_accounts()

    if accounts:
        result = app.acquire_token_silent(scopes=SCOPES, account=accounts[0])

    if not result:
        result = app.acquire_token_interactive(scopes=SCOPES)

    save_cache(cache)

    if not result:
        raise RuntimeError("Microsoft n'a retourné aucun résultat OAuth.")

    access_token = result.get("access_token")

    if not access_token:
        error = result.get("error", "erreur inconnue")

        description = result.get("error_description", "")

        raise RuntimeError(
            f"Authentification Microsoft impossible : {error} | {description}"
        )

    return str(access_token)


def _get_owned_microsoft_token_unlocked(
    user_id: int, account_id: int, expected_email: str
) -> str:
    """Obtient un jeton Microsoft depuis le cache du compte IMAP."""

    if not MICROSOFT_CLIENT_ID:
        raise RuntimeError("MICROSOFT_CLIENT_ID non configuré.")

    content = read_oauth_cache(user_id, account_id, "microsoft")

    if not content:
        raise RuntimeError(
            "Autorisation Microsoft absente. Ce compte doit être connecté via OAuth."
        )

    cache = msal.SerializableTokenCache()

    try:
        cache.deserialize(content)
    except (ValueError, TypeError) as error:
        raise RuntimeError("Cache Microsoft invalide.") from error

    application = msal.PublicClientApplication(
        client_id=MICROSOFT_CLIENT_ID, authority=AUTHORITY, token_cache=cache
    )

    expected = expected_email.strip().casefold()

    # Nous cherchons une identité explicitement correspondante.
    accounts = [
        account
        for account in application.get_accounts()
        if str(account.get("username", "")).strip().casefold() == expected
    ]

    if len(accounts) != 1:
        raise RuntimeError(
            "Aucune identité Microsoft unique ne correspond à la boîte IMAP configurée."
        )

    result = application.acquire_token_silent(scopes=SCOPES, account=accounts[0])

    if not result or not result.get("access_token"):
        raise RuntimeError(
            "Jeton Microsoft indisponible ou expiré. "
            "Une nouvelle autorisation est nécessaire."
        )

    claims = result.get("id_token_claims")

    if isinstance(claims, dict):
        claim_email = (
            str(claims.get("preferred_username") or claims.get("email") or "")
            .strip()
            .casefold()
        )

        if claim_email and claim_email != expected:
            raise RuntimeError(
                "L'identité Microsoft retournée ne correspond "
                "pas à la boîte configurée."
            )

    if cache.has_state_changed:
        write_oauth_cache(user_id, account_id, "microsoft", cache.serialize())

    return str(result["access_token"])


def get_owned_microsoft_token(
    user_id: int, account_id: int, expected_email: str
) -> str:
    """Lit et renouvelle le cache MSAL sous verrou."""

    with locked_oauth_account(user_id, account_id, "microsoft"):
        return _get_owned_microsoft_token_unlocked(user_id, account_id, expected_email)
