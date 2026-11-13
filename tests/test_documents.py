"""Documents et échanges : fichiers fictifs, bases et stockage temporaires."""

import io
import re
import sqlite3
import stat
import zipfile
from unittest.mock import patch

from app.accounts import create_user, set_user_active
from app.admin_accounts import create_managed_promotion, set_managed_user_promotion
from app.database import get_connection
from app.documents import (
    MAX_DOCUMENT_BYTES,
    DocumentInputError,
    DocumentNotFound,
    DocumentStorageError,
    add_document_comment,
    delete_document,
    document_detail,
    download_document,
    init_documents,
    list_document_learners,
    upload_document,
)
from tests.helpers import OfflineCase

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
PDF2 = b"%PDF-1.4\n2 0 obj\n<<>>\nendobj\n%%EOF\n"


def docx(*, macro=False, extra=False, compression=zipfile.ZIP_DEFLATED):
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w", compression=compression) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
        )
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body/></w:document>',
        )
        if macro:
            archive.writestr("word/vbaProject.bin", b"fixture")
        if extra:
            archive.writestr("../outside", b"fixture")
    return content.getvalue()


class DocumentTests(OfflineCase):
    def test_pedagogy_chooses_promotion_before_learner(self):
        data = create_managed_promotion(self.admin, "Data 2026–2027")
        grc = create_managed_promotion(self.admin, "GRC 2026–2027")
        set_managed_user_promotion(self.admin, self.alice, data)
        set_managed_user_promotion(self.admin, self.bob, grc)
        page = self.team.get("/documents")
        self.assertIn('name="promotion"', page.text)
        self.assertNotIn('name="learner"', page.text)
        self.assertNotIn("alice@example.invalid", page.text)
        page = self.team.get(f"/documents?promotion={data}")
        self.assertIn('name="learner"', page.text)
        self.assertIn("alice@example.invalid", page.text)
        self.assertNotIn("bob@example.invalid", page.text)
        page = self.team.get(f"/documents?promotion={data}&learner={self.alice}")
        self.assertIn("CV confidentiel Alice", page.text)
        self.assertEqual(
            self.team.get(
                f"/documents?promotion={grc}&learner={self.alice}"
            ).status_code,
            404,
        )
        # Un lien existant vers un apprenant retrouve automatiquement sa promotion.
        page = self.team.get(f"/documents?learner={self.alice}")
        self.assertEqual(page.status_code, 200)
        self.assertIn(f'value="{data}" selected', page.text)
        self.assertNotIn("bob@example.invalid", page.text)

    def test_empty_and_unassigned_promotions_are_usable(self):
        empty = create_managed_promotion(self.admin, "Nouvelle formation 2027–2028")
        page = self.team.get(f"/documents?promotion={empty}")
        self.assertIn("Aucun apprenant dans cette promotion.", page.text)
        self.assertNotIn("alice@example.invalid", page.text)
        page = self.team.get("/documents?promotion=unassigned")
        self.assertIn("alice@example.invalid", page.text)
        self.assertIn("bob@example.invalid", page.text)
        self.assertEqual(self.team.get("/documents?promotion=999999").status_code, 404)

    def setUp(self):
        super().setUp()
        self.alice = self.login_test_user("alice@example.invalid")
        self.bob = self.create_test_user("bob@example.invalid")
        self.password = "FixturePedagogyPassword2026!"
        self.admin = create_user("pedagogy@example.invalid", self.password, "admin")
        self.team = self.app.test_client()
        self.assertEqual(
            self.team.post(
                "/login",
                data={"email": "pedagogy@example.invalid", "password": self.password},
            ).status_code,
            303,
        )
        self.document, self.version = upload_document(
            self.alice, "cv.pdf", PDF, kind="cv", title="CV confidentiel Alice"
        )

    def upload(
        self,
        client=None,
        *,
        path="/documents",
        filename="new.pdf",
        payload=PDF,
        **values,
    ):
        data = {
            "kind": "cv",
            "title": "CV nouveau",
            **values,
            "file": (io.BytesIO(payload), filename),
        }
        response = (client or self.client).post(
            path, data=data, content_type="multipart/form-data"
        )
        # Le générateur multipart de Werkzeug crée un fichier temporaire pour
        # les grosses requêtes de test ; la fixture referme explicitement ce flux.
        self.addCleanup(response.request.input_stream.close)
        self.addCleanup(response.close)
        return response

    def path(self, version_id=None):
        with get_connection() as connection:
            storage = connection.execute(
                "SELECT storage_name FROM document_versions WHERE id=?",
                (version_id or self.version,),
            ).fetchone()[0]
        return self.root / "documents" / str(self.alice) / storage

    def test_upload_http_pdf_docx_and_independent_letters(self):
        for name, payload, kind in (
            ("../cv-français.PDF", PDF, "cv"),
            ("lettre.docx", docx(), "lm"),
        ):
            with self.subTest(name=name):
                response = self.upload(filename=name, payload=payload, kind=kind)
                self.assertEqual(response.status_code, 303)
                identifier = int(response.headers["Location"].rsplit("/", 1)[1])
                data = document_detail(self.alice, identifier)
                self.assertEqual(data["document"]["kind"], kind)
                self.assertEqual(len(data["versions"]), 1)
                self.assertNotIn("..", data["version"]["filename"])
                metadata, content = download_document(self.alice, data["version"]["id"])
                self.assertEqual(content, payload)
                self.assertTrue(metadata["filename"].endswith((".pdf", ".docx")))
        self.assertEqual(len(list_document_learners(self.admin)), 2)

    def test_upload_owner_comes_from_session_and_version_migration_is_additive(self):
        response = self.upload(user_id=self.bob, owner_id=self.bob)
        self.assertEqual(response.status_code, 303)
        identifier = int(response.headers["Location"].rsplit("/", 1)[1])
        self.assertEqual(
            document_detail(self.alice, identifier)["document"]["user_id"], self.alice
        )
        with self.assertRaises(DocumentNotFound):
            document_detail(self.bob, identifier)
        init_documents()
        self.assertEqual(download_document(self.alice, self.version)[1], PDF)

    def test_missing_files_and_huge_identifiers_return_controlled_errors(self):
        self.path().unlink()
        self.assertEqual(
            self.client.get(f"/documents/versions/{self.version}/download").status_code,
            503,
        )
        for path in (f"/documents/{2**80}", f"/documents/versions/{2**80}/download"):
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_new_version_keeps_prior_file_and_discussion(self):
        add_document_comment(
            self.admin, self.version, "ANNOTATION-V1", kind="annotation", page=2
        )
        response = self.upload(
            path=f"/documents/{self.document}/versions", payload=PDF2
        )
        self.assertEqual(response.status_code, 303)
        data = document_detail(self.alice, self.document)
        self.assertEqual([row["version"] for row in data["versions"]], [2, 1])
        self.assertEqual(data["comments"], [])
        self.assertEqual(
            document_detail(self.admin, self.document, self.version)["comments"][0][
                "body"
            ],
            "ANNOTATION-V1",
        )
        self.assertEqual(download_document(self.alice, self.version)[1], PDF)

    def test_both_profiles_exchange_messages_with_server_side_author(self):
        route = f"/documents/{self.document}/versions/{self.version}/comments"
        self.assertEqual(
            self.team.post(
                route,
                data={
                    "kind": "annotation",
                    "page": "2",
                    "body": "Préciser les compétences.",
                },
            ).status_code,
            303,
        )
        self.assertEqual(
            self.client.post(
                route,
                data={
                    "kind": "message",
                    "body": "Je vais compléter.",
                    "author_id": self.admin,
                    "author_role": "admin",
                },
            ).status_code,
            303,
        )
        comments = document_detail(self.alice, self.document)["comments"]
        self.assertEqual(
            [(row["author_id"], row["author_role"], row["page"]) for row in comments],
            [(self.admin, "admin", 2), (self.alice, "student", None)],
        )
        page = self.client.get(f"/documents/{self.document}")
        self.assertIn("Préciser les compétences.", page.text)
        self.assertIn("Équipe pédagogique", page.text)
        self.assertIn("page 2", page.text)

    def test_pedagogy_can_review_but_cannot_replace_or_delete_files(self):
        self.assertEqual(
            self.team.get(f"/documents?learner={self.alice}").status_code, 200
        )
        self.assertEqual(self.team.get(f"/documents/{self.document}").status_code, 200)
        response = self.team.get(f"/documents/versions/{self.version}/download")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, PDF)
        self.assertIn("attachment", response.headers["Content-Disposition"])
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(self.upload(self.team).status_code, 403)
        self.assertEqual(
            self.upload(
                self.team, path=f"/documents/{self.document}/versions"
            ).status_code,
            403,
        )
        self.assertEqual(
            self.team.post(f"/documents/{self.document}/delete").status_code, 403
        )
        self.assertNotIn(
            "Déposer une nouvelle version",
            self.team.get(f"/documents/{self.document}").text,
        )
        self.assertTrue(self.path().exists())

    def test_other_learner_cannot_read_change_download_comment_or_delete(self):
        peer = self.app.test_client()
        peer.post(
            "/login",
            data={"email": "bob@example.invalid", "password": "MotDePasseDeTest2026!"},
        )
        for path in (
            f"/documents/{self.document}",
            f"/documents?learner={self.alice}",
            f"/documents/versions/{self.version}/download",
        ):
            self.assertEqual(peer.get(path).status_code, 404)
        self.assertNotIn("CV confidentiel Alice", peer.get("/documents").text)
        self.assertEqual(
            self.upload(peer, path=f"/documents/{self.document}/versions").status_code,
            404,
        )
        self.assertEqual(
            peer.post(
                f"/documents/{self.document}/versions/{self.version}/comments",
                data={"body": "Interdit"},
            ).status_code,
            404,
        )
        self.assertEqual(
            peer.post(f"/documents/{self.document}/delete").status_code, 404
        )
        with self.assertRaises(DocumentNotFound):
            download_document(self.bob, self.version)

    def test_anonymous_and_disabled_actors_are_rejected(self):
        anonymous = self.app.test_client()
        self.assertEqual(anonymous.get("/documents").status_code, 302)
        self.assertEqual(
            anonymous.get(f"/documents/versions/{self.version}/download").status_code,
            302,
        )
        set_user_active(self.admin, False)
        with self.assertRaises(PermissionError):
            download_document(self.admin, self.version)
        set_user_active(self.alice, False)
        self.assertEqual(self.client.get("/documents").status_code, 302)
        with self.assertRaises(PermissionError):
            add_document_comment(self.alice, self.version, "Interdit")

    def test_retained_documents_of_disabled_learner_remain_reviewable_by_team(self):
        set_user_active(self.alice, False)
        self.assertEqual(
            document_detail(self.admin, self.document)["owner"]["active"], 0
        )
        self.assertEqual(download_document(self.admin, self.version)[1], PDF)

    def test_file_signature_archive_and_size_validation(self):
        for name, payload in (
            ("fake.pdf", b"<html>not a PDF</html>"),
            ("file.exe", PDF),
            ("empty.pdf", b""),
            ("macro.docx", docx(macro=True)),
            ("unsupported-compression.docx", docx(compression=zipfile.ZIP_BZIP2)),
            ("traversal.docx", docx(extra=True)),
            ("fake.docx", PDF),
            ("large.pdf", b"x" * (MAX_DOCUMENT_BYTES + 1)),
        ):
            with self.subTest(name=name), self.assertRaises(DocumentInputError):
                upload_document(self.alice, name, payload, kind="cv", title="Interdit")
        self.assertEqual(len(document_detail(self.alice, self.document)["versions"]), 1)

    def test_upload_limit_is_specific_to_document_endpoints(self):
        payload = b"%PDF-1.4\n" + b"x" * (3 * 1024 * 1024) + b"\n%%EOF\n"
        self.assertEqual(self.upload(payload=payload).status_code, 303)
        self.assertEqual(self.app.config["MAX_CONTENT_LENGTH"], 2 * 1024 * 1024)
        self.assertEqual(
            self.client.post(
                "/application/new",
                data=b"x" * (3 * 1024 * 1024),
                content_type="application/x-www-form-urlencoded",
            ).status_code,
            413,
        )

    def test_private_paths_permissions_and_no_static_access(self):
        path = self.path()
        self.assertRegex(path.name, r"^[a-f0-9]{32}\.pdf$")
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(path.parent.parent.stat().st_mode), 0o700)
        self.assertEqual(
            self.client.get(f"/static/documents/{self.alice}/{path.name}").status_code,
            404,
        )

    def test_symlink_and_modified_files_are_never_downloaded(self):
        path = self.path()
        outside = self.root / "outside.pdf"
        outside.write_bytes(b"PRIVATE-OUTSIDE")
        path.unlink()
        path.symlink_to(outside)
        with self.assertRaises(DocumentStorageError):
            download_document(self.alice, self.version)
        response = self.client.get(f"/documents/versions/{self.version}/download")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("PRIVATE-OUTSIDE", response.text)
        path.unlink()
        path.write_bytes(PDF2)
        with self.assertRaises(DocumentStorageError):
            download_document(self.alice, self.version)

    def test_failed_database_insert_removes_new_file_and_version(self):
        before = set(self.path().parent.iterdir())
        with get_connection() as connection:
            connection.execute(
                "CREATE TRIGGER fail_document_version BEFORE INSERT ON document_versions BEGIN SELECT RAISE(ABORT,'fixture'); END"
            )
        with self.assertRaises(sqlite3.IntegrityError):
            upload_document(self.alice, "new.pdf", PDF2, document_id=self.document)
        self.assertEqual(set(self.path().parent.iterdir()), before)
        self.assertEqual(len(document_detail(self.alice, self.document)["versions"]), 1)

    def test_actor_is_rechecked_after_file_validation(self):
        from app import documents

        original = documents._validate_file

        def revoke(filename, content):
            result = original(filename, content)
            set_user_active(self.alice, False)
            return result

        with (
            patch("app.documents._validate_file", side_effect=revoke),
            self.assertRaises(PermissionError),
        ):
            upload_document(self.alice, "new.pdf", PDF2, document_id=self.document)
        self.assertEqual(len(list(self.path().parent.glob("*.pdf"))), 1)

    def test_delete_cascades_files_versions_comments_and_is_owner_only(self):
        _, second = upload_document(
            self.alice, "new.pdf", PDF2, document_id=self.document
        )
        add_document_comment(self.admin, self.version, "Retour pédagogique")
        paths = [self.path(), self.path(second)]
        self.assertEqual(
            self.client.post(f"/documents/{self.document}/delete").status_code, 303
        )
        self.assertTrue(all(not path.exists() for path in paths))
        with get_connection() as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM document_comments").fetchone()[
                    0
                ],
                0,
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM document_versions").fetchone()[
                    0
                ],
                0,
            )
        self.assertEqual(self.team.get(f"/documents/{self.document}").status_code, 404)

    def test_failed_deletion_restores_files_and_metadata(self):
        with get_connection() as connection:
            connection.execute(
                "CREATE TRIGGER fail_document_delete BEFORE DELETE ON documents BEGIN SELECT RAISE(ABORT,'fixture'); END"
            )
        with self.assertRaises(sqlite3.IntegrityError):
            delete_document(self.alice, self.document)
        self.assertEqual(download_document(self.alice, self.version)[1], PDF)
        self.assertEqual(list(self.path().parent.glob(".deleting-*")), [])

    def test_cross_document_version_selection_and_invalid_comments_are_rejected(self):
        other, other_version = upload_document(
            self.alice, "lm.pdf", PDF2, kind="lm", title="Lettre ACME"
        )
        self.assertEqual(
            self.client.get(
                f"/documents/{self.document}?version={other_version}"
            ).status_code,
            404,
        )
        route = f"/documents/{self.document}/versions/{other_version}/comments"
        self.assertEqual(
            self.client.post(route, data={"body": "Interdit"}).status_code, 404
        )
        for kind, page in (
            ("message", "2"),
            ("annotation", "0"),
            ("annotation", "10000"),
            ("annotation", "not-a-page"),
        ):
            response = self.client.post(
                f"/documents/{self.document}/versions/{self.version}/comments",
                data={"kind": kind, "page": page, "body": "Brouillon conservé"},
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn("Brouillon conservé", response.text)
        self.assertEqual(document_detail(self.alice, other)["comments"], [])

    def test_titles_and_comments_are_escaped(self):
        title = '<script>alert("title")</script>'
        identifier, version = upload_document(
            self.alice, "cv.pdf", PDF, kind="cv", title=title
        )
        add_document_comment(self.admin, version, '<img src=x onerror="alert(1)">')
        page = self.client.get(f"/documents/{identifier}")
        self.assertNotIn(title, page.text)
        self.assertNotIn("<img src=x", page.text)
        self.assertIn("&lt;script&gt;", page.text)
        self.assertIn("&lt;img", page.text)

    def test_csrf_protects_upload_comment_and_delete(self):
        self.app.config["WTF_CSRF_ENABLED"] = True
        self.assertEqual(self.upload().status_code, 400)
        self.assertEqual(
            self.client.post(f"/documents/{self.document}/delete").status_code, 400
        )
        route = f"/documents/{self.document}/versions/{self.version}/comments"
        self.assertEqual(
            self.client.post(route, data={"body": "Interdit"}).status_code, 400
        )
        token = re.search(
            r'name="csrf_token"\s+value="([^"]+)"', self.client.get("/documents").text
        ).group(1)
        self.assertEqual(self.upload(csrf_token=token).status_code, 303)

    def test_initialization_is_idempotent_and_does_not_create_storage(self):
        init_documents()
        init_documents()
        self.assertEqual(
            document_detail(self.alice, self.document)["version"]["version"], 1
        )
        self.assertFalse((self.root / "documents" / str(self.bob)).exists())
