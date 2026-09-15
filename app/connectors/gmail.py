from __future__ import annotations

import base64
import html
import re

from datetime import datetime
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
# Les stubs tiers référencent oauth2client.Credentials, absent ici.
from googleapiclient.discovery import build  # pyright: ignore[reportUnknownVariableType]

from app.classifier import (
    detect_status,
    score_message,
)
from app.models import DetectedEmail

from app.mail_filters import (
    should_analyze_email,
)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
]

CREDENTIALS_FILE = Path(
    "credentials.json"
)

TOKEN_FILE = Path(
    "token.json"
)


def get_credentials() -> Credentials:
    credentials: Credentials | None = None

    if TOKEN_FILE.exists():
        # google-auth n'annote pas les paramètres filename et scopes.
        credentials = Credentials.from_authorized_user_file(  # pyright: ignore[reportUnknownMemberType]
            str(TOKEN_FILE),
            SCOPES,
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
        flow = InstalledAppFlow.from_client_secrets_file(
            str(CREDENTIALS_FILE),
            SCOPES,
        )

        credentials = flow.run_local_server(
            port=0,
        )

        TOKEN_FILE.write_text(
            # Le paramètre facultatif strip n'est pas annoté dans google-auth.
            credentials.to_json(),  # pyright: ignore[reportUnknownMemberType]
            encoding="utf-8",
        )

    return credentials


def decode_base64_url(
    data: str,
) -> str:
    if not data:
        return ""

    try:
        decoded = base64.urlsafe_b64decode(
            data + "=" * (-len(data) % 4)
        )

        return decoded.decode(
            "utf-8",
            errors="replace",
        )

    except Exception:
        return ""


def html_to_text(
    value: str,
) -> str:
    value = re.sub(
        r"<style.*?>.*?</style>",
        " ",
        value,
        flags=re.IGNORECASE | re.DOTALL,
    )

    value = re.sub(
        r"<script.*?>.*?</script>",
        " ",
        value,
        flags=re.IGNORECASE | re.DOTALL,
    )

    value = re.sub(
        r"<br\s*/?>",
        "\n",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(
        r"</p>",
        "\n",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(
        r"<[^>]+>",
        " ",
        value,
    )

    value = html.unescape(
        value
    )

    value = re.sub(
        r"[ \t]+",
        " ",
        value,
    )

    value = re.sub(
        r"\n\s*\n+",
        "\n\n",
        value,
    )

    return value.strip()

def extract_body(
    payload: dict[str, Any],
) -> str:

    mime_type = str(
        payload.get(
            "mimeType",
            "",
        )
    ).casefold()

    body = payload.get(
        "body",
        {},
    )

    data = body.get(
        "data",
        "",
    )

    if mime_type == "text/plain" and data:
        return decode_base64_url(
            data
        ).strip()

    if mime_type == "text/html" and data:
        return html_to_text(
            decode_base64_url(
                data
            )
        )

    parts = payload.get(
        "parts",
        [],
    )

    plain_texts: list[str] = []
    html_texts: list[str] = []

    for part in parts:
        part_mime = str(
            part.get(
                "mimeType",
                "",
            )
        ).casefold()

        extracted = extract_body(
            part
        )

        if not extracted:
            continue

        if part_mime == "text/plain":
            plain_texts.append(
                extracted
            )

        elif part_mime == "text/html":
            html_texts.append(
                extracted
            )

        elif part_mime.startswith(
            "multipart/"
        ):
            #
            # Le contenu a déjà été nettoyé
            # récursivement.
            #
            plain_texts.append(
                extracted
            )

    if plain_texts:
        return "\n\n".join(
            plain_texts
        ).strip()

    if html_texts:
        return "\n\n".join(
            html_texts
        ).strip()

    return ""

def get_header(
    headers: list[dict[str, Any]],
    name: str,
) -> str:
    wanted = name.casefold()

    for header in headers:
        header_name = str(
            header.get(
                "name",
                "",
            )
        )

        if header_name.casefold() == wanted:
            return str(
                header.get(
                    "value",
                    "",
                )
            )

    return ""


def parse_google_date(
    value: str,
) -> datetime:
    try:
        return parsedate_to_datetime(
            value
        )

    except (TypeError, ValueError):
        pass

    return datetime.now().astimezone()


def build_email_message(
    sender: str,
    subject: str,
    date: str,
    message_id: str,
    body: str,
) -> EmailMessage:
    message = EmailMessage()

    if sender:
        message["From"] = sender

    if subject:
        message["Subject"] = subject

    if date:
        message["Date"] = date

    if message_id:
        message["Message-ID"] = message_id

    message.set_content(
        body
    )

    return message


def scan_gmail(
    since: datetime,
) -> list[DetectedEmail]:

    credentials = get_credentials()

    service: Any = build(
        "gmail",
        "v1",
        credentials=credentials,
        cache_discovery=False,
    )

    query = (
        f"after:{since.strftime('%Y/%m/%d')}"
    )

    detected_emails: list[DetectedEmail] = []

    page_token: str | None = None

    total_seen = 0

    print()
    print("📧 Gmail API")

    while True:
        request = (
            service.users()
            .messages()
            .list(
                userId="me",
                q=query,
                pageToken=page_token,
                maxResults=100,
            )
        )

        result = request.execute()

        messages = result.get(
            "messages",
            [],
        )

        for message_ref in messages:
            gmail_id = message_ref.get(
                "id"
            )

            if not gmail_id:
                continue

            total_seen += 1

            data = (
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=gmail_id,
                    format="full",
                )
                .execute()
            )

            payload = data.get(
                "payload",
                {},
            )

            headers = payload.get(
                "headers",
                [],
            )

            sender = get_header(
                headers,
                "From",
            )

            subject = get_header(
                headers,
                "Subject",
            )

            date_header = get_header(
                headers,
                "Date",
            )

            message_id = get_header(
                headers,
                "Message-ID",
            )

            #
            # Certains messages peuvent ne pas avoir
            # de Message-ID RFC.
            #
            if not message_id:
                message_id = (
                    f"gmail:{gmail_id}"
                )

            body = extract_body(
                payload
            )

            email_message = build_email_message(
                sender=sender,
                subject=subject,
                date=date_header,
                message_id=message_id,
                body=body,
            )

            if not should_analyze_email(
                sender=sender,
                subject=subject,
                body=body,
            ):
                continue

            score, reasons, normalized_body = (
                score_message(
                    email_message
                )
            )

            if score < 5:
                continue

            status = detect_status(
                subject,
                normalized_body,
            )

            detected_emails.append(
                DetectedEmail(
                    mailbox="Gmail API",
                    date=parse_google_date(
                        date_header
                    ),
                    sender=sender,
                    subject=subject,
                    message_id=message_id,
                    score=score,
                    status=status,
                    reasons=reasons,
                    body=normalized_body,
                )
            )

        page_token = result.get(
            "nextPageToken"
        )

        if not page_token:
            break

    print(
        f"  Parcourus  : {total_seen}"
    )

    print(
        f"  Détectés   : "
        f"{len(detected_emails)}"
    )

    return detected_emails
