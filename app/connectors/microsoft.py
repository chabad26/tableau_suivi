from __future__ import annotations

import os
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import msal
import requests
from dotenv import load_dotenv

from app.classifier import detect_status, score_message
from app.connectors.common import build_email_message as _build_email_message
from app.connectors.common import html_to_text as _html_to_text
from app.mail_filters import should_analyze_email
from app.models import DetectedEmail
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


def html_to_text(value: str) -> str:
    """Point d'entrée historique vers la conversion commune."""
    return _html_to_text(value)


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
        result = app.acquire_token_interactive(
            scopes=SCOPES, redirect_uri="http://localhost"
        )

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


def parse_date(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    except ValueError:
        return datetime.now().astimezone()


def build_email_message(
    sender: str, subject: str, message_id: str, body: str
) -> EmailMessage:
    return _build_email_message(sender, subject, message_id, body)


def scan_microsoft(since: datetime) -> list[DetectedEmail]:

    token = get_access_token()

    headers = {"Authorization": (f"Bearer {token}"), "Accept": "application/json"}

    since_iso = since.astimezone().isoformat()

    url = "https://graph.microsoft.com/v1.0/me/messages"

    params: dict[str, str] | None = {
        "$top": "100",
        "$select": ("id,internetMessageId,receivedDateTime,from,subject,body"),
        "$filter": (f"receivedDateTime ge {since_iso}"),
        "$orderby": ("receivedDateTime desc"),
    }

    detected_emails: list[DetectedEmail] = []

    total_seen = 0

    print()
    print("📨 Microsoft Graph")

    while url:
        response = requests.get(url, headers=headers, params=params, timeout=30)

        response.raise_for_status()

        data = response.json()

        messages = data.get("value", [])

        for item in messages:
            total_seen += 1

            sender_data = item.get("from", {}).get("emailAddress", {})

            sender_name = str(sender_data.get("name", ""))

            sender_address = str(sender_data.get("address", ""))

            if sender_name:
                sender = f"{sender_name} <{sender_address}>"
            else:
                sender = sender_address

            subject = str(item.get("subject", ""))

            message_id = str(item.get("internetMessageId", ""))

            graph_id = str(item.get("id", ""))

            if not message_id:
                message_id = f"microsoft:{graph_id}"

            received_at = parse_date(str(item.get("receivedDateTime", "")))

            body_data = item.get("body", {})

            body = str(body_data.get("content", ""))

            content_type = str(body_data.get("contentType", "")).casefold()

            if content_type == "html":
                body = html_to_text(body)

            if not should_analyze_email(
                sender,
                subject,
                body,
            ):
                continue

            email_message = build_email_message(
                sender=sender, subject=subject, message_id=message_id, body=body
            )

            score, reasons, normalized_body = score_message(email_message)

            if score < 5:
                continue

            status = detect_status(subject, normalized_body)

            detected_emails.append(
                DetectedEmail(
                    mailbox="Microsoft Graph",
                    date=received_at,
                    sender=sender,
                    subject=subject,
                    message_id=message_id,
                    score=score,
                    status=status,
                    reasons=reasons,
                    body=normalized_body,
                )
            )

        url = data.get("@odata.nextLink", "")

        #
        # nextLink contient déjà tous les paramètres.
        #
        params = None

    print(f"  Parcourus : {total_seen}")

    print(f"  Détectés  : {len(detected_emails)}")

    return detected_emails
