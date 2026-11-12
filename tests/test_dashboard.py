"""Dashboard chiffré, filtres et journal des statuts, sans données réelles."""

from datetime import datetime, timezone

from app.accounts import create_user, set_user_active
from app.admin_accounts import create_managed_promotion, set_managed_user_promotion
from app.dashboard import dashboard_statistics
from app.database import get_connection
from app.owned_applications import (
    create_user_application,
    delete_user_application,
    set_user_application_status,
)
from app.owned_importer import import_user_emails
from app.owned_jobs import execute_user_job
from app.ownership import init_ownership
from tests.helpers import OfflineCase, fake_email

REFERENCE = datetime(2026, 11, 30, 23, 59, tzinfo=timezone.utc)


class DashboardTests(OfflineCase):
    def setUp(self):
        super().setUp()
        self.password = "FixtureCampusPassword2026!"
        self.alice = self.login_test_user("alice@example.invalid")
        self.bob = self.create_test_user("bob@example.invalid")
        self.admin = create_user("pedagogy@example.invalid", self.password, "admin")
        self.data = create_managed_promotion(self.admin, "Data 2026–2027")
        self.grc = create_managed_promotion(self.admin, "GRC 2026–2027")
        set_managed_user_promotion(self.admin, self.alice, self.data)
        set_managed_user_promotion(self.admin, self.bob, self.grc)
        self.first = create_user_application(
            self.alice,
            "SECRET-COMPANY-ALICE",
            "SECRET-JOB",
            note="SECRET-NOTE",
            offer_text="SECRET-OFFER",
        )
        self.second = create_user_application(
            self.alice, "Another private company", "Private title"
        )
        set_user_application_status(self.alice, self.second, "REJECTED")
        self.foreign = create_user_application(
            self.bob, "SECRET-COMPANY-BOB", "Private job", status="INTERVIEW"
        )
        self.unowned = self.application(company="SECRET-LEGACY")
        with get_connection() as connection:
            connection.execute(
                "UPDATE applications SET first_seen='2026-10-31T23:30:00-02:00' WHERE id=?",
                (self.first,),
            )
            connection.execute(
                "UPDATE applications SET first_seen='2026-10-01T00:00:00+00:00' WHERE id IN (?,?)",
                (self.second, self.foreign),
            )
            connection.execute(
                "UPDATE application_status_history SET recorded_at='2026-11-12T10:00:00+00:00'"
            )

    def as_admin(self):
        client = self.app.test_client()
        self.assertEqual(
            client.post(
                "/login",
                data={"email": "pedagogy@example.invalid", "password": self.password},
            ).status_code,
            303,
        )
        return client

    def test_personal_counts_use_displayed_status_and_exclude_foreign_rows(self):
        data = dashboard_statistics(self.alice, now=REFERENCE)
        self.assertEqual(
            (
                data["total"],
                data["counts"]["SENT"],
                data["counts"]["REJECTED"],
                data["counts"]["INTERVIEW"],
            ),
            (2, 1, 1, 0),
        )
        self.assertEqual(data["accounts"], 1)
        self.assertEqual([p["name"] for p in data["promotions"]], ["Data 2026–2027"])
        page = self.client.get("/dashboard")
        self.assertEqual(page.status_code, 200)
        self.assertNotIn("GRC 2026–2027", page.text)
        self.assertNotIn("Vue campus", page.text)
        self.assertNotIn("Ajouter une formation", page.text)
        self.assertEqual(data["learners"], [])
        self.assertNotIn("Statistiques par apprenant", page.text)
        self.assertNotIn("bob@example.invalid", page.text)

    def test_campus_statistics_are_admin_only_and_filterable(self):
        data = dashboard_statistics(self.admin, scope="campus", now=REFERENCE)
        self.assertEqual((data["total"], data["accounts"]), (3, 2))
        self.assertEqual(data["counts"]["INTERVIEW"], 1)
        self.assertEqual(
            dashboard_statistics(self.admin, scope="campus", promotion=str(self.data))[
                "total"
            ],
            2,
        )
        self.assertEqual(
            dashboard_statistics(self.admin, scope="campus", promotion=str(self.grc))[
                "total"
            ],
            1,
        )
        unassigned = dashboard_statistics(
            self.admin, scope="campus", promotion="unassigned"
        )
        self.assertEqual((unassigned["total"], unassigned["accounts"]), (0, 0))
        set_managed_user_promotion(self.admin, self.bob, None)
        unassigned = dashboard_statistics(
            self.admin, scope="campus", promotion="unassigned"
        )
        self.assertEqual((unassigned["total"], unassigned["accounts"]), (1, 1))
        self.assertEqual(self.client.get("/dashboard?scope=campus").status_code, 403)
        with self.assertRaises(PermissionError):
            dashboard_statistics(self.alice, scope="campus")

    def test_pedagogical_team_personal_applications_are_not_campus_metrics(self):
        create_user_application(self.admin, "PRIVATE-STAFF-COMPANY", "Private title")
        self.assertEqual(dashboard_statistics(self.admin, scope="campus")["total"], 3)
        self.assertEqual(dashboard_statistics(self.admin)["total"], 1)
        page = self.as_admin().get("/dashboard")
        self.assertIn("Chiffres agrégés des apprenants", page.text)
        self.assertNotIn("PRIVATE-STAFF-COMPANY", page.text)

    def test_page_contains_learner_identifiers_but_no_application_details(self):
        page = self.as_admin().get("/dashboard?scope=campus")
        self.assertEqual(page.status_code, 200)
        for private in (
            "SECRET-COMPANY",
            "SECRET-JOB",
            "SECRET-NOTE",
            "SECRET-OFFER",
            "SECRET-LEGACY",
        ):
            self.assertNotIn(private, page.text)
        self.assertIn("Ajouter une formation / promotion", page.text)
        self.assertIn("alice@example.invalid", page.text)
        self.assertIn("bob@example.invalid", page.text)
        self.assertIn("/admin/users#promotions-title", page.text)

    def test_learner_rows_match_current_status_totals_and_promotion_filter(self):
        data = dashboard_statistics(self.admin, scope="campus")
        rows = {row["id"]: row for row in data["learners"]}
        self.assertEqual(set(rows), {self.alice, self.bob})
        self.assertEqual(rows[self.alice]["total"], 2)
        self.assertEqual(rows[self.alice]["counts"]["SENT"], 1)
        self.assertEqual(rows[self.alice]["counts"]["REJECTED"], 1)
        self.assertEqual(rows[self.bob]["counts"]["INTERVIEW"], 1)
        self.assertEqual(sum(row["total"] for row in rows.values()), data["total"])
        for status, total in data["counts"].items():
            self.assertEqual(sum(row["counts"][status] for row in rows.values()), total)
        filtered = dashboard_statistics(
            self.admin, scope="campus", promotion=str(self.data)
        )
        self.assertEqual([row["id"] for row in filtered["learners"]], [self.alice])
        page = self.as_admin().get(f"/dashboard?scope=campus&promotion={self.data}")
        self.assertIn("alice@example.invalid", page.text)
        self.assertNotIn("bob@example.invalid", page.text)
        self.assertEqual(dashboard_statistics(self.admin)["learners"], [])

    def test_learners_without_applications_and_inactive_accounts_are_included(self):
        empty = create_user("empty@example.invalid", self.password)
        set_user_active(self.bob, False)
        rows = {
            row["id"]: row
            for row in dashboard_statistics(self.admin, scope="campus")["learners"]
        }
        self.assertEqual(rows[empty]["total"], 0)
        self.assertEqual(sum(rows[empty]["counts"].values()), 0)
        self.assertEqual(rows[empty]["promotion"], "")
        self.assertFalse(rows[self.bob]["active"])
        self.assertEqual(rows[self.bob]["total"], 1)
        unassigned = dashboard_statistics(
            self.admin, scope="campus", promotion="unassigned"
        )
        self.assertEqual([row["id"] for row in unassigned["learners"]], [empty])

    def test_learner_table_handles_empty_promotion(self):
        promotion = create_managed_promotion(self.admin, "Promotion vide")
        page = self.as_admin().get(f"/dashboard?scope=campus&promotion={promotion}")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Aucun apprenant dans ce périmètre.", page.text)

    def test_personal_promotion_filter_never_broadens_access(self):
        self.assertEqual(
            dashboard_statistics(self.alice, promotion=str(self.data))["total"], 2
        )
        for value in (str(self.grc), "unassigned"):
            self.assertEqual(
                self.client.get(f"/dashboard?promotion={value}").status_code, 403
            )

    def test_invalid_filters_are_rejected(self):
        client = self.as_admin()
        for query in (
            "scope=invalid",
            "months=5000",
            "months=abc",
            "promotion=-1",
            "promotion=999999",
            "promotion=1%20OR%201=1",
            f"promotion={2**63}",
        ):
            with self.subTest(query=query):
                suffix = (
                    query if query.startswith("scope=") else f"scope=campus&{query}"
                )
                self.assertEqual(client.get(f"/dashboard?{suffix}").status_code, 400)
        self.assertEqual(self.app.test_client().get("/dashboard").status_code, 302)

    def test_authorization_is_rechecked_after_role_or_activation_changes(self):
        client = self.as_admin()
        with get_connection() as connection:
            connection.execute(
                "UPDATE users SET role='student' WHERE id=?", (self.admin,)
            )
        self.assertEqual(client.get("/dashboard?scope=campus").status_code, 403)
        set_user_active(self.alice, False)
        self.assertEqual(self.client.get("/dashboard").status_code, 302)
        with self.assertRaises(PermissionError):
            dashboard_statistics(self.alice)

    def test_history_and_first_seen_are_distinct_and_normalized_to_utc(self):
        data = dashboard_statistics(self.alice, now=REFERENCE)
        months = {row["month"]: row for row in data["timeline"]}
        self.assertEqual(len(months), 6)
        self.assertEqual((months["2026-10"]["new"], months["2026-11"]["new"]), (1, 1))
        self.assertEqual(months["2026-10"]["changes"], 0)
        self.assertEqual(months["2026-11"]["changes"], 1)
        self.assertEqual(months["2026-11"]["counts"]["REJECTED"], 1)
        self.assertEqual(
            len(dashboard_statistics(self.alice, months=12)["timeline"]), 12
        )

    def test_new_promotions_appear_without_changing_code_and_can_be_empty(self):
        new = create_managed_promotion(self.admin, "Nouvelle formation 2027–2028")
        page = self.as_admin().get("/dashboard?scope=campus")
        self.assertIn("Nouvelle formation 2027–2028", page.text)
        data = dashboard_statistics(self.admin, scope="campus", promotion=str(new))
        self.assertEqual((data["total"], data["accounts"]), (0, 0))

    def test_legacy_trainer_is_not_a_new_dashboard_profile(self):
        legacy = create_user("legacy-trainer@example.invalid", self.password, "trainer")
        with self.assertRaises(PermissionError):
            dashboard_statistics(legacy)
        admin = self.as_admin()
        form = admin.get("/admin/users/new")
        self.assertNotIn('value="trainer"', form.text)
        response = admin.post(
            "/admin/users",
            data={
                "email": "new-trainer@example.invalid",
                "password": self.password,
                "password_confirm": self.password,
                "role": "trainer",
            },
        )
        self.assertEqual(response.status_code, 400)


