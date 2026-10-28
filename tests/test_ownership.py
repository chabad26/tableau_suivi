"""Tests de préparation du schéma multi-utilisateur."""

from app import database
from app.ownership import OWNED_TABLES, init_ownership
from tests.helpers import OfflineCase


class OwnershipTests(OfflineCase):
    def test_ownership_columns_exist(self):
        init_ownership()

        with database.get_connection() as connection:
            for table in OWNED_TABLES:
                columns = connection.execute(f"PRAGMA table_info({table})").fetchall()

                names = {row["name"] for row in columns}

                self.assertIn("user_id", names, msg=f"Colonne absente : {table}")

    def test_migration_is_idempotent(self):
        init_ownership()
        init_ownership()

        with database.get_connection() as connection:
            for table in OWNED_TABLES:
                columns = connection.execute(f"PRAGMA table_info({table})").fetchall()

                user_columns = [row for row in columns if row["name"] == "user_id"]

                self.assertEqual(len(user_columns), 1)

    def test_existing_applications_are_preserved(self):
        application_id = self.application(company="Entreprise historique")

        init_ownership()

        with database.get_connection() as connection:
            application = connection.execute(
                """
                SELECT id, company, user_id
                FROM applications
                WHERE id = ?
                """,
                (application_id,),
            ).fetchone()

        self.assertIsNotNone(application)

        assert application is not None

        self.assertEqual(application["company"], "Entreprise historique")

        self.assertIsNone(application["user_id"])
