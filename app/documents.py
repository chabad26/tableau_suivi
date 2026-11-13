"""Documents privés des apprenants, versions et échanges pédagogiques."""

import hashlib
import io
import os
import re
import sqlite3
import stat
import zipfile
import zlib
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree

from werkzeug.utils import secure_filename

from app import database
from app.database import get_connection
from app.owned_applications import require_user_id

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
DOCUMENT_KINDS = {"cv": "CV", "lm": "Lettre de motivation"}


class DocumentInputError(ValueError):
    """Erreur fixe de saisie, affichable sans exposer de détails techniques."""


class DocumentNotFound(LookupError):
    pass


class DocumentStorageError(RuntimeError):
    pass


def _key(value: int) -> int:
    if type(value) is not int or not 0 < value < 2**63:
        raise DocumentNotFound()
    return value


def init_documents() -> None:
    with get_connection() as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            kind TEXT NOT NULL CHECK(kind IN ('cv','lm')),
            title TEXT NOT NULL,
            last_version INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        connection.execute("""CREATE TABLE IF NOT EXISTS document_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            version INTEGER NOT NULL,
            filename TEXT NOT NULL,
            storage_name TEXT NOT NULL UNIQUE,
            size_bytes INTEGER NOT NULL,
            sha256 TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(document_id,version)
        )""")
        connection.execute("""CREATE TABLE IF NOT EXISTS document_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id INTEGER NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
            author_id INTEGER NOT NULL REFERENCES users(id),
            author_role TEXT NOT NULL CHECK(author_role IN ('student','admin')),
            kind TEXT NOT NULL CHECK(kind IN ('message','annotation')),
            page INTEGER,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_documents_user ON documents(user_id,id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_document_comments_version ON document_comments(version_id,id)"
        )


def _actor(connection: sqlite3.Connection, actor_id: int) -> sqlite3.Row:
    actor_id = require_user_id(actor_id)
    row = connection.execute(
        "SELECT id,role,active FROM users WHERE id=?", (actor_id,)
    ).fetchone()
    if row is None or not row["active"] or row["role"] not in {"student", "admin"}:
        raise PermissionError("Accès aux documents non autorisé.")
    return row


def _owner(
    connection: sqlite3.Connection,
    actor: sqlite3.Row,
    owner_id: int,
    *,
    edit: bool = False,
) -> sqlite3.Row:
    owner_id = require_user_id(owner_id)
    if actor["role"] != "admin" and actor["id"] != owner_id:
        raise DocumentNotFound()
    if edit and (actor["role"] != "student" or actor["id"] != owner_id):
        raise PermissionError("Seul l'apprenant peut gérer ses fichiers.")
    row = connection.execute(
        "SELECT u.id,u.email,u.active,u.promotion_id,p.name AS promotion_name FROM users u LEFT JOIN promotions p ON p.id=u.promotion_id WHERE u.id=? AND u.role='student'",
        (owner_id,),
    ).fetchone()
    if row is None:
        raise DocumentNotFound()
    return row


def _document(
    connection: sqlite3.Connection,
    actor_id: int,
    document_id: int,
    *,
    edit: bool = False,
) -> tuple[sqlite3.Row, sqlite3.Row]:
    document_id = _key(document_id)
    actor = _actor(connection, actor_id)
    row = connection.execute(
        "SELECT id,user_id,kind,title,last_version,created_at FROM documents WHERE id=?",
        (document_id,),
    ).fetchone()
    if row is None:
        raise DocumentNotFound()
    owner = _owner(connection, actor, row["user_id"], edit=edit)
    return row, owner


def list_document_learners(
    actor_id: int, *, promotion: str | None = None
) -> list[dict]:
    with get_connection() as connection:
        connection.execute("BEGIN")
        if _actor(connection, actor_id)["role"] != "admin":
            raise PermissionError()
        where, params = "u.role='student'", []
        if promotion == "unassigned":
            where += " AND u.promotion_id IS NULL"
        elif promotion is not None:
            try:
                promotion_id = _key(int(promotion))
            except ValueError:
                raise DocumentNotFound() from None
            where += " AND u.promotion_id=?"
            params.append(promotion_id)
        return [
            dict(row)
            for row in connection.execute(
                f"SELECT u.id,u.email,u.active,p.name AS promotion_name,COUNT(d.id) AS documents_count FROM users u LEFT JOIN promotions p ON p.id=u.promotion_id LEFT JOIN documents d ON d.user_id=u.id WHERE {where} GROUP BY u.id ORDER BY u.email COLLATE NOCASE,u.id",
                params,
            )
        ]


def list_documents(actor_id: int, owner_id: int) -> tuple[dict, list[dict]]:
    with get_connection() as connection:
        connection.execute("BEGIN")
        owner = _owner(connection, _actor(connection, actor_id), owner_id)
        rows = connection.execute(
            "SELECT d.id,d.user_id,d.kind,d.title,d.created_at,COUNT(v.id) AS versions_count,MAX(v.created_at) AS updated_at FROM documents d LEFT JOIN document_versions v ON v.document_id=d.id WHERE d.user_id=? GROUP BY d.id ORDER BY d.id DESC",
            (owner_id,),
        ).fetchall()
        return dict(owner), [dict(row) for row in rows]


def document_detail(
    actor_id: int, document_id: int, version_id: int | None = None
) -> dict:
    with get_connection() as connection:
        connection.execute("BEGIN")
        document, owner = _document(connection, actor_id, document_id)
        versions = [
            dict(row)
            for row in connection.execute(
                "SELECT id,version,filename,size_bytes,created_at FROM document_versions WHERE document_id=? ORDER BY version DESC",
                (document_id,),
            )
        ]
        version = (
            next((row for row in versions if row["id"] == version_id), None)
            if version_id is not None
            else (versions[0] if versions else None)
        )
        if version_id is not None and version is None:
            raise DocumentNotFound()
        comments = []
        if version is not None:
            comments = [
                dict(row)
                for row in connection.execute(
                    "SELECT c.id,c.author_id,c.author_role,c.kind,c.page,c.body,c.created_at,u.email AS author_email FROM document_comments c JOIN users u ON u.id=c.author_id WHERE c.version_id=? ORDER BY c.id",
                    (version["id"],),
                )
            ]
        return {
            "document": dict(document),
            "owner": dict(owner),
            "versions": versions,
            "version": version,
            "comments": comments,
        }


def _validate_file(filename: str, content: bytes) -> tuple[str, str]:
    if not content or len(content) > MAX_DOCUMENT_BYTES:
        raise DocumentInputError("Choisis un fichier non vide de 10 Mo maximum.")
    original = filename.replace("\\", "/").rsplit("/", 1)[-1]
    suffix = Path(original).suffix.casefold()
    if suffix not in {".pdf", ".docx"}:
        raise DocumentInputError("Seuls les fichiers PDF et DOCX sont acceptés.")
    name = (secure_filename(Path(original).stem)[:140] or "document") + suffix
    if suffix == ".pdf":
        if not content.startswith(b"%PDF-") or b"%%EOF" not in content[-2048:]:
            raise DocumentInputError("Le fichier ne ressemble pas à un PDF valide.")
    else:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                files = archive.infolist()
                names = [item.filename for item in files]
                if (
                    len(names) != len(set(names))
                    or len(files) > 2000
                    or sum(item.file_size for item in files) > 50 * 1024 * 1024
                    or any(
                        item.compress_type
                        not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                        for item in files
                    )
                ):
                    raise ValueError()
                if (
                    "[Content_Types].xml" not in names
                    or "word/document.xml" not in names
                    or any(
                        "vbaproject" in name.casefold()
                        or name.startswith("/")
                        or ".." in name.split("/")
                        for name in names
                    )
                ):
                    raise ValueError()
                if archive.getinfo("[Content_Types].xml").file_size > 256 * 1024:
                    raise ValueError()
                types = archive.read("[Content_Types].xml")
                if b"<!DOCTYPE" in types.upper() or b"<!ENTITY" in types.upper():
                    raise ValueError()
                root = ElementTree.fromstring(types)
                if not any(
                    element.get("PartName") == "/word/document.xml"
                    and element.get("ContentType")
                    == "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
                    for element in root
                ):
                    raise ValueError()
        except (
            ValueError,
            KeyError,
            zipfile.BadZipFile,
            RuntimeError,
            ElementTree.ParseError,
            zlib.error,
            NotImplementedError,
            OSError,
        ):
            raise DocumentInputError(
                "Le fichier ne ressemble pas à un DOCX pris en charge."
            ) from None
    return name, suffix


def _directory(owner_id: int, *, create: bool = False) -> Path:
    root = database.DATABASE_PATH.parent / "documents"
    directory = root / str(require_user_id(owner_id))
    for parent in (directory, *directory.parents):
        if parent.is_symlink():
            raise DocumentStorageError("Stockage de documents indisponible.")
    if create:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(root, 0o700)
        os.chmod(directory, 0o700)
    return directory


def _path(owner_id: int, storage_name: str) -> Path:
    if re.fullmatch(r"[a-f0-9]{32}\.(pdf|docx)", storage_name) is None:
        raise DocumentStorageError("Stockage de documents indisponible.")
    path = _directory(owner_id) / storage_name
    if path.is_symlink():
        raise DocumentStorageError("Stockage de documents indisponible.")
    return path


def upload_document(
    actor_id: int,
    filename: str,
    content: bytes,
    *,
    kind: str = "",
    title: str = "",
    document_id: int | None = None,
) -> tuple[int, int]:
    # Vérification avant validation du fichier, puis dans la transaction d'écriture.
    with get_connection() as connection:
        if document_id is not None:
            _document(connection, actor_id, document_id, edit=True)
        else:
            _owner(connection, _actor(connection, actor_id), actor_id, edit=True)
    name, suffix = _validate_file(filename, content)
    if document_id is None and (
        kind not in DOCUMENT_KINDS or not 1 <= len(title.strip()) <= 120
    ):
        raise DocumentInputError(
            "Choisis CV ou lettre de motivation et un titre de 1 à 120 caractères."
        )
    created: Path | None = None
    try:
        with get_connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if document_id is None:
                _owner(connection, _actor(connection, actor_id), actor_id, edit=True)
                cursor = connection.execute(
                    "INSERT INTO documents(user_id,kind,title) VALUES (?,?,?)",
                    (actor_id, kind, title.strip()),
                )
                if cursor.lastrowid is None:
                    raise DocumentStorageError()
                document_id = int(cursor.lastrowid)
            else:
                _document(connection, actor_id, document_id, edit=True)
            connection.execute(
                "UPDATE documents SET last_version=last_version+1 WHERE id=?",
                (document_id,),
            )
            number = connection.execute(
                "SELECT last_version FROM documents WHERE id=?", (document_id,)
            ).fetchone()[0]
            directory = _directory(actor_id, create=True)
            storage_name = uuid4().hex + suffix
            path = directory / storage_name
            descriptor = os.open(
                path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600
            )
            created = path
            with os.fdopen(descriptor, "wb") as file:
                os.fchmod(file.fileno(), 0o600)
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
            cursor = connection.execute(
                "INSERT INTO document_versions(document_id,version,filename,storage_name,size_bytes,sha256) VALUES (?,?,?,?,?,?)",
                (
                    document_id,
                    number,
                    name,
                    storage_name,
                    len(content),
                    hashlib.sha256(content).hexdigest(),
                ),
            )
            if cursor.lastrowid is None:
                raise DocumentStorageError()
            version_id = int(cursor.lastrowid)
        return document_id, version_id
    except Exception:
        if created is not None:
            created.unlink(missing_ok=True)
        raise


def download_document(actor_id: int, version_id: int) -> tuple[dict, bytes]:
    version_id = _key(version_id)
    with get_connection() as connection:
        connection.execute("BEGIN")
        _actor(connection, actor_id)
        row = connection.execute(
            "SELECT v.*,d.user_id FROM document_versions v JOIN documents d ON d.id=v.document_id WHERE v.id=?",
            (version_id,),
        ).fetchone()
        if row is None:
            raise DocumentNotFound()
        _document(connection, actor_id, row["document_id"])
        path = _path(row["user_id"], row["storage_name"])
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(descriptor, "rb") as file:
                info = os.fstat(file.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_DOCUMENT_BYTES:
                    raise DocumentStorageError()
                content = file.read(MAX_DOCUMENT_BYTES + 1)
        except OSError:
            raise DocumentStorageError("Fichier temporairement indisponible.") from None
        if (
            len(content) != row["size_bytes"]
            or hashlib.sha256(content).hexdigest() != row["sha256"]
        ):
            raise DocumentStorageError("Fichier temporairement indisponible.")
        return {"filename": row["filename"], "document_id": row["document_id"]}, content


def add_document_comment(
    actor_id: int,
    version_id: int,
    body: str,
    *,
    kind: str = "message",
    page: int | None = None,
) -> int:
    version_id = _key(version_id)
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        actor = _actor(connection, actor_id)
        version = connection.execute(
            "SELECT document_id FROM document_versions WHERE id=?", (version_id,)
        ).fetchone()
        if version is None:
            raise DocumentNotFound()
        _document(connection, actor_id, version["document_id"])
        body = body.strip()
        if not 1 <= len(body) <= 4000 or kind not in {"message", "annotation"}:
            raise DocumentInputError(
                "Saisis un message ou une annotation de 1 à 4 000 caractères."
            )
        if page is not None and (
            type(page) is not int or not 1 <= page <= 9999 or kind != "annotation"
        ):
            raise DocumentInputError(
                "Le numéro de page doit être compris entre 1 et 9 999 et concerne les annotations."
            )
        cursor = connection.execute(
            "INSERT INTO document_comments(version_id,author_id,author_role,kind,page,body) VALUES (?,?,?,?,?,?)",
            (version_id, actor_id, actor["role"], kind, page, body),
        )
        if cursor.lastrowid is None:
            raise DocumentStorageError()
        return int(version["document_id"])


def delete_document(actor_id: int, document_id: int) -> None:
    staged: list[tuple[Path, Path]] = []
    try:
        with get_connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            document, _ = _document(connection, actor_id, document_id, edit=True)
            for row in connection.execute(
                "SELECT storage_name FROM document_versions WHERE document_id=?",
                (document_id,),
            ):
                original = _path(document["user_id"], row["storage_name"])
                temporary = original.with_name(".deleting-" + original.name)
                if temporary.exists() or temporary.is_symlink():
                    raise DocumentStorageError()
                if original.exists():
                    os.replace(original, temporary)
                    staged.append((original, temporary))
            connection.execute("DELETE FROM documents WHERE id=?", (document_id,))
    except Exception:
        for original, temporary in reversed(staged):
            os.replace(temporary, original)
        raise
    for _, temporary in staged:
        temporary.unlink(missing_ok=True)
