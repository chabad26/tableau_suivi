"""Scanner IMAP isolé par utilisateur."""

from dataclasses import dataclass, field
from datetime import datetime

from app.accounts import get_user
from app.connectors.imap import ImapAccount, scan_imap_account
from app.models import DetectedEmail
from app.owned_applications import require_user_id
from app.owned_imap import get_enabled_user_imap_accounts, get_user_imap_account
from app.secrets import get_imap_password


@dataclass
class UserScanResult:
    emails: list[DetectedEmail] = field(default_factory=list)
    scanned_accounts: int = 0
    skipped_accounts: int = 0
    errors: list[str] = field(default_factory=list)


def build_user_imap_account(user_id: int, account_id: int) -> ImapAccount:
    """
    Construit une configuration IMAP après vérification
    de son propriétaire.

    Les secrets ne sont récupérés qu'après ce contrôle.
    """

    user_id = require_user_id(user_id)

    row = get_user_imap_account(user_id, account_id)

    if row is None:
        raise ValueError("Compte IMAP introuvable.")

    if not bool(row["enabled"]):
        raise ValueError("Compte IMAP désactivé.")

    auth_method = str(row["auth_method"] or "password").casefold()

    provider = str(row["provider"] or "imap").casefold()

    # Sécurité temporaire :
    # les caches OAuth ne sont pas encore isolés.
    if auth_method != "password":
        raise ValueError(
            "Authentification OAuth2 indisponible "
            "pendant la migration multi-utilisateur."
        )

    if provider in {"gmail", "microsoft"}:
        raise ValueError(
            "Ce fournisseur nécessite une authentification "
            "qui doit encore être isolée par utilisateur."
        )

    password = get_imap_password(account_id)

    if not password:
        raise ValueError("Mot de passe IMAP absent.")

    uid_validity = int(row["uid_validity"]) if row["uid_validity"] is not None else None

    return ImapAccount(
        account_id=account_id,
        key=f"user:{user_id}:db:{account_id}",
        label=str(row["email"]),
        provider=provider,
        host=str(row["host"]),
        port=int(row["port"]),
        use_ssl=bool(row["use_ssl"]),
        username=str(row["username"]),
        auth_method=auth_method,
        password=password,
        folder=str(row["folder"] or "INBOX"),
        last_uid=int(row["last_uid"] or 0),
        uid_validity=uid_validity,
    )


def scan_user_imap(user_id: int, since: datetime) -> UserScanResult:
    """
    Analyse uniquement les comptes IMAP de user_id.

    Ne sauvegarde aucun email.
    Ne modifie pas les curseurs de synchronisation.
    """

    user_id = require_user_id(user_id)

    user = get_user(user_id)

    if user is None or not user.active:
        raise ValueError("Utilisateur inexistant ou désactivé.")

    result = UserScanResult()

    accounts = get_enabled_user_imap_accounts(user_id)

    for row in accounts:
        account_id = int(row["id"])

        try:
            account = build_user_imap_account(user_id, account_id)

        except ValueError as error:
            result.skipped_accounts += 1

            result.errors.append(f"Compte {account_id} : {error}")

            continue

        try:
            detected = scan_imap_account(account, since, persist_sync_state=False)

        except Exception as error:
            result.errors.append(
                f"Compte {account_id} : échec du scan ({type(error).__name__})"
            )

            continue

        result.emails.extend(detected)
        result.scanned_accounts += 1

    return result
