from __future__ import annotations

import email
import imaplib
import ssl
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import Message
from email.utils import parsedate_to_datetime
from app.database import (
    get_enabled_imap_accounts,
    update_imap_account_health,
)
from app.secrets import get_imap_password
from app.classifier import (
    detect_status,
    score_message,
)
from app.mail_filters import (
    should_analyze_email,
)
from app.models import DetectedEmail
from app.settings import (
    IMAP_ENABLED,
    IMAP_FOLDER,
    IMAP_HOST,
    IMAP_PASSWORD,
    IMAP_PORT,
    IMAP_USERNAME,
)
from app.connectors.common import (
    build_email_message,
    decode_mime_header,
    html_to_text,
    sanitize_header_value,
)
import traceback

class ImapAuthenticationError(Exception):
    pass
@dataclass(frozen=True)
class ImapAccount:
    account_id: int | None
    key: str
    label: str
    host: str
    port: int
    use_ssl: bool
    username: str
    password: str
    folder: str

def get_imap_accounts() -> list[ImapAccount]:
    accounts: list[ImapAccount] = []

    for row in get_enabled_imap_accounts():
        account_id = int(row["id"])

        password = get_imap_password(
            account_id
        )

        if not password:
            print(
                f"⚠ Mot de passe IMAP absent : "
                f"{row['email']}"
            )
            continue

        accounts.append(
            ImapAccount(
                account_id=account_id,
                key=f"db:{account_id}",
                label=str(row["email"]),
                host=str(row["host"]),
                port=int(row["port"]),
                use_ssl=bool(row["use_ssl"]),
                username=str(row["username"]),
                password=password,
                folder=str(
                    row["folder"]
                    or "INBOX"
                ),
            )
        )

    # Compatibilité avec l'ancien compte .env.
    #
    # Dès qu'on aura migré tous les comptes vers SQLite/keyring,
    # on pourra supprimer cette partie.
    if (
        not accounts
        and IMAP_ENABLED
        and IMAP_HOST
        and IMAP_USERNAME
        and IMAP_PASSWORD
    ):
        accounts.append(
            ImapAccount(
                account_id=None,
                key="legacy-env",
                label=IMAP_USERNAME,
                host=IMAP_HOST,
                port=IMAP_PORT,
                use_ssl=True,
                username=IMAP_USERNAME,
                password=IMAP_PASSWORD,
                folder=IMAP_FOLDER,
            )
        )

    return accounts

def get_message_body(
    message: Message,
) -> str:
    if message.is_multipart():
        plain_parts: list[str] = []
        html_parts: list[str] = []

        for part in message.walk():
            disposition = str(
                part.get(
                    "Content-Disposition",
                    "",
                )
            ).casefold()

            if "attachment" in disposition:
                continue

            content_type = part.get_content_type()

            if content_type not in {
                "text/plain",
                "text/html",
            }:
                continue

            payload = part.get_payload(
                decode=True
            )

            # get_payload peut aussi renvoyer un Message : decode exige des octets.
            if not isinstance(payload, bytes) or not payload:
                continue

            charset = (
                part.get_content_charset()
                or "utf-8"
            )

            text = payload.decode(
                charset,
                errors="replace",
            )

            if content_type == "text/plain":
                plain_parts.append(text)
            else:
                html_parts.append(text)

        if plain_parts:
            return "\n\n".join(
                plain_parts
            ).strip()

        if html_parts:
            return html_to_text(
                "\n\n".join(
                    html_parts
                )
            )

        return ""

    payload = message.get_payload(
        decode=True
    )

    if not isinstance(payload, bytes) or not payload:
        return ""

    charset = (
        message.get_content_charset()
        or "utf-8"
    )

    text = payload.decode(
        charset,
        errors="replace",
    )

    if (
        message.get_content_type()
        == "text/html"
    ):
        return html_to_text(text)

    return text.strip()

def connect_imap(
    account: ImapAccount,
) -> imaplib.IMAP4:
    for attempt in range(3):
        try:
            if account.use_ssl:
                context = ssl.create_default_context()

                return imaplib.IMAP4_SSL(
                    account.host,
                    account.port,
                    ssl_context=context,
                    timeout=15,
                )

            return imaplib.IMAP4(
                account.host,
                account.port,
                timeout=15,
            )

        except ssl.SSLCertVerificationError:
            raise RuntimeError(
                "Certificat TLS IMAP non valide."
            ) from None

        except (
            ConnectionResetError,
            TimeoutError,
            ssl.SSLEOFError,
        ):
            if attempt == 2:
                raise RuntimeError(
                    "Connexion IMAP interrompue "
                    "après 3 tentatives."
                ) from None

            time.sleep(
                attempt + 1
            )

    raise RuntimeError(
        "Connexion IMAP impossible."
    )


