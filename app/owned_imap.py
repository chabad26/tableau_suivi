"""Accès aux configurations IMAP avec isolation utilisateur."""

import sqlite3

from app.database import get_connection
from app.owned_applications import require_user_id


def get_user_imap_accounts(user_id: int) -> list[sqlite3.Row]:
    """Liste uniquement les comptes IMAP de cet utilisateur."""

    user_id = require_user_id(user_id)

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                email,
                provider,
                host,
                port,
                use_ssl,
                username,
                folder,
                enabled,
                created_at,
                last_status,
                last_error,
                last_checked_at,
                auth_method,
                last_uid,
                uid_validity,
                user_id
            FROM imap_accounts
            WHERE user_id = ?
            ORDER BY email COLLATE NOCASE
            """,
            (user_id,),
        ).fetchall()

    return list(rows)


def get_user_imap_account(user_id: int, account_id: int) -> sqlite3.Row | None:
    """Récupère une configuration seulement si elle appartient à l'utilisateur."""

    user_id = require_user_id(user_id)

    with get_connection() as connection:
        return connection.execute(
            """
            SELECT *
            FROM imap_accounts
            WHERE id = ?
              AND user_id = ?
            """,
            (account_id, user_id),
        ).fetchone()


def get_enabled_user_imap_accounts(user_id: int) -> list[sqlite3.Row]:
    """Comptes activés, pour le futur scanner personnel."""

    user_id = require_user_id(user_id)

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM imap_accounts
            WHERE user_id = ?
              AND enabled = 1
            ORDER BY id
            """,
            (user_id,),
        ).fetchall()

    return list(rows)


def update_user_imap_health(
    user_id: int, account_id: int, status: str, error: str | None = None
) -> bool:
    """Met à jour la santé d'un compte appartenant à l'utilisateur."""

    user_id = require_user_id(user_id)

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE imap_accounts
            SET last_status = ?,
                last_error = ?,
                last_checked_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND user_id = ?
            """,
            (status, error, account_id, user_id),
        )

        return cursor.rowcount == 1


