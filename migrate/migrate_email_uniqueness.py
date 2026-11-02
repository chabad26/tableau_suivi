"""Migration de l'unicité des emails vers (user_id, message_id)."""

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.settings import DATABASE_PATH


def connect_database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row

    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")

    return connection


def has_composite_unique(connection: sqlite3.Connection) -> bool:
    """Vérifie la présence de UNIQUE(user_id, message_id)."""

    indexes = connection.execute("PRAGMA index_list(emails)").fetchall()

    for index in indexes:
        if not index["unique"]:
            continue

        name = str(index["name"])

        # Le nom vient de SQLite, pas d'une entrée utilisateur.
        columns = connection.execute(f"PRAGMA index_info('{name}')").fetchall()

        column_names = [str(column["name"]) for column in columns]

        if column_names == ["user_id", "message_id"]:
            return True

    return False


def check_preconditions(connection: sqlite3.Connection) -> int:
    """Refuse une migration qui pourrait perdre des données."""

    columns = {
        str(row["name"])
        for row in connection.execute("PRAGMA table_info(emails)").fetchall()
    }

    required = {
        "id",
        "user_id",
        "message_id",
        "application_id",
        "mailbox",
        "sender",
        "subject",
        "received_at",
        "detected_status",
        "score",
        "body",
    }

    missing = required - columns

    if missing:
        raise RuntimeError(f"Colonnes manquantes : {sorted(missing)}")

    unowned = connection.execute(
        """
        SELECT COUNT(*)
        FROM emails
        WHERE user_id IS NULL
        """
    ).fetchone()[0]

    if unowned:
        raise RuntimeError(
            f"{unowned} email(s) n'ont pas de propriétaire. "
            "Effectue d'abord la migration historique."
        )

    unknown_users = connection.execute(
        """
        SELECT COUNT(*)
        FROM emails AS e
        LEFT JOIN users AS u
          ON u.id = e.user_id
        WHERE u.id IS NULL
        """
    ).fetchone()[0]

    if unknown_users:
        raise RuntimeError(
            f"{unknown_users} email(s) possèdent un identifiant utilisateur inexistant."
        )

    mismatches = connection.execute(
        """
        SELECT COUNT(*)
        FROM emails AS e
        LEFT JOIN applications AS a
          ON a.id = e.application_id
        WHERE e.application_id IS NOT NULL
          AND (
              a.id IS NULL
              OR a.user_id IS NULL
              OR a.user_id != e.user_id
          )
        """
    ).fetchone()[0]

    if mismatches:
        raise RuntimeError(
            f"{mismatches} email(s) sont associés "
            "à une candidature absente ou d'un autre utilisateur."
        )

    # Cette migration connaît les triggers de notre schéma actuel.
    # Si un autre trigger a été ajouté, nous préférons arrêter
    # plutôt que de le supprimer silencieusement.
    triggers = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'trigger'
          AND tbl_name = 'emails'
        """
    ).fetchall()

    expected_triggers = {
        "emails_application_insert",
        "emails_application_update",
        "emails_owner_insert",
        "emails_owner_update",
    }

    unexpected = {str(row["name"]) for row in triggers} - expected_triggers

    if unexpected:
        raise RuntimeError(f"Triggers inconnus sur emails : {sorted(unexpected)}")

    count = connection.execute("SELECT COUNT(*) FROM emails").fetchone()[0]

    return int(count)


def backup_database(path: Path) -> Path:
    """Sauvegarde SQLite cohérente avant modification."""

    backup_dir = path.parent.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")

    backup_path = backup_dir / (f"{path.stem}_before_email_unique_{timestamp}.sqlite")

    try:
        with sqlite3.connect(path) as source:
            with sqlite3.connect(backup_path) as destination:
                source.backup(destination)
    except Exception:
        backup_path.unlink(missing_ok=True)
        raise

    return backup_path


def migrate(connection: sqlite3.Connection) -> int:
    """Reconstruit emails dans une transaction atomique."""

    connection.execute("BEGIN IMMEDIATE")

    try:
        if has_composite_unique(connection):
            connection.rollback()
            return 0

        expected_count = check_preconditions(connection)

        connection.execute("""
            CREATE TABLE emails_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                user_id INTEGER NOT NULL,

                message_id TEXT NOT NULL,

                application_id INTEGER,

                mailbox TEXT NOT NULL,

                sender TEXT,
                subject TEXT,

                received_at TEXT NOT NULL,

                detected_status TEXT NOT NULL,

                score INTEGER NOT NULL,

                body TEXT,

                UNIQUE(user_id, message_id),

                FOREIGN KEY(user_id)
                    REFERENCES users(id),

                FOREIGN KEY(application_id)
                    REFERENCES applications(id)
                    ON DELETE SET NULL
            )
        """)

        connection.execute("""
            INSERT INTO emails_new (
                id,
                user_id,
                message_id,
                application_id,
                mailbox,
                sender,
                subject,
                received_at,
                detected_status,
                score,
                body
            )
            SELECT
                id,
                user_id,
                message_id,
                application_id,
                mailbox,
                sender,
                subject,
                received_at,
                detected_status,
                score,
                body
            FROM emails
        """)

        copied_count = connection.execute("SELECT COUNT(*) FROM emails_new").fetchone()[
            0
        ]

        if copied_count != expected_count:
            raise RuntimeError("Le nombre d'emails copiés ne correspond pas.")

            # Ce trigger appartient à applications, mais fait
        # référence à emails.
        #
        # Il doit être supprimé avant la reconstruction
        # pour éviter une erreur lors du renommage.
        connection.execute("""
            DROP TRIGGER IF EXISTS detach_application_emails
        """)

        # Les triggers directement associés à emails
        # disparaîtront avec l'ancienne table.
        connection.execute("DROP TABLE emails")

        connection.execute("ALTER TABLE emails_new RENAME TO emails")

        # On restaure le comportement historique :
        # supprimer une candidature ne supprime pas ses emails.
        connection.execute("""
            CREATE TRIGGER detach_application_emails
            BEFORE DELETE ON applications
            BEGIN
                UPDATE emails
                SET application_id = NULL
                WHERE application_id = OLD.id;
            END
        """)

        # Index de recherche existants.
        connection.execute("""
            CREATE INDEX idx_emails_message_id
            ON emails(message_id)
        """)

        connection.execute("""
            CREATE INDEX idx_emails_application_received
            ON emails(application_id, received_at DESC)
        """)

        connection.execute("""
            CREATE INDEX idx_emails_user_application
            ON emails(user_id, application_id)
        """)

        # Vérification d'appartenance à chaque insertion.
        connection.execute("""
            CREATE TRIGGER emails_owner_insert
            BEFORE INSERT ON emails
            WHEN NEW.application_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM applications
                  WHERE id = NEW.application_id
                    AND user_id = NEW.user_id
              )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Application does not belong to email owner'
                );
            END
        """)

        # Même protection lors des modifications.
        connection.execute("""
            CREATE TRIGGER emails_owner_update
            BEFORE UPDATE ON emails
            WHEN NEW.application_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM applications
                  WHERE id = NEW.application_id
                    AND user_id = NEW.user_id
              )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Application does not belong to email owner'
                );
            END
        """)

        # Si une candidature change de propriétaire, ses emails
        # doivent être détachés au préalable.
        connection.execute("""
            CREATE TRIGGER applications_email_owner_guard
            BEFORE UPDATE OF user_id ON applications
            WHEN EXISTS (
                SELECT 1
                FROM emails
                WHERE application_id = OLD.id
                  AND user_id != NEW.user_id
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Application owner conflicts with linked emails'
                );
            END
        """)

        remaining = connection.execute("SELECT COUNT(*) FROM emails").fetchone()[0]

        if remaining != expected_count:
            raise RuntimeError("Des emails ont disparu pendant la migration.")

        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()

        if foreign_key_errors:
            raise RuntimeError("La vérification des clés étrangères a échoué.")

        if not has_composite_unique(connection):
            raise RuntimeError("La nouvelle contrainte UNIQUE est absente.")

        connection.commit()
        return expected_count

    except Exception:
        connection.rollback()
        raise


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migration de l'unicité des Message-ID."
    )

    parser.add_argument(
        "--apply", action="store_true", help="Applique la migration après sauvegarde."
    )

    args = parser.parse_args()

    path = DATABASE_PATH.resolve()

    if not path.is_file():
        parser.error(f"Base introuvable : {path}")

    with connect_database(path) as connection:
        if has_composite_unique(connection):
            print("✅ La contrainte composite existe déjà.")
            return

        count = check_preconditions(connection)

    print()
    print("📨 MIGRATION DES EMAILS")
    print(f"Base : {path}")
    print(f"Messages à préserver : {count}")
    print("Ancienne contrainte : UNIQUE(message_id)")
    print("Nouvelle contrainte : UNIQUE(user_id, message_id)")

    if not args.apply:
        print()
        print("🧪 Simulation validée. Aucune modification.")
        return

    print()
    print("⚠️ Flask et le worker doivent être arrêtés.")
    confirmation = input("Saisis MIGRER pour confirmer : ").strip()

    if confirmation != "MIGRER":
        print("❌ Migration annulée.")
        return

    backup_path = backup_database(path)

    print(f"💾 Sauvegarde : {backup_path}")

    with connect_database(path) as connection:
        migrated = migrate(connection)

    print(f"✅ Migration terminée : {migrated} emails préservés.")
    print("✅ Unicité désormais définie par utilisateur.")


if __name__ == "__main__":
    main()
