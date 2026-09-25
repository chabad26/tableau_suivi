from __future__ import annotations

from typing import Any

import msal

from app.settings import (
    MICROSOFT_AUTHORITY,
    MICROSOFT_CLIENT_ID,
    MICROSOFT_TOKEN_CACHE_FILE,
)


AUTHORITY = MICROSOFT_AUTHORITY

SCOPES = [
    "https://outlook.office.com/IMAP.AccessAsUser.All",
]

TOKEN_CACHE_FILE = MICROSOFT_TOKEN_CACHE_FILE


def load_cache() -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()

    if TOKEN_CACHE_FILE.exists():
        cache.deserialize(
            TOKEN_CACHE_FILE.read_text(
                encoding="utf-8",
            )
        )

    return cache


def save_cache(
    cache: msal.SerializableTokenCache,
) -> None:
    if not cache.has_state_changed:
        return

    TOKEN_CACHE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    TOKEN_CACHE_FILE.write_text(
        cache.serialize(),
        encoding="utf-8",
    )


def get_access_token() -> str:
    if not MICROSOFT_CLIENT_ID:
        raise RuntimeError(
            "MICROSOFT_CLIENT_ID non configuré."
        )

    cache = load_cache()

    app = msal.PublicClientApplication(
        client_id=MICROSOFT_CLIENT_ID,
        authority=AUTHORITY,
        token_cache=cache,
    )

    result: dict[str, Any] | None = None

    accounts = app.get_accounts()

    if accounts:
        result = app.acquire_token_silent(
            scopes=SCOPES,
            account=accounts[0],
        )

    if not result:
        result = app.acquire_token_interactive(
            scopes=SCOPES,
        )

    save_cache(cache)

    if not result:
        raise RuntimeError(
            "Microsoft n'a retourné "
            "aucun résultat OAuth."
        )

    access_token = result.get(
        "access_token"
    )

    if not access_token:
        error = result.get(
            "error",
            "erreur inconnue",
        )

        description = result.get(
            "error_description",
            "",
        )

        raise RuntimeError(
            "Authentification Microsoft "
            f"impossible : {error} | "
            f"{description}"
        )

    return str(access_token)