def set_user_imap_enabled(user_id: int, account_id: int, enabled: bool) -> bool:
    """Active ou désactive uniquement un compte possédé."""

    user_id = require_user_id(user_id)

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE imap_accounts
            SET enabled = ?
            WHERE id = ?
              AND user_id = ?
            """,
            (int(enabled), account_id, user_id),
        )

        return cursor.rowcount == 1


def save_user_imap_checkpoint(
    user_id: int,
    account_id: int,
    *,
    previous_uid: int,
    previous_uid_validity: int | None,
    last_uid: int,
    uid_validity: int | None,
    expected_host: str,
    expected_username: str,
    expected_folder: str,
    expected_provider: str,
    expected_auth_method: str,
    expected_port: int,
    expected_use_ssl: bool,
) -> bool:
    """
    Enregistre un checkpoint uniquement si la configuration
    IMAP et son propriétaire n'ont pas changé.

    Retourne False en cas de modification concurrente.
    """

    user_id = require_user_id(user_id)

    if last_uid < 0 or previous_uid < 0:
        raise ValueError("UID IMAP invalide.")

    # Sans UIDVALIDITY, on ne peut pas certifier
    # que les UID correspondent à la même boîte.
    if uid_validity is None:
        return False

    if uid_validity == previous_uid_validity and last_uid < previous_uid:
        return False

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")

        cursor = connection.execute(
            """
            UPDATE imap_accounts
            SET last_uid = ?,
                uid_validity = ?
            WHERE id = ?
              AND user_id = ?
              AND enabled = 1
              AND host = ?
              AND username = ?
              AND folder = ?
              AND provider = ?
              AND auth_method = ?
              AND port = ?
              AND use_ssl = ?
              AND last_uid = ?
              AND uid_validity IS ?
              AND EXISTS (
                  SELECT 1
                  FROM users
                  WHERE users.id = imap_accounts.user_id
                    AND users.active = 1
              )
            """,
            (
                last_uid,
                uid_validity,
                account_id,
                user_id,
                expected_host,
                expected_username,
                expected_folder,
                expected_provider,
                expected_auth_method,
                expected_port,
                int(expected_use_ssl),
                previous_uid,
                previous_uid_validity,
            ),
        )

        return cursor.rowcount == 1


class ImapConfigurationError(ValueError):
    """Paramètres IMAP invalides, message affichable."""


class ImapConfigurationConflict(RuntimeError):
    """Configuration modifiée ou utilisée pendant une édition."""


class ImapSecretStorageError(RuntimeError):
    """Le gestionnaire de secrets n'a pas confirmé l'enregistrement."""


def imap_account_revision(account: sqlite3.Row) -> str:
    """Empreinte sans secret pour détecter une édition concurrente."""
    import hashlib
    import json

    fields = (
        "id",
        "user_id",
        "email",
        "provider",
        "host",
        "port",
        "use_ssl",
        "username",
        "folder",
        "auth_method",
        "enabled",
    )
    return hashlib.sha256(
        json.dumps([account[key] for key in fields]).encode()
    ).hexdigest()


def validate_imap_configuration(
    email: str,
    provider: str,
    host: str,
    port: int,
    use_ssl: bool,
    username: str,
    folder: str,
    auth_method: str,
) -> tuple:
    """Validation locale : aucune résolution DNS ni connexion au fournisseur."""
    import re

    from app.mail_providers import get_provider

    email = email.strip().casefold()
    provider = provider.strip().casefold()
    host = host.strip().casefold()
    username = username.strip()
    folder = folder.strip() or "INBOX"
    auth_method = auth_method.strip().casefold()
    if not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", email) or len(email) > 254:
        raise ImapConfigurationError("Adresse email invalide.")
    if not host or len(host) > 253 or not re.fullmatch(r"[a-z0-9.-]+", host):
        raise ImapConfigurationError("Nom du serveur IMAP invalide.")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ImapConfigurationError("Port IMAP invalide.")
    if not username or len(username) > 254 or any(ord(char) < 32 for char in username):
        raise ImapConfigurationError("Identifiant IMAP invalide.")
    if len(folder) > 255 or any(ord(char) < 32 for char in folder):
        raise ImapConfigurationError("Dossier IMAP invalide.")
    known_provider = get_provider(provider)
    if provider != "imap" and known_provider is None:
        raise ImapConfigurationError("Fournisseur IMAP inconnu.")
    expected_auth = known_provider.auth_method if known_provider else "password"
    if auth_method != expected_auth:
        raise ImapConfigurationError(
            "Méthode d’authentification incompatible avec le fournisseur."
        )
    if auth_method == "oauth2" and username.casefold() != email:
        raise ImapConfigurationError(
            "Pour OAuth, l’adresse et l’identifiant doivent correspondre."
        )
    return email, provider, host, port, int(use_ssl), username, folder, auth_method


def _check_owner_active(connection: sqlite3.Connection, user_id: int) -> None:
    if (
        connection.execute(
            "SELECT 1 FROM users WHERE id = ? AND active = 1", (user_id,)
        ).fetchone()
        is None
    ):
        raise ImapConfigurationError("Utilisateur inexistant ou désactivé.")


def _check_account_idle(
    connection: sqlite3.Connection, user_id: int, account_id: int
) -> None:
    if connection.execute(
        "SELECT 1 FROM jobs WHERE user_id = ? AND state = 'running' AND (kind = 'scan' OR kind = ?) LIMIT 1",
        (user_id, f"test:imap:{account_id}"),
    ).fetchone():
        raise ImapConfigurationConflict(
            "Un travail utilise cette boîte. Attendre sa fin avant de la modifier."
        )


def _store_password(account_id: int, password: str) -> None:
    from app.secrets import set_imap_password

    try:
        set_imap_password(account_id, password)
    except Exception:
        raise ImapSecretStorageError(
            "Le gestionnaire de secrets est indisponible. La boîte n’a pas été enregistrée."
        ) from None


def create_user_imap_account(
    user_id: int,
    *,
    email: str,
    provider: str,
    host: str,
    port: int,
    use_ssl: bool,
    username: str,
    folder: str = "INBOX",
    auth_method: str = "password",
    password: str = "",
) -> int:
    user_id = require_user_id(user_id)
    values = validate_imap_configuration(
        email, provider, host, port, use_ssl, username, folder, auth_method
    )
    if values[-1] == "password" and not password:
        raise ImapConfigurationError("Le mot de passe IMAP est obligatoire.")
    if values[-1] == "oauth2" and password:
        raise ImapConfigurationError(
            "OAuth ne nécessite pas de mot de passe dans ce formulaire."
        )
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        _check_owner_active(connection, user_id)
        cursor = connection.execute(
            "INSERT INTO imap_accounts (user_id, email, provider, host, port, use_ssl, username, folder, auth_method) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, *values),
        )
        assert cursor.lastrowid is not None
        account_id = cursor.lastrowid
        if values[-1] == "password":
            _store_password(account_id, password)
        return account_id


def update_user_imap_account(
    user_id: int,
    account_id: int,
    *,
    revision: str,
    email: str,
    provider: str,
    host: str,
    port: int,
    use_ssl: bool,
    username: str,
    folder: str = "INBOX",
    auth_method: str = "password",
    password: str = "",
) -> bool:
    user_id = require_user_id(user_id)
    values = validate_imap_configuration(
        email, provider, host, port, use_ssl, username, folder, auth_method
    )
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        _check_owner_active(connection, user_id)
        account = connection.execute(
            "SELECT * FROM imap_accounts WHERE id = ? AND user_id = ?",
            (account_id, user_id),
        ).fetchone()
        if account is None:
            return False
        if imap_account_revision(account) != revision:
            raise ImapConfigurationConflict(
                "Cette boîte a été modifiée. Recharger la page avant de réessayer."
            )
        _check_account_idle(connection, user_id, account_id)
        identity_changed = any(
            account[key] != value
            for key, value in [
                ("username", values[5]),
                ("provider", values[1]),
                ("auth_method", values[7]),
            ]
        )
        if values[-1] == "password" and identity_changed and not password:
            raise ImapConfigurationError(
                "Un nouveau mot de passe est requis pour ce changement d’identité."
            )
        if values[-1] == "oauth2" and password:
            raise ImapConfigurationError(
                "OAuth ne nécessite pas de mot de passe dans ce formulaire."
            )
        keys = (
            "email",
            "provider",
            "host",
            "port",
            "use_ssl",
            "username",
            "folder",
            "auth_method",
        )
        changed = tuple(account[key] for key in keys) != values
        connection.execute(
            "UPDATE imap_accounts SET email=?, provider=?, host=?, port=?, use_ssl=?, username=?, folder=?, auth_method=?, last_uid=CASE WHEN ? THEN 0 ELSE last_uid END, uid_validity=CASE WHEN ? THEN NULL ELSE uid_validity END, last_status=CASE WHEN ? THEN 'unknown' ELSE last_status END, last_error=NULL WHERE id=? AND user_id=?",
            (*values, changed, changed, changed or bool(password), account_id, user_id),
        )
        if values[-1] == "password" and password:
            _store_password(account_id, password)
        return True


def toggle_user_imap_account(user_id: int, account_id: int, revision: str) -> bool:
    user_id = require_user_id(user_id)
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        _check_owner_active(connection, user_id)
        account = connection.execute(
            "SELECT * FROM imap_accounts WHERE id=? AND user_id=?",
            (account_id, user_id),
        ).fetchone()
        if account is None:
            return False
        if imap_account_revision(account) != revision:
            raise ImapConfigurationConflict(
                "La configuration a changé. Actualiser la page."
            )
        _check_account_idle(connection, user_id, account_id)
        connection.execute(
            "UPDATE imap_accounts SET enabled=? WHERE id=? AND user_id=?",
            (int(not account["enabled"]), account_id, user_id),
        )
        return True
