"""Conversations multi-boîtes : pas de fusion entre postes ou propriétaires."""

from datetime import timedelta

from app.database import get_connection
from app.owned_applications import (
    get_user_application,
    get_user_application_emails,
    get_user_applications,
    update_user_application,
)
from app.owned_importer import import_user_emails
from tests.helpers import OfflineCase, fake_email


class ApplicationMatchingTests(OfflineCase):
    def setUp(self):
        super().setUp()
        self.alice = self.create_test_user("alice@example.invalid")
        self.bob = self.create_test_user("bob@example.invalid")
        self.first = fake_email(
            "<conversation-first@example.invalid>",
            sender='"Camille Martin (ACME)" <recruiter@acme.invalid>',
            subject="Stage : proposition d'entretien",
            mailbox="Ancienne boîte",
            body="Bonjour, proposition d'entretien pour votre candidature.",
            status="INTERVIEW",
        )

    def seed(self, message=None, owner=None):
        message = message or self.first
        owner = owner or self.alice
        import_user_emails(owner, [message])
        with get_connection() as connection:
            return connection.execute(
                "SELECT application_id FROM emails WHERE user_id=? AND message_id=?",
                (owner, message.message_id),
            ).fetchone()[0]

    def test_changed_display_name_and_recipient_mailbox_keep_same_application(self):
        identifier = self.seed()
        update_user_application(
            self.alice,
            identifier,
            "ACME",
            "Stage AIS",
            "Direct",
            "INTERVIEW",
            "Note à conserver",
        )
        reply = fake_email(
            "<conversation-reply@example.invalid>",
            sender="Camille Martin <recruiter@acme.invalid>",
            subject="Re: Stage : proposition d'entretien",
            mailbox="Nouvelle boîte",
            date=self.first.date + timedelta(days=4),
            body="Suite de notre échange.",
            status="ACCEPTED",
        )
        import_user_emails(self.alice, [reply])
        self.assertEqual(len(get_user_applications(self.alice)), 1)
        self.assertEqual(len(get_user_application_emails(self.alice, identifier)), 2)
        row = get_user_application(self.alice, identifier)
        self.assertEqual(
            (row["job_title"], row["manual_status"], row["manual_note"]),
            ("Stage AIS", "INTERVIEW", "Note à conserver"),
        )

    def test_reply_to_links_despite_changed_sender_and_subject(self):
        identifier = self.seed()
        reply = fake_email(
            "<new-address@example.invalid>",
            sender="Autre interlocuteur <contact@other.invalid>",
            subject="Suite de notre échange",
            body="Bonjour.",
            in_reply_to=self.first.message_id,
        )
        import_user_emails(self.alice, [reply])
        self.assertEqual(len(get_user_applications(self.alice)), 1)
        self.assertEqual(len(get_user_application_emails(self.alice, identifier)), 2)
        with get_connection() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT in_reply_to FROM emails WHERE user_id=? AND message_id=?",
                    (self.alice, reply.message_id),
                ).fetchone()[0],
                self.first.message_id,
            )

    def test_references_link_conversation_when_direct_parent_is_missing(self):
        identifier = self.seed()
        reply = fake_email(
            "<reference-reply@example.invalid>",
            sender="Other <new@other.invalid>",
            subject="Une suite",
            body="Bonjour.",
            references=f"<unknown@example.invalid> {self.first.message_id}",
        )
        import_user_emails(self.alice, [reply])
        self.assertEqual(len(get_user_application_emails(self.alice, identifier)), 2)

    def test_direct_parent_is_preferred_over_older_references(self):
        target = self.seed()
        other = fake_email(
            "<unrelated@example.invalid>",
            sender="Other <other@elsewhere.invalid>",
            subject="Autre conversation",
            body="Bonjour.",
        )
        other_id = self.seed(other)
        reply = fake_email(
            "<direct-parent@example.invalid>",
            sender="New <new@different.invalid>",
            subject="Suite",
            body="Bonjour.",
            in_reply_to=self.first.message_id,
            references=f"{other.message_id} {self.first.message_id}",
        )
        import_user_emails(self.alice, [reply])
        self.assertEqual(len(get_user_application_emails(self.alice, target)), 2)
        self.assertEqual(len(get_user_application_emails(self.alice, other_id)), 1)

    def test_conversation_matching_never_uses_another_owners_messages(self):
        foreign = self.seed(owner=self.bob)
        reply = fake_email(
            "<own-reply@example.invalid>",
            sender="New <new@different.invalid>",
            subject="Suite",
            body="Bonjour.",
            in_reply_to=self.first.message_id,
        )
        import_user_emails(self.alice, [reply])
        self.assertEqual(len(get_user_applications(self.alice)), 1)
        self.assertEqual(len(get_user_application_emails(self.bob, foreign)), 1)
        self.assertEqual(get_user_applications(self.alice)[0]["user_id"], self.alice)

    def test_different_explicit_job_title_is_not_attached_to_parent_job(self):
        original = fake_email(
            "<job-a@example.invalid>", subject="Votre candidature : Développeur Python"
        )
        first_id = self.seed(original)
        reply = fake_email(
            "<job-b@example.invalid>",
            subject="Votre candidature : Analyste GRC",
            in_reply_to=original.message_id,
        )
        import_user_emails(self.alice, [reply])
        self.assertEqual(len(get_user_applications(self.alice)), 2)
        self.assertEqual(len(get_user_application_emails(self.alice, first_id)), 1)

    def test_ambiguous_conversation_candidates_are_not_chosen_arbitrarily(self):
        first_id = self.seed()
        second = fake_email(
            "<same-subject@example.invalid>",
            sender="Autre nom <recruiter@acme.invalid>",
            subject=self.first.subject,
            body="Bonjour.",
        )
        second_id = self.seed(second)
        reply = fake_email(
            "<ambiguous@example.invalid>",
            sender="Encore un nom <recruiter@acme.invalid>",
            subject=f"Re: {self.first.subject}",
            body="Bonjour.",
        )
        import_user_emails(self.alice, [reply])
        self.assertEqual(len(get_user_applications(self.alice)), 3)
        self.assertEqual(len(get_user_application_emails(self.alice, first_id)), 1)
        self.assertEqual(len(get_user_application_emails(self.alice, second_id)), 1)

    def test_generic_subject_is_not_enough_without_thread_metadata(self):
        original = fake_email(
            "<generic@example.invalid>",
            sender=self.first.sender,
            subject="Votre candidature",
            body="Bonjour.",
        )
        self.seed(original)
        reply = fake_email(
            "<generic-reply@example.invalid>",
            sender="Autre nom <recruiter@acme.invalid>",
            subject="Re: Votre candidature",
            body="Bonjour.",
        )
        import_user_emails(self.alice, [reply])
        self.assertEqual(len(get_user_applications(self.alice)), 2)

    def test_very_old_subject_match_without_headers_is_not_enough(self):
        self.seed()
        reply = fake_email(
            "<late-reply@example.invalid>",
            sender="Autre nom <recruiter@acme.invalid>",
            subject=f"Re: {self.first.subject}",
            date=self.first.date + timedelta(days=120),
            body="Bonjour.",
        )
        import_user_emails(self.alice, [reply])
        self.assertEqual(len(get_user_applications(self.alice)), 2)

    def test_mailboxes_can_be_scanned_in_reverse_date_order(self):
        reply = fake_email(
            "<newer-first@example.invalid>",
            sender="Autre nom <recruiter@acme.invalid>",
            subject=f"Re: {self.first.subject}",
            date=self.first.date + timedelta(days=4),
            body="Bonjour.",
        )
        identifier = self.seed(reply)
        import_user_emails(self.alice, [self.first])
        self.assertEqual(len(get_user_applications(self.alice)), 1)
        self.assertEqual(len(get_user_application_emails(self.alice, identifier)), 2)