def scan_imap(
    since: datetime,
) -> list[DetectedEmail]:
    detected: list[DetectedEmail] = []

    accounts = get_imap_accounts()

    for account in accounts:
        try:
            emails = scan_imap_account(
                account,
                since,
            )

            detected.extend(
                emails
            )

            if account.account_id is not None:
                update_imap_account_health(
                    account.account_id,
                    "connected",
                    None,
                )

        except ImapAuthenticationError:
            if account.account_id is not None:
                update_imap_account_health(
                    account.account_id,
                    "auth_error",
                    "Identifiants refusés",
                )

            print()
            print(
                f"⚠ IMAP {account.label} "
                "authentification refusée"
            )

        except Exception as error:
            if account.account_id is not None:
                update_imap_account_health(
                    account.account_id,
                    "error",
                    "Connexion ou lecture impossible",
                )

            print()
            print(
                f"⚠ IMAP {account.label} "
                f"indisponible "
                f"({type(error).__name__})"
            )

    return detected

def scan_imap_account(
    account: ImapAccount,
    since: datetime,
) -> list[DetectedEmail]:
    detected: list[DetectedEmail] = []

    connection = connect_imap(
        account
    )

    try:
        connection.login(
            account.username,
            account.password,
        )
    
        status, _ = connection.select(
            account.folder,
            readonly=True,
        )

        if status != "OK":
            raise RuntimeError(
                "Dossier IMAP inaccessible."
            )

        imap_date = since.strftime(
            "%d-%b-%Y"
        )

        status, data = connection.uid(
            "search",
            None,  # type: ignore[arg-type]
            "SINCE",
            imap_date,
        )

        if status != "OK":
            raise RuntimeError(
                "Recherche IMAP impossible."
            )

        message_ids = (
            data[0].split()
            if data and data[0]
            else []
        )

        print()
        print(
            f"📨 IMAP — {account.label}"
        )

        total_seen = 0

        for imap_uid in message_ids:
            total_seen += 1

            try:
                status, raw_data = connection.uid(
                    "fetch",
                    imap_uid,
                    "(RFC822)",
                )

                if status != "OK":
                    continue

                raw_message = None

                for item in raw_data:
                    if (
                        isinstance(item, tuple)
                        and len(item) >= 2
                        and isinstance(item[1], bytes)
                    ):
                        raw_message = item[1]
                        break

                if not raw_message:
                    continue

                message = email.message_from_bytes(
                    raw_message
                )

                sender = decode_mime_header(
                    str(
                        message.get(
                            "From",
                            "",
                        )
                    )
                )

                subject = decode_mime_header(
                    str(
                        message.get(
                            "Subject",
                            "",
                        )
                    )
                )

                date_header = str(
                    message.get(
                        "Date",
                        "",
                    )
                )

                try:
                    date = parsedate_to_datetime(
                        date_header
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    date = datetime.now(
                        timezone.utc
                    )

                if date.tzinfo is None:
                    date = date.replace(
                        tzinfo=timezone.utc
                    )

                if (
                    date.astimezone(timezone.utc)
                    < since.astimezone(timezone.utc)
                ):
                    continue

                message_id = str(
                    message.get(
                        "Message-ID",
                        "",
                    )
                ).strip()

                if not message_id:
                    message_id = (
                        f"imap:{account.key}:"
                        f"{imap_uid.decode()}"
                    )

                body = get_message_body(
                    message
                )

                if not should_analyze_email(
                    sender,
                    subject,
                    body,
                ):
                    continue

                sender = sanitize_header_value(
                    sender
                )

                subject = sanitize_header_value(
                    subject
                )

                message_id = sanitize_header_value(
                    message_id
                )

                date_header = sanitize_header_value(
                    date_header
                )

                normalized_message = build_email_message(
                    sender=sender,
                    subject=subject,
                    message_id=message_id,
                    body=body,
                    date=date_header,
                )

                (
                    score,
                    reasons,
                    normalized_body,
                ) = score_message(
                    normalized_message
                )

                if score < 5:
                    continue

                status_value = detect_status(
                    subject,
                    normalized_body,
                )

                detected.append(
                    DetectedEmail(
                        mailbox=f"IMAP {account.label}",
                        date=date,
                        sender=sender,
                        subject=subject,
                        message_id=message_id,
                        score=score,
                        status=status_value,
                        reasons=reasons,
                        body=normalized_body,
                    )
                )

            except Exception as error:
                print(
                    f"  ⚠ UID {imap_uid.decode()} ignoré "
                    f"({type(error).__name__}: {error})"
                )
                continue
                print(
                    f"  Parcourus : {total_seen}"
                )

        print(
            f"  Détectés  : {len(detected)}"
        )
        print(
            f"  Parcourus : {total_seen}"
        )

    except imaplib.IMAP4.error as error:
        raise ImapAuthenticationError(
            "Authentification IMAP refusée."
        ) from error
    
    finally:
        try:
            connection.logout()
        except Exception:
            pass

    return detected