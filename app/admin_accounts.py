"""Administration des identités, sans accès aux candidatures ni aux secrets IMAP."""

import sqlite3

from werkzeug.security import generate_password_hash

from app.accounts import (
    CREATABLE_ROLES,
    UserInputError,
    check_promotion,
    validate_user_input,
)
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
                "SELECT u.id, u.email, u.role, u.active, u.created_at, u.promotion_id, p.name AS promotion_name FROM users u LEFT JOIN promotions p ON p.id=u.promotion_id ORDER BY u.id DESC"
            ).fetchall()
        )


def create_managed_user(
    actor_id: int,
    email: str,
    password: str,
    role: str = "student",
    promotion_id: int | None = None,
) -> int:
    # Rejeter avant le calcul coûteux, puis revérifier dans la transaction d'écriture.
    with get_connection() as connection:
        _check_admin(connection, actor_id)
        check_promotion(connection, promotion_id)
    email = validate_user_input(email, password, role)
    if role not in CREATABLE_ROLES:
        raise UserInputError("Choisir un compte apprenant ou équipe pédagogique.")
    try:
        password_hash = generate_password_hash(password, method="scrypt")
    except Exception:
        raise AdminAccountStorageError("Création momentanément indisponible.") from None
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        _check_admin(connection, actor_id)
        check_promotion(connection, promotion_id)
        try:
            cursor = connection.execute(
                "INSERT INTO users (email, password_hash, role, promotion_id) VALUES (?, ?, ?, ?)",
                (email, password_hash, role, promotion_id),
            )
        except sqlite3.IntegrityError:
            raise AdminAccountConflict(
                "Un compte utilise déjà cette adresse email."
            ) from None
        if cursor.lastrowid is None:
            raise RuntimeError("Identifiant utilisateur indisponible.")
        return cursor.lastrowid


def list_managed_promotions(actor_id: int) -> list[sqlite3.Row]:
    with get_connection() as connection:
        connection.execute("BEGIN")
        _check_admin(connection, actor_id)
        return list(
            connection.execute(
                "SELECT id, name FROM promotions ORDER BY name COLLATE NOCASE, id"
            ).fetchall()
        )


def create_managed_promotion(actor_id: int, name: str) -> int:
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        _check_admin(connection, actor_id)
        name = " ".join(name.split())
        if not 1 <= len(name) <= 100:
            raise UserInputError(
                "Le libellé de promotion doit contenir entre 1 et 100 caractères."
            )
        try:
            cursor = connection.execute(
                "INSERT INTO promotions (name) VALUES (?)", (name,)
            )
        except sqlite3.IntegrityError:
            raise AdminAccountConflict("Cette promotion existe déjà.") from None
        if cursor.lastrowid is None:
            raise RuntimeError("Identifiant de promotion indisponible.")
        return cursor.lastrowid


def set_managed_user_promotion(
    actor_id: int, target_id: int, promotion_id: int | None
) -> bool:
    target_id = require_user_id(target_id)
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        _check_admin(connection, actor_id)
        check_promotion(connection, promotion_id)
        cursor = connection.execute(
            "UPDATE users SET promotion_id=? WHERE id=?", (promotion_id, target_id)
        )
        return cursor.rowcount == 1


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
