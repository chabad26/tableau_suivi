"""Promotions : migration additive, administration et conservation des droits."""

import sqlite3
from contextlib import closing
from unittest.mock import patch

from app import database
from app.accounts import (
    UserInputError,
    authenticate,
    create_user,
    get_user,
    init_users,
    set_user_active,
)
from app.admin_accounts import (
    AdminAccountConflict,
    create_managed_promotion,
    create_managed_user,
    list_managed_promotions,
    set_managed_user_promotion,
)
from app.database import get_connection
from app.owned_applications import create_user_application
from tests.helpers import OfflineCase


class PromotionsTests(OfflineCase):
    def setUp(self):
        super().setUp()
        self.password = "FixtureCampusPassword2026!"
        self.admin = create_user("admin@campus.invalid", self.password, "admin")
        self.student = create_user("alice@campus.invalid", self.password)
        self.trainer = create_user("trainer@campus.invalid", self.password, "trainer")
        self.data = create_managed_promotion(self.admin, "Data")
        self.grc = create_managed_promotion(self.admin, "GRC 2026–2027")
        self.sign_in("admin@campus.invalid")

    def sign_in(self, email, client=None):
        client = client or self.client
        response = client.post(
            "/login", data={"email": email, "password": self.password}
        )
        self.assertEqual(response.status_code, 303)

    def test_legacy_users_are_migrated_idempotently_without_reassignment(self):
        path = self.root / "legacy.db"
        with closing(sqlite3.connect(path)) as connection, connection:
            connection.execute(
                "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, password_hash TEXT, role TEXT, active INTEGER, created_at TEXT)"
            )
            connection.execute(
                "INSERT INTO users VALUES (7, 'legacy@campus.invalid', 'fixture-hash', 'student', 1, '2020-01-01')"
            )
        with patch.object(database, "DATABASE_PATH", path):
            init_users()
            init_users()
            with get_connection() as connection:
                row = connection.execute("SELECT * FROM users WHERE id=7").fetchone()
                self.assertEqual(
                    tuple(row),
                    (
                        7,
                        "legacy@campus.invalid",
                        "fixture-hash",
                        "student",
                        1,
                        "2020-01-01",
                        None,
                    ),
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM promotions").fetchone()[0],
                    0,
                )
                self.assertEqual(
                    connection.execute("PRAGMA foreign_key_check").fetchall(), []
                )
            user = get_user(7)
            self.assertIsNone(user.promotion_id)
            self.assertEqual(user.promotion_name, "")

    def test_catalog_normalizes_whitespace_and_rejects_duplicates(self):
        with self.assertRaises(AdminAccountConflict):
            create_managed_promotion(self.admin, "  data  ")
        new = create_managed_promotion(self.admin, "  Cyber    sécurité  ")
        self.assertEqual(
            dict((r["id"], r["name"]) for r in list_managed_promotions(self.admin))[
                new
            ],
            "Cyber sécurité",
        )
        for value in ("", "  ", "X" * 101):
            with self.subTest(value=value), self.assertRaises(UserInputError):
                create_managed_promotion(self.admin, value)

    def test_creation_supports_optional_valid_promotion_for_all_roles(self):
        for role in ("student", "admin"):
            identifier = create_managed_user(
                self.admin,
                f"new-{role}@campus.invalid",
                self.password,
                role,
                promotion_id=self.data,
            )
            user = authenticate(f"new-{role}@campus.invalid", self.password)
            self.assertEqual(
                (user.id, user.role, user.promotion_id, user.promotion_name),
                (identifier, role, self.data, "Data"),
            )
        self.assertIsNone(get_user(self.student).promotion_id)
        with self.assertRaises(UserInputError):
            create_managed_user(
                self.admin, "invalid@campus.invalid", self.password, promotion_id=999999
            )

    def test_creation_and_update_routes_preserve_assignment(self):
        response = self.client.post(
            "/admin/users",
            data={
                "email": "new@campus.invalid",
                "role": "student",
                "password": self.password,
                "password_confirm": self.password,
                "promotion_id": str(self.data),
            },
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(
            authenticate("new@campus.invalid", self.password).promotion_name, "Data"
        )
        for promotion_id, expected in ((self.grc, "GRC 2026–2027"), ("", "")):
            response = self.client.post(
                f"/admin/users/{self.student}/promotion",
                data={
                    "promotion_id": promotion_id,
                    "role": "admin",
                    "user_id": self.admin,
                },
            )
            self.assertEqual(response.status_code, 303)
            user = get_user(self.student)
            self.assertEqual(user.promotion_name, expected)
            self.assertEqual(user.role, "student")
        self.assertEqual(self.client.get("/admin/users").status_code, 200)

    def test_account_promotion_refreshes_without_new_login(self):
        client = self.app.test_client()
        self.sign_in("alice@campus.invalid", client)
        self.assertIn("Non renseignée", client.get("/account").text)
        set_managed_user_promotion(self.admin, self.student, self.grc)
        self.assertIn("GRC 2026–2027", client.get("/account").text)
        # Même promotion ne donne pas accès aux candidatures d'un autre compte.
        set_managed_user_promotion(self.admin, self.trainer, self.grc)
        foreign = create_user_application(
            self.trainer, "Entreprise privée", "Poste privé"
        )
        self.assertEqual(client.get(f"/application/{foreign}").status_code, 404)

    def test_invalid_references_leave_user_unchanged(self):
        for value in ("-1", "0", "invalid", "999999", str(2**63), "9" * 100):
            with self.subTest(value=value):
                self.assertEqual(
                    self.client.post(
                        f"/admin/users/{self.student}/promotion",
                        data={"promotion_id": value},
                    ).status_code,
                    400,
                )
        self.assertIsNone(get_user(self.student).promotion_id)
        self.assertEqual(
            self.client.post(
                "/admin/users/999999/promotion", data={"promotion_id": self.data}
            ).status_code,
            404,
        )

    def test_only_active_admins_can_manage_promotions(self):
        for actor, email in (
            (self.student, "alice@campus.invalid"),
            (self.trainer, "trainer@campus.invalid"),
        ):
            client = self.app.test_client()
            self.sign_in(email, client)
            for path, data in (
                ("/admin/promotions", {"name": "Forbidden"}),
                (f"/admin/users/{self.student}/promotion", {"promotion_id": self.data}),
            ):
                self.assertEqual(client.post(path, data=data).status_code, 403)
            for function, args in (
                (list_managed_promotions, ()),
                (create_managed_promotion, ("Forbidden",)),
                (set_managed_user_promotion, (self.student, self.data)),
            ):
                with self.assertRaises(PermissionError):
                    function(actor, *args)
        set_user_active(self.admin, False)
        with self.assertRaises(PermissionError):
            set_managed_user_promotion(self.admin, self.student, self.data)
        self.assertEqual(
            self.client.post(
                "/admin/promotions", data={"name": "Forbidden"}
            ).status_code,
            302,
        )

    def test_promotion_post_routes_require_session_and_csrf(self):
        paths = [
            ("/admin/promotions", {"name": "Cyber"}),
            (f"/admin/users/{self.student}/promotion", {"promotion_id": self.data}),
        ]
        for path, data in paths:
            self.assertEqual(
                self.app.test_client().post(path, data=data).status_code, 302
            )
        self.app.config["WTF_CSRF_ENABLED"] = True
        for path, data in paths:
            self.assertEqual(self.client.post(path, data=data).status_code, 400)

    def test_invalid_creation_preserves_promotion_but_not_password(self):
        response = self.client.post(
            "/admin/users",
            data={
                "email": "invalid",
                "role": "student",
                "password": self.password,
                "password_confirm": self.password,
                "promotion_id": str(self.data),
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(f'value="{self.data}" selected', response.text)
        self.assertNotIn(self.password, response.text)

    def test_promotion_labels_are_escaped_in_both_views(self):
        promotion = create_managed_promotion(self.admin, "<script>alert(1)</script>")
        set_managed_user_promotion(self.admin, self.student, promotion)
        self.assertNotIn(
            "<script>alert(1)</script>", self.client.get("/admin/users").text
        )
        client = self.app.test_client()
        self.sign_in("alice@campus.invalid", client)
        self.assertIn(
            "&lt;script&gt;alert(1)&lt;/script&gt;", client.get("/account").text
        )
