from __future__ import annotations

import msal

from app.oauth_store import locked_oauth_account, read_oauth_cache, write_oauth_cache
from app.settings import MICROSOFT_AUTHORITY, MICROSOFT_CLIENT_ID

AUTHORITY = MICROSOFT_AUTHORITY

SCOPES = ["https://outlook.office.com/IMAP.AccessAsUser.All"]


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
        client_id=MICROSOFT_CLIENT_ID,
        authority=AUTHORITY,
        token_cache=cache,
        timeout=15,
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
