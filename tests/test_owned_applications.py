"""Tests d'isolation des candidatures entre utilisateurs."""

from app.owned_applications import (
    create_user_application,
    delete_user_application,
    get_user_application,
    get_user_application_emails,
    get_user_applications,
    set_user_application_status,
)
from app.extractor import job_title_score
from tests.helpers import OfflineCase


class OwnedApplicationsTests(OfflineCase):
    ALICE = 101
    BOB = 202

    def test_each_user_sees_only_their_applications(self):
        create_user_application(self.ALICE, "Entreprise Alice", "Développeuse Python")

        create_user_application(self.BOB, "Entreprise Bob", "Administrateur réseau")

        alice_rows = get_user_applications(self.ALICE)
        bob_rows = get_user_applications(self.BOB)

        self.assertEqual(len(alice_rows), 1)
        self.assertEqual(len(bob_rows), 1)

        self.assertEqual(alice_rows[0]["company"], "Entreprise Alice")

        self.assertEqual(bob_rows[0]["company"], "Entreprise Bob")

    def test_user_cannot_read_another_application(self):
        application_id = create_user_application(
            self.ALICE, "Entreprise privée", "Développeuse"
        )

        self.assertIsNotNone(get_user_application(self.ALICE, application_id))

        self.assertIsNone(get_user_application(self.BOB, application_id))

    def test_user_cannot_modify_another_status(self):
        application_id = create_user_application(
            self.ALICE, "Entreprise privée", "Développeuse"
        )

        modified = set_user_application_status(self.BOB, application_id, "REJECTED")

        self.assertFalse(modified)

        application = get_user_application(self.ALICE, application_id)

        assert application is not None

        self.assertEqual(application["manual_status"], "SENT")

    def test_user_cannot_delete_another_application(self):
        application_id = create_user_application(
            self.ALICE, "Entreprise privée", "Développeuse"
        )

        deleted = delete_user_application(self.BOB, application_id)

        self.assertFalse(deleted)

        self.assertIsNotNone(get_user_application(self.ALICE, application_id))

    def test_owner_can_delete_application(self):
        application_id = create_user_application(
            self.ALICE, "Entreprise privée", "Développeuse"
        )

        self.assertTrue(delete_user_application(self.ALICE, application_id))

        self.assertIsNone(get_user_application(self.ALICE, application_id))

    def test_user_cannot_read_another_users_emails(self):
        application_id = create_user_application(
            self.ALICE, "Entreprise privée", "Développeuse"
        )

        self.assertEqual(get_user_application_emails(self.BOB, application_id), [])

    def test_invalid_user_id_is_rejected(self):
        with self.assertRaises(ValueError):
            get_user_applications(0)

        with self.assertRaises(ValueError):
            get_user_applications(None)  # type: ignore[arg-type]

def update_user_application(
    user_id: int,
    application_id: int,
    company: str,
    job_title: str,
    source: str,
    status: str,
    note: str = "",
) -> bool:
    """Modifie une candidature uniquement si elle appartient à l'utilisateur."""

    user_id = require_user_id(user_id)

    if not company.strip():
        raise ValueError("Le nom de l'entreprise est obligatoire.")

    with get_connection() as connection:
        current = connection.execute(
            """
            SELECT company, job_title, source
            FROM applications
            WHERE id = ?
              AND user_id = ?
            """,
            (application_id, user_id),
        ).fetchone()

        if current is None:
            return False

        current_title = str(current["job_title"] or "")
        candidate_title = job_title.strip()

        # On conserve la logique de sélection du meilleur intitulé.
        new_title = (
            candidate_title
            if job_title_score(candidate_title) > job_title_score(current_title)
            else current_title
        )

        cursor = connection.execute(
            """
            UPDATE applications
            SET company = ?,
                job_title = ?,
                source = ?,
                manual_status = ?,
                manual_note = ?,
                manual_override = 1
            WHERE id = ?
              AND user_id = ?
            """,
            (
                company.strip(),
                new_title,
                source.strip() or str(current["source"] or ""),
                status,
                note,
                application_id,
                user_id,
            ),
        )

        return cursor.rowcount == 1