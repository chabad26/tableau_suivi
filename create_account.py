"""Créer un compte depuis le terminal (administration locale uniquement)."""

import argparse
from getpass import getpass

from app.accounts import create_user, init_users
from app.database import init_database


def main() -> None:
    parser = argparse.ArgumentParser(description="Créer un compte Job Tracker")
    parser.add_argument("email")
    parser.add_argument(
        "--role", choices=("student", "trainer", "admin"), default="student"
    )
    args = parser.parse_args()
    password = getpass("Mot de passe (12 caractères minimum) : ")
    confirm = getpass("Confirmer le mot de passe : ")
    if password != confirm:
        parser.error("Les mots de passe ne correspondent pas")
    init_database()
    init_users()
    user_id = create_user(args.email, password, args.role)
    print(f"Compte #{user_id} créé : {args.email.strip().casefold()} ({args.role})")


if __name__ == "__main__":
    main()
