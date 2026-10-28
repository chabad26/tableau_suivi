#!/usr/bin/env python3

"""Migration des candidatures et emails historiques vers un utilisateur."""

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.database import get_connection
from app.settings import DATABASE_PATH


def find_user(connection: sqlite3.Connection, email: str) -> sqlite3.Row:
    """Identifie le propriétaire sans créer de compte."""

    user = connection.execute(
        """
        SELECT id, email, role, active
        FROM users
        WHERE email = ? COLLATE NOCASE
        """,
        (email.strip(),),
    ).fetchone()

    if user is None:
        raise ValueError(f"Utilisateur introuvable : {email}")

    if not user["active"]:
        raise ValueError("Impossible de migrer vers un compte désactivé.")

    return user


def count_orphans(connection: sqlite3.Connection) -> dict[str, int]:
    """Compte les enregistrements sans propriétaire."""

    result = {}

    for table in ("applications", "emails", "imap_accounts", "jobs"):
        row = connection.execute(
            f"SELECT COUNT(*) FROM {table} WHERE user_id IS NULL"
        ).fetchone()

        result[table] = int(row[0])

    return result


def check_integrity(connection: sqlite3.Connection, target_user_id: int) -> None:
    """
    Vérifie les relations entre les emails et les candidatures.

    Aucun email ne doit être rattaché à une candidature
    appartenant à un utilisateur différent.
    """

    # Email historique rattaché à la candidature d'un autre utilisateur.
    conflicts = connection.execute(
        """
        SELECT COUNT(*)
        FROM emails AS e
        JOIN applications AS a
          ON a.id = e.application_id
        WHERE e.user_id IS NULL
          AND a.user_id IS NOT NULL
          AND a.user_id != ?
        """,
        (target_user_id,),
    ).fetchone()[0]

    if conflicts:
        raise ValueError(
            f"{conflicts} email(s) sans propriétaire sont liés "
            "à des candidatures d'autres utilisateurs."
        )

    # Email déjà attribué à quelqu'un d'autre,
    # mais lié à une candidature historique à migrer.
    conflicts = connection.execute(
        """
        SELECT COUNT(*)
        FROM emails AS e
        JOIN applications AS a
          ON a.id = e.application_id
        WHERE a.user_id IS NULL
          AND e.user_id IS NOT NULL
          AND e.user_id != ?
        """,
        (target_user_id,),
    ).fetchone()[0]

    if conflicts:
        raise ValueError(
            f"{conflicts} email(s) d'autres utilisateurs "
            "sont liés aux candidatures historiques."
        )

    # Aucune référence à une candidature inexistante.
    orphans = connection.execute(
        """
        SELECT COUNT(*)
        FROM emails AS e
        LEFT JOIN applications AS a
          ON a.id = e.application_id
        WHERE e.application_id IS NOT NULL
          AND a.id IS NULL
        """
    ).fetchone()[0]

    if orphans:
        raise ValueError(f"{orphans} email(s) référencent une candidature inexistante.")


def create_backup(database_path: Path) -> Path:
    """
    Sauvegarde SQLite cohérente, y compris en mode WAL.

    Ne pas remplacer par une simple copie du fichier .db.
    """

    backup_dir = database_path.parent.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")

    backup_path = backup_dir / (
        f"{database_path.stem}_pre_ownership_{timestamp}.sqlite"
    )

    # L'API SQLite backup prend en compte les pages
    # présentes dans le journal WAL.
    try:
        with sqlite3.connect(database_path) as source:
            with sqlite3.connect(backup_path) as destination:
                source.backup(destination)

    except Exception:
        backup_path.unlink(missing_ok=True)
        raise

    print(f"💾 Sauvegarde créée : {backup_path}")

    return backup_path


def print_report(user: sqlite3.Row, counts: dict[str, int]) -> None:
    """Affiche le récapitulatif avant migration."""

    print()
    print("=" * 55)
    print("         MIGRATION DES DONNÉES HISTORIQUES")
    print("=" * 55)

    print(f"👤 Compte : {user['email']}")
    print(f"🆔 ID     : {user['id']}")
    print(f"🔐 Rôle   : {user['role']}")

    print()
    print("Données sans propriétaire :")
    print(f"  📋 Candidatures : {counts['applications']}")
    print(f"  ✉️  Emails       : {counts['emails']}")
    print(f"  📬 Comptes IMAP : {counts['imap_accounts']}")
    print(f"  ⚙️  Jobs         : {counts['jobs']}")

    print()
    print("Actions prévues :")
    print("  ✅ Attribuer les candidatures historiques")
    print("  ✅ Attribuer les emails historiques")
    print("  ⏸️  Ne pas modifier les comptes IMAP")
    print("  ⏸️  Ne pas modifier les jobs")
    print("  🔒 Ne pas modifier les données déjà attribuées")


