"""Conversion des messages partagée par Gmail et Microsoft Graph."""

import html
import re
from email.message import EmailMessage


def html_to_text(value: str) -> str:
    """Conserve les règles de nettoyage historiques des deux API."""
    value = re.sub(r"<style.*?>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<script.*?>.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"</p>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n\s*\n+", "\n\n", value)
    return value.strip()


def build_email_message(
    sender: str, subject: str, message_id: str, body: str, *, date: str = ""
) -> EmailMessage:
    """Construit le message transmis au moteur de classification existant."""
    message = EmailMessage()
    for name, value in (
        ("From", sender),
        ("Subject", subject),
        ("Date", date),
        ("Message-ID", message_id),
    ):
        if value:
            message[name] = value
    message.set_content(body)
    return message
