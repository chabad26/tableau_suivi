"""Comptes utilisateurs : stockage et authentification sans exposition HTTP."""

import re
import sqlite3
from dataclasses import dataclass

from werkzeug.security import check_password_hash, generate_password_hash

from app.database import get_connection


@dataclass(frozen=True)
class User:
    id: int
    email: str
    role: str
    active: bool


ROLES = frozenset({"student", "trainer", "admin"})


class UserInputError(ValueError):
    """Erreur de saisie dont le message fixe peut être affiché."""


def init_users() -> None:
    """Migration additive : aucune donnée de candidature n'est modifiée."""
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'student'
                    CHECK (role IN ('student', 'trainer', 'admin')),
                active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)


def validate_user_input(email: str, password: str, role: str = "student") -> str:
    """Valide les mêmes paramètres pour le terminal et le backoffice."""
    email = email.strip().casefold()
    if (
        not re.fullmatch(r"[^\s@<>\"']+@[^\s@<>\"']+\.[^\s@<>\"']+", email)
        or len(email) > 254
    ):
        raise UserInputError("Adresse email invalide")
    if not 12 <= len(password) <= 256:
        raise UserInputError("Le mot de passe doit contenir entre 12 et 256 caractères")
    if role not in ROLES:
        raise UserInputError("Rôle invalide")
    return email


def create_user(email: str, password: str, role: str = "student") -> int:
    email = validate_user_input(email, password, role)
    password_hash = generate_password_hash(password, method="scrypt")
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)",
            (email, password_hash, role),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("Identifiant utilisateur indisponible")
        return int(cursor.lastrowid)


def _as_user(row: sqlite3.Row | None) -> User | None:
    if row is None:
        return None
    return User(
        int(row["id"]), str(row["email"]), str(row["role"]), bool(row["active"])
    )


def get_user(user_id: int) -> User | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, email, role, active FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return _as_user(row)


def authenticate(email: str, password: str) -> User | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, email, role, active, password_hash FROM users WHERE email = ?",
            (email.strip().casefold(),),
        ).fetchone()
    if row is None or not bool(row["active"]):
        return None
    if not check_password_hash(str(row["password_hash"]), password):
        return None
    return _as_user(row)


def set_user_active(user_id: int, active: bool) -> None:
    with get_connection() as connection:
        connection.execute(
            "UPDATE users SET active = ? WHERE id = ?", (int(active), user_id)
        )
