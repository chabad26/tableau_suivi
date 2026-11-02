"""Administration des identités, sans accès aux candidatures ni aux secrets IMAP."""

import sqlite3

from werkzeug.security import generate_password_hash

from app.accounts import validate_user_input
from app.database import get_connection
from app.owned_applications import require_user_id


class AdminAccountConflict(ValueError):
    """Opération administrative refusée avec un message affichable."""


class AdminAccountStorageError(RuntimeError):
    """Échec technique dont les détails ne doivent pas exposer un secret."""


def _check_admin(connection: sqlite3.Connection, actor_id: int) -> None:
    actor_id = require_user_id(actor_id)
    actor = connection.execute(
        "SELECT 1 FROM users WHERE id=? AND role='admin' AND active=1", (actor_id,)
    ).fetchone()
    if actor is None:
        raise PermissionError("Administration réservée aux administrateurs actifs.")


def list_managed_users(actor_id: int) -> list[sqlite3.Row]:
    """Ne sélectionne jamais les hashes des mots de passe."""
    with get_connection() as connection:
        connection.execute("BEGIN")
        _check_admin(connection, actor_id)
        return list(
            connection.execute(
                "SELECT id, email, role, active, created_at FROM users ORDER BY id DESC"
            ).fetchall()
        )


def create_managed_user(
    actor_id: int, email: str, password: str, role: str = "student"
) -> int:
    # Rejeter avant le calcul coûteux, puis revérifier dans la transaction d'écriture.
    with get_connection() as connection:
        _check_admin(connection, actor_id)
    email = validate_user_input(email, password, role)
    try:
        password_hash = generate_password_hash(password, method="scrypt")
    except Exception:
        raise AdminAccountStorageError("Création momentanément indisponible.") from None
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        _check_admin(connection, actor_id)
        try:
            cursor = connection.execute(
                "INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)",
                (email, password_hash, role),
            )
        except sqlite3.IntegrityError:
            raise AdminAccountConflict(
                "Un compte utilise déjà cette adresse email."
            ) from None
        if cursor.lastrowid is None:
            raise RuntimeError("Identifiant utilisateur indisponible.")
        return cursor.lastrowid


def set_managed_user_active(actor_id: int, target_id: int, active: bool) -> bool:
    """Action idempotente : réactiver/désactiver sans supprimer aucune donnée."""
    target_id = require_user_id(target_id)
    if type(active) is not bool:
        raise ValueError("État de compte invalide.")
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        _check_admin(connection, actor_id)
        if actor_id == target_id and not active:
            raise AdminAccountConflict(
                "Vous ne pouvez pas désactiver votre propre compte."
            )
        cursor = connection.execute(
            "UPDATE users SET active=? WHERE id=?", (int(active), target_id)
        )
        return cursor.rowcount == 1
