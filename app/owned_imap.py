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
