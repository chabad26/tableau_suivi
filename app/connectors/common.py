"""Conversion des messages partagée par les connecteurs mail."""

import html
import re
from email.message import EmailMessage
from email.header import decode_header, make_header


def decode_mime_header(value: str) -> str:
    if not value:
        return ""

    try:
        return str(
            make_header(
                decode_header(value)
            )
        ).strip()
    except (LookupError, UnicodeError):
        return value.strip()

def extract_html_preheader(
    value: str,
) -> str:
    """
    Extrait le texte d'un préheader HTML masqué.
    Les plateformes de recrutement y placent souvent
    un résumé très exploitable.
    """

    patterns = [
        r"""
        <(?:div|span)
        [^>]*?
        style=["'][^"']*
        (?:display\s*:\s*none|max-height\s*:\s*0|visibility\s*:\s*hidden)
        [^"']*["']
        [^>]*>
        (.*?)
        </(?:div|span)>
        """,
        r"""
        <(?:div|span)
        [^>]*?
        aria-hidden=["']true["']
        [^>]*>
        (.*?)
        </(?:div|span)>
        """,
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            value,
            flags=re.IGNORECASE
            | re.DOTALL
            | re.VERBOSE,
        )

        if not match:
            continue

        preheader = re.sub(
            r"<[^>]+>",
            " ",
            match.group(1),
        )

        preheader = html.unescape(
            preheader
        )

        preheader = re.sub(
            r"\s+",
            " ",
            preheader,
        ).strip()

        if preheader:
            return preheader

    return ""

def html_to_text(value: str) -> str:
    preheader = extract_html_preheader(
        value
    )

    value = re.sub(
        r"<style.*?>.*?</style>",
        " ",
        value,
        flags=re.I | re.S,
    )

    value = re.sub(
        r"<script.*?>.*?</script>",
        " ",
        value,
        flags=re.I | re.S,
    )

    value = re.sub(
        r"<br\s*/?>",
        "\n",
        value,
        flags=re.I,
    )

    value = re.sub(
        r"</p>",
        "\n",
        value,
        flags=re.I,
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

    value = value.strip()

    if (
        preheader
        and preheader.casefold()
        not in value.casefold()
    ):
        return (
            preheader
            + "\n\n"
            + value
        )

    return value


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

def sanitize_header_value(
    value: str,
) -> str:
    return " ".join(
        value
        .replace("\r", " ")
        .replace("\n", " ")
        .split()
    )