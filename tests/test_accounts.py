"""Tests de la première brique comptes utilisateurs."""

import sqlite3

from app import database
from app.accounts import (
    authenticate,
    create_user,
    get_user,
    init_users,
    set_user_active,
)
from tests.helpers import OfflineCase


class AccountsTests(OfflineCase):
    def setUp(self):
        super().setUp()
        init_users()

    def test_create_and_authenticate(self):
        user_id = create_user("  Eleve@Campus.Example ", "UnePhraseSecrete!2026")
        user = authenticate("eleve@campus.example", "UnePhraseSecrete!2026")
        self.assertIsNotNone(user)
        assert user is not None
        self.assertEqual(user.id, user_id)
        self.assertEqual(user.email, "eleve@campus.example")
        self.assertEqual(user.role, "student")
        self.assertIsNone(authenticate("eleve@campus.example", "incorrect"))

    def test_password_is_hashed(self):
        user_id = create_user("test@campus.example", "UnePhraseSecrete!2026")
        with database.get_connection() as connection:
            row = connection.execute(
                "SELECT password_hash FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        self.assertNotEqual(row["password_hash"], "UnePhraseSecrete!2026")
        self.assertTrue(row["password_hash"].startswith("scrypt:"))

    def test_duplicate_email_is_rejected(self):
        create_user("test@campus.example", "UnePhraseSecrete!2026")
        with self.assertRaises(sqlite3.IntegrityError):
            create_user("TEST@CAMPUS.EXAMPLE", "UnePhraseSecrete!2026")

    def test_deactivated_account_cannot_sign_in(self):
        user_id = create_user("test@campus.example", "UnePhraseSecrete!2026")
        set_user_active(user_id, False)
        self.assertIsNone(authenticate("test@campus.example", "UnePhraseSecrete!2026"))
        user = get_user(user_id)
        self.assertIsNotNone(user)
        assert user is not None
        self.assertFalse(user.active)

    def test_invalid_input_and_idempotent_schema(self):
        init_users()
        with self.assertRaises(ValueError):
            create_user("bad-email", "UnePhraseSecrete!2026")
        with self.assertRaises(ValueError):
            create_user("ok@campus.example", "short")
        with self.assertRaises(ValueError):
            create_user("ok@campus.example", "UnePhraseSecrete!2026", role="superadmin")
