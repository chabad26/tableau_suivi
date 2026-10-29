import imaplib

from app.connectors.gmail import get_credentials, get_owned_gmail_token
from app.connectors.microsoft import get_access_token, get_owned_microsoft_token
from app.owned_applications import require_user_id
from app.owned_imap import get_user_imap_account


def xoauth2_string(username: str, access_token: str) -> bytes:
    return (f"user={username}\x01auth=Bearer {access_token}\x01\x01").encode("utf-8")


def authenticate_imap(
    connection: imaplib.IMAP4, provider: str, username: str, password: str | None
) -> None:

    if provider == "gmail":
        credentials = get_credentials()

        token = credentials.token

        if not token:
            raise RuntimeError("Jeton Gmail indisponible.")

        connection.authenticate("XOAUTH2", lambda _: xoauth2_string(username, token))

        return

    if provider == "microsoft":
        token = get_access_token()

        connection.authenticate("XOAUTH2", lambda _: xoauth2_string(username, token))

        return

    if not password:
        raise RuntimeError("Mot de passe IMAP absent.")

    connection.login(username, password)


def authenticate_owned_imap(
    connection: imaplib.IMAP4,
    user_id: int,
    account_id: int,
    username: str,
    password: str | None,
) -> None:
    """Authentifie une boîte IMAP appartenant à un utilisateur."""

    user_id = require_user_id(user_id)

    account = get_user_imap_account(user_id, account_id)

    if account is None or not bool(account["enabled"]):
        raise ValueError("Compte IMAP introuvable ou désactivé.")

    expected_username = str(account["username"]).strip()

    if username.strip().casefold() != expected_username.casefold():
        raise ValueError("Identifiant IMAP incohérent.")

    provider = str(account["provider"] or "imap").casefold()

    auth_method = str(account["auth_method"] or "password").casefold()

    if auth_method == "oauth2":
        if provider == "gmail":
            token = get_owned_gmail_token(user_id, account_id, expected_username)

        elif provider == "microsoft":
            token = get_owned_microsoft_token(user_id, account_id, expected_username)

        else:
            raise ValueError("Fournisseur OAuth non pris en charge.")

        connection.authenticate(
            "XOAUTH2", lambda _: xoauth2_string(expected_username, token)
        )

        return

    if auth_method != "password":
        raise ValueError("Méthode d'authentification inconnue.")

    if provider in {"gmail", "microsoft"}:
        raise ValueError("Ce fournisseur doit utiliser OAuth2.")

    if not password:
        raise RuntimeError("Mot de passe IMAP absent.")

    connection.login(expected_username, password)
