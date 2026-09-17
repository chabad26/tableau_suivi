from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Les stubs tiers référencent oauth2client.Credentials, absent ici.
# L'exception porte sur l'import ; les appels Gmail restent typés.
from googleapiclient.discovery import (
    build,  # pyright: ignore[reportUnknownVariableType]
)

from app.settings import GMAIL_CREDENTIALS_FILE, GMAIL_TOKEN_FILE

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


CREDENTIALS_FILE = GMAIL_CREDENTIALS_FILE

TOKEN_FILE = GMAIL_TOKEN_FILE


def get_credentials() -> Credentials:
    credentials = None

    if TOKEN_FILE.exists():
        # google-auth n'annote pas les paramètres filename et scopes.
        credentials = Credentials.from_authorized_user_file(  # pyright: ignore[reportUnknownMemberType]
            str(TOKEN_FILE), SCOPES
        )

    if (
        credentials
        and credentials.expired
        # google-auth documente str | None, sans annotation de type.
        and credentials.refresh_token  # pyright: ignore[reportUnknownMemberType]
    ):
        # Le paramètre request n'est pas annoté dans google-auth.
        credentials.refresh(  # pyright: ignore[reportUnknownMemberType]
            Request()
        )

    if not credentials or not credentials.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)

        credentials = flow.run_local_server(port=0)

        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(
            # Le paramètre facultatif strip n'est pas annoté dans google-auth.
            credentials.to_json(),  # pyright: ignore[reportUnknownMemberType]
            encoding="utf-8",
        )

    return credentials


def main() -> None:
    credentials = get_credentials()

    service = build("gmail", "v1", credentials=credentials)

    result = service.users().messages().list(userId="me", maxResults=10).execute()

    messages = result.get("messages", [])

    print(f"{len(messages)} mails récupérés")

    for message in messages:
        message_id = message.get("id")
        if not message_id:
            continue
        data = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=message_id,
                format="metadata",
                metadataHeaders=["From", "Subject", "Date", "Message-ID"],
            )
            .execute()
        )

        headers = {
            item["name"]: item["value"]
            for item in data.get("payload", {}).get("headers", [])
            if "name" in item and "value" in item
        }

        print()
        print(headers.get("Date", "-"))

        print(headers.get("From", "-"))

        print(headers.get("Subject", "-"))


if __name__ == "__main__":
    main()
