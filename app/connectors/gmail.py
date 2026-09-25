from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from app.settings import (
    GMAIL_CREDENTIALS_FILE,
    GMAIL_TOKEN_FILE,
)


SCOPES = [
    "https://mail.google.com/"
]

CREDENTIALS_FILE = (
    GMAIL_CREDENTIALS_FILE
)

TOKEN_FILE = (
    GMAIL_TOKEN_FILE
)


def get_credentials() -> Credentials:
    credentials: Credentials | None = None

    if TOKEN_FILE.exists():
        credentials = (
            Credentials
            .from_authorized_user_file(
                str(TOKEN_FILE),
                SCOPES,
            )
        )

    if (
        credentials
        and credentials.expired
        and credentials.refresh_token
    ):
        credentials.refresh(
            Request()
        )

    if (
        not credentials
        or not credentials.valid
    ):
        flow = (
            InstalledAppFlow
            .from_client_secrets_file(
                str(CREDENTIALS_FILE),
                SCOPES,
            )
        )

        credentials = (
            flow.run_local_server(
                port=0
            )
        )

    TOKEN_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    TOKEN_FILE.write_text(
        credentials.to_json(),
        encoding="utf-8",
    )

    return credentials