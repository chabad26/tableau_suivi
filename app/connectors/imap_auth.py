import base64
import imaplib

from app.connectors.gmail import get_credentials
from app.connectors.microsoft import get_access_token


def xoauth2_string(
    username: str,
    access_token: str,
) -> bytes:
    value = (
        f"user={username}"
        f"\x01auth=Bearer {access_token}"
        f"\x01\x01"
    )

    return base64.b64encode(
        value.encode("utf-8")
    )


def authenticate_imap(
    connection: imaplib.IMAP4,
    provider: str,
    username: str,
    password: str | None,
) -> None:

    if provider == "gmail":
        credentials = get_credentials()

        token = credentials.token

        if not token:
            raise RuntimeError(
                "Jeton Gmail indisponible."
            )

        auth = xoauth2_string(
            username,
            token,
        )

        connection.authenticate(
            "XOAUTH2",
            lambda _: auth,
        )

        return

    if provider == "microsoft":
        token = get_access_token()

        auth = xoauth2_string(
            username,
            token,
        )

        connection.authenticate(
            "XOAUTH2",
            lambda _: auth,
        )

        return

    if not password:
        raise RuntimeError(
            "Mot de passe IMAP absent."
        )

    connection.login(
        username,
        password,
    )