class ApplicationHistoryTests(OfflineCase):
    def setUp(self):
        super().setUp()
        self.alice = self.create_test_user("alice@example.invalid")
        self.bob = self.create_test_user("bob@example.invalid")
        self.application = create_user_application(
            self.alice, "Private company", "Private title"
        )

    def events(self):
        with get_connection() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM application_status_history WHERE application_id=? ORDER BY id",
                    (self.application,),
                )
            ]

    def test_only_effective_status_changes_are_recorded(self):
        self.assertEqual(self.events()[0]["event_kind"], "created")
        with get_connection() as connection:
            connection.execute(
                "UPDATE applications SET current_status='REJECTED',manual_note='Note' WHERE id=?",
                (self.application,),
            )
        self.assertEqual(len(self.events()), 1)
        set_user_application_status(self.alice, self.application, "INTERVIEW")
        set_user_application_status(self.alice, self.application, "INTERVIEW")
        self.assertEqual(len(self.events()), 2)
        self.assertEqual(
            (self.events()[-1]["previous_status"], self.events()[-1]["status"]),
            ("SENT", "INTERVIEW"),
        )
        with get_connection() as connection:
            connection.execute(
                "UPDATE applications SET manual_override=0 WHERE id=?",
                (self.application,),
            )
        self.assertEqual(self.events()[-1]["status"], "REJECTED")

    def test_old_records_get_one_snapshot_without_fabricating_past_changes(self):
        with get_connection() as connection:
            connection.execute("DELETE FROM application_status_history")
            connection.execute(
                "UPDATE applications SET first_seen='2020-01-01',last_update='2020-01-01' WHERE id=?",
                (self.application,),
            )
        init_ownership()
        init_ownership()
        events = self.events()
        self.assertEqual(len(events), 1)
        self.assertEqual(
            (events[0]["event_kind"], events[0]["previous_status"]), ("snapshot", None)
        )
        self.assertNotIn("2020-01-01", events[0]["recorded_at"])
        data = dashboard_statistics(self.alice)
        self.assertEqual(sum(row["changes"] for row in data["timeline"]), 0)

    def test_ownership_transfer_resets_history_and_deletion_cleans_it(self):
        set_user_application_status(self.alice, self.application, "INTERVIEW")
        with get_connection() as connection:
            connection.execute(
                "UPDATE applications SET user_id=? WHERE id=?",
                (self.bob, self.application),
            )
        events = self.events()
        self.assertEqual(len(events), 1)
        self.assertEqual(
            (events[0]["user_id"], events[0]["event_kind"]), (self.bob, "snapshot")
        )
        self.assertTrue(delete_user_application(self.bob, self.application))
        self.assertEqual(self.events(), [])

    def test_rollback_removes_uncommitted_history(self):
        with self.assertRaises(RuntimeError):
            with get_connection() as connection:
                connection.execute(
                    "UPDATE applications SET manual_status='ACCEPTED' WHERE id=?",
                    (self.application,),
                )
                raise RuntimeError("fixture rollback")
        self.assertEqual(len(self.events()), 1)

    def test_repeated_reanalysis_does_not_invent_expired_status_transitions(self):
        import_user_emails(self.alice, [fake_email("<historical@example.invalid>")])
        execute_user_job(self.alice, "reclassify")
        with get_connection() as connection:
            before = [
                tuple(row)
                for row in connection.execute(
                    "SELECT * FROM application_status_history ORDER BY id"
                )
            ]
        execute_user_job(self.alice, "reclassify")
        with get_connection() as connection:
            after = [
                tuple(row)
                for row in connection.execute(
                    "SELECT * FROM application_status_history ORDER BY id"
                )
            ]
        self.assertEqual(after, before)