def apply_migration(target_user_id: int) -> tuple[int, int]:
    """
    Migration atomique.

    BEGIN IMMEDIATE empêche les autres connexions
    d'écrire pendant l'opération.
    """

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")

        user = connection.execute(
            """
            SELECT id
            FROM users
            WHERE id = ?
              AND active = 1
            """,
            (target_user_id,),
        ).fetchone()

        if user is None:
            raise ValueError("Le compte destinataire n'existe plus ou est désactivé.")

        check_integrity(connection, target_user_id)

        # 1. Attribution des candidatures sans propriétaire.
        applications = connection.execute(
            """
            UPDATE applications
            SET user_id = ?
            WHERE user_id IS NULL
            """,
            (target_user_id,),
        )

        applications_updated = applications.rowcount

        # 2. Attribution des emails sans propriétaire.
        emails = connection.execute(
            """
            UPDATE emails
            SET user_id = ?
            WHERE user_id IS NULL
            """,
            (target_user_id,),
        )

        emails_updated = emails.rowcount

        # 3. Contrôle après modification.
        inconsistent = connection.execute(
            """
            SELECT COUNT(*)
            FROM emails AS e
            JOIN applications AS a
              ON a.id = e.application_id
            WHERE e.user_id IS NOT NULL
              AND a.user_id IS NOT NULL
              AND e.user_id != a.user_id
              AND (
                  e.user_id = ?
                  OR a.user_id = ?
              )
            """,
            (target_user_id, target_user_id),
        ).fetchone()[0]

        if inconsistent:
            raise ValueError(
                f"Migration annulée : {inconsistent} "
                "liaison(s) email/candidature incohérente(s)."
            )

        connection.commit()

    return applications_updated, emails_updated


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Attribue les candidatures et emails historiques à un utilisateur existant."
        )
    )

    parser.add_argument(
        "--email", required=True, help="Adresse email du compte destinataire"
    )

    parser.add_argument(
        "--apply", action="store_true", help="Applique réellement la migration"
    )

    args = parser.parse_args()

    database_path = DATABASE_PATH.resolve()

    if not database_path.is_file():
        parser.error(f"Base SQLite introuvable : {database_path}")

    # Lecture du compte et préparation du rapport.
    with get_connection() as connection:
        user = find_user(connection, args.email)

        user_id = int(user["id"])
        email = str(user["email"])

        counts = count_orphans(connection)

        check_integrity(connection, user_id)

        print_report(user, counts)

    if not args.apply:
        print()
        print("🧪 MODE SIMULATION")
        print("Aucune donnée n'a été modifiée.")
        print()
        print("Pour appliquer la migration :")
        print(f"python migrate_legacy_data.py --email {email} --apply")
        return

    if counts["applications"] == 0 and counts["emails"] == 0:
        print()
        print("✅ Aucune candidature ou email à migrer.")
        return

    print()
    print("⚠️  ATTENTION : migration réelle demandée.")
    print("Arrête Flask et le worker avant de poursuivre.")
    print()

    confirmation = input(f"Saisis exactement {email} pour confirmer : ").strip()

    if confirmation != email:
        print("❌ Confirmation incorrecte. Migration annulée.")
        return

    # La sauvegarde est créée avant toute modification.
    backup_path = create_backup(database_path)

    print()
    print("🔄 Migration en cours...")

    try:
        applications_updated, emails_updated = apply_migration(user_id)
    except Exception:
        print("❌ Migration annulée. Transaction non validée.")
        print(f"💾 Sauvegarde disponible : {backup_path}")
        raise

    print()
    print("=" * 55)
    print("                 MIGRATION TERMINÉE")
    print("=" * 55)

    print(f"✅ Candidatures attribuées : {applications_updated}")
    print(f"✅ Emails attribués        : {emails_updated}")

    print()
    print(f"💾 Sauvegarde : {backup_path}")
    print("🎉 Tu peux maintenant retrouver tes données dans ton tableau.")


if __name__ == "__main__":
    main()
