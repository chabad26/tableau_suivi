#!/usr/bin/env python3

"""Attribution contrôlée des anciens comptes IMAP."""

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.settings import DATABASE_PATH


def connect_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def list_accounts() -> None:
    """Affiche les configurations IMAP et leurs propriétaires."""

    connection = connect_db()

    try:
        rows = connection.execute(
            """
            SELECT
                a.id,
                a.email,
                a.provider,
                a.auth_method,
                a.enabled,
                a.user_id,
                u.email AS owner_email
            FROM imap_accounts AS a
            LEFT JOIN users AS u
              ON u.id = a.user_id
            ORDER BY a.id
            """
        ).fetchall()

        print("\n📬 Comptes IMAP enregistrés\n")

        if not rows:
            print("Aucun compte IMAP.")
            return

        for row in rows:
            owner = row["owner_email"] or "SANS PROPRIÉTAIRE"

            print(
                f"ID {row['id']:>3} | "
                f"{row['email']} | "
                f"{row['provider'] or 'imap'} | "
                f"{row['auth_method']} | "
                f"Propriétaire : {owner}"
            )
    finally:
        connection.close()


def find_target(connection: sqlite3.Connection, email: str) -> sqlite3.Row:
    user = connection.execute(
        """
        SELECT id, email, role
        FROM users
        WHERE email = ? COLLATE NOCASE
          AND active = 1
        """,
        (email.strip(),),
    ).fetchone()

    if user is None:
        raise ValueError("Compte utilisateur introuvable ou désactivé.")

    return user


def check_accounts(
    connection: sqlite3.Connection, account_ids: list[int]
) -> list[sqlite3.Row]:
    """Vérifie que les comptes sélectionnés sont encore disponibles."""

    if not account_ids:
        raise ValueError("Aucun compte IMAP sélectionné.")

    if len(account_ids) != len(set(account_ids)):
        raise ValueError("Identifiants IMAP en double.")

    if any(account_id <= 0 for account_id in account_ids):
        raise ValueError("Identifiant IMAP invalide.")

    placeholders = ", ".join("?" for _ in account_ids)

    rows = connection.execute(
        f"""
        SELECT id, email, user_id
        FROM imap_accounts
        WHERE id IN ({placeholders})
        ORDER BY id
        """,
        account_ids,
    ).fetchall()

    if len(rows) != len(account_ids):
        raise ValueError("Certains identifiants IMAP sont introuvables.")

    already_owned = [row["id"] for row in rows if row["user_id"] is not None]

    if already_owned:
        raise ValueError(
            "Comptes déjà attribués : " + ", ".join(map(str, already_owned))
        )

    return list(rows)


def backup_database(path: Path) -> Path:
    """Crée une sauvegarde SQLite cohérente avant migration."""

    backup_dir = path.parent.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")

    destination_path = backup_dir / (
        f"{path.stem}_pre_imap_ownership_{timestamp}.sqlite"
    )

    source = sqlite3.connect(path)
    destination = sqlite3.connect(destination_path)

    try:
        source.backup(destination)
    except Exception:
        destination.close()
        destination_path.unlink(missing_ok=True)
        raise
    finally:
        source.close()
        destination.close()

    print(f"💾 Sauvegarde : {destination_path}")

    return destination_path


def assign_accounts(email: str, account_ids: list[int]) -> int:
    """Attribue les comptes en une seule transaction."""

    connection = connect_db()

    try:
        # Réservation de l'écriture dès le départ.
        connection.execute("BEGIN IMMEDIATE")

        target = find_target(connection, email)
        check_accounts(connection, account_ids)

        placeholders = ", ".join("?" for _ in account_ids)

        cursor = connection.execute(
            f"""
            UPDATE imap_accounts
            SET user_id = ?
            WHERE id IN ({placeholders})
              AND user_id IS NULL
            """,
            (int(target["id"]), *account_ids),
        )

        if cursor.rowcount != len(account_ids):
            raise RuntimeError("Tous les comptes n'ont pas été attribués.")

        connection.commit()
        return cursor.rowcount

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migration des comptes IMAP historiques."
    )

    parser.add_argument("--list", action="store_true", help="Liste les comptes IMAP")

    parser.add_argument("--email", help="Email du propriétaire destinataire")

    parser.add_argument(
        "--ids", type=int, nargs="+", help="Identifiants IMAP à attribuer"
    )

    parser.add_argument(
        "--apply", action="store_true", help="Applique réellement la migration"
    )

    args = parser.parse_args()

    if not DATABASE_PATH.is_file():
        parser.error(f"Base de données introuvable : {DATABASE_PATH}")

    if args.list:
        list_accounts()
        return

    if not args.email or not args.ids:
        parser.error("--email et --ids sont obligatoires pour préparer une migration.")

    connection = connect_db()

    try:
        target = find_target(connection, args.email)
        accounts = check_accounts(connection, args.ids)

        target_email = str(target["email"])

        print()
        print("=" * 60)
        print("           ATTRIBUTION DES COMPTES IMAP")
        print("=" * 60)

        print(f"👤 Propriétaire : {target_email}")
        print(f"🆔 ID utilisateur : {target['id']}")

        print("\nComptes sélectionnés :")

        for account in accounts:
            print(f"  📬 [{account['id']}] {account['email']}")

        print("\nInchangés :")
        print("  🔐 Mots de passe et keyring")
        print("  🔄 Curseurs de synchronisation")
        print("  ⚙️ Configuration des serveurs")
        print("  👥 Comptes appartenant à d'autres utilisateurs")

    finally:
        connection.close()

    if not args.apply:
        print("\n🧪 SIMULATION : aucune modification.")
        return

    print("\n⚠️ Arrête Flask et le worker avant de continuer.")

    confirmation = input(f"Saisis {target_email} pour confirmer : ").strip()

    if confirmation != target_email:
        print("❌ Migration annulée.")
        return

    backup_path = backup_database(DATABASE_PATH)

    try:
        count = assign_accounts(target_email, args.ids)
    except Exception:
        print("❌ Migration annulée.")
        print(f"💾 Sauvegarde disponible : {backup_path}")
        raise

    print(f"\n✅ {count} compte(s) IMAP attribué(s).")
    print(f"💾 Sauvegarde disponible : {backup_path}")
    print("\n🔐 Aucun mot de passe n'a été déplacé.")


if __name__ == "__main__":
    main()
