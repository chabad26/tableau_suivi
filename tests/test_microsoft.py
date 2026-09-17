from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import msal
import requests

from app.settings import (
    MICROSOFT_AUTHORITY,
    MICROSOFT_CLIENT_ID,
    MICROSOFT_TOKEN_CACHE_FILE,
)

CLIENT_ID = MICROSOFT_CLIENT_ID

AUTHORITY = MICROSOFT_AUTHORITY

SCOPES = ["Mail.Read"]

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
    if not CLIENT_ID:
        raise RuntimeError("MICROSOFT_CLIENT_ID non configuré dans .env.")
    cache = load_cache()

    app = msal.PublicClientApplication(
        client_id=CLIENT_ID, authority=AUTHORITY, token_cache=cache
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
        raise RuntimeError(
            "Authentification Microsoft impossible : "
            f"{result.get('error')} | "
            f"{result.get('error_description')}"
        )

    return str(access_token)


def main() -> None:
    token = get_access_token()

    response = requests.get(
        "https://graph.microsoft.com/v1.0/me/messages",
        headers={"Authorization": (f"Bearer {token}")},
        params={
            "$top": "10",
            "$select": ("id,internetMessageId,receivedDateTime,from,subject"),
            "$orderby": ("receivedDateTime desc"),
        },
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    messages = data.get("value", [])

    print(f"{len(messages)} mails récupérés")

    for message in messages:
        sender = message.get("from", {}).get("emailAddress", {})

        sender_name = sender.get("name", "")

        sender_address = sender.get("address", "")

        print()
        print(message.get("receivedDateTime", "-"))

        print(f"{sender_name} <{sender_address}>")

        print(message.get("subject", "-"))

        print(f"Message-ID : {message.get('internetMessageId', '-')}")


if __name__ == "__main__":
    main()
