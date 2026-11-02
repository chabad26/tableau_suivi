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
