"""Documents CV/LM : espace personnel et échanges avec l'équipe pédagogique."""

import io
import sqlite3

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required

from app.admin_accounts import list_managed_promotions
from app.documents import (
    DOCUMENT_KINDS,
    MAX_DOCUMENT_BYTES,
    DocumentInputError,
    DocumentNotFound,
    DocumentStorageError,
    add_document_comment,
    delete_document,
    document_detail,
    download_document,
    list_document_learners,
    list_documents,
    upload_document,
)

documents_bp = Blueprint("documents", __name__, url_prefix="/documents")


@documents_bp.errorhandler(DocumentNotFound)
def not_found(_error):
    return render_template(
        "documents/error.html", message="Document ou apprenant introuvable."
    ), 404


@documents_bp.errorhandler(PermissionError)
def forbidden(_error):
    return render_template(
        "documents/error.html", message="Cet accès n'est pas autorisé."
    ), 403


def storage_failure(_error):
    current_app.logger.warning("Opération sur les documents indisponible")
    return render_template(
        "documents/error.html",
        message="Le document est temporairement indisponible. Réessaie plus tard.",
    ), 503


for error_type in (DocumentStorageError, OSError, sqlite3.Error):
    documents_bp.register_error_handler(error_type, storage_failure)


def _actor_id() -> int:
    return int(current_user.get_id())


def _identifier(value: str) -> int:
    try:
        identifier = int(value)
    except ValueError:
        raise DocumentNotFound() from None
    if not 0 < identifier < 2**63:
        raise DocumentNotFound()
    return identifier


def _listing(error: str | None = None):
    actor_id = _actor_id()
    promotions, promotion = [], ""
    if current_user.role == "admin":
        promotions = list_managed_promotions(actor_id)
        selected = request.args.get("learner", "")
        owner_id = _identifier(selected) if selected else None
        promotion = request.args.get("promotion", "")
        # Les liens déjà ouverts vers un apprenant retrouvent sa promotion.
        if not promotion and owner_id is not None:
            owner, _ = list_documents(actor_id, owner_id)
            promotion = (
                str(owner["promotion_id"])
                if owner["promotion_id"] is not None
                else "unassigned"
            )
        if promotion and promotion != "unassigned":
            promotion = str(_identifier(promotion))
            if int(promotion) not in {row["id"] for row in promotions}:
                raise DocumentNotFound()
        learners = (
            list_document_learners(actor_id, promotion=promotion) if promotion else []
        )
        if owner_id is not None and owner_id not in {row["id"] for row in learners}:
            raise DocumentNotFound()
    elif current_user.role == "student":
        learners, owner_id = [], actor_id
        if (
            request.args.get("learner")
            and _identifier(request.args["learner"]) != actor_id
        ):
            raise DocumentNotFound()
    else:
        raise PermissionError()
    owner, documents = (
        list_documents(actor_id, owner_id) if owner_id is not None else (None, [])
    )
    return render_template(
        "documents/list.html",
        owner=owner,
        documents=documents,
        learners=learners,
        promotions=promotions,
        selected_promotion=promotion,
        kinds=DOCUMENT_KINDS,
        is_owner=current_user.role == "student",
        error=error,
        values=request.form,
    )


@documents_bp.get("")
@login_required
def list_page():
    return _listing()


def _read_upload() -> tuple[str, bytes]:
    if current_user.role != "student":
        raise PermissionError()
    file = request.files.get("file")
    if file is None or not file.filename:
        raise DocumentInputError("Choisis le fichier à déposer.")
    return file.filename, file.stream.read(MAX_DOCUMENT_BYTES + 1)


@documents_bp.post("")
@login_required
def upload_document_web():
    try:
        filename, content = _read_upload()
        document_id, _ = upload_document(
            _actor_id(),
            filename,
            content,
            kind=request.form.get("kind", ""),
            title=request.form.get("title", ""),
        )
    except DocumentInputError as error:
        return _listing(str(error)), 400
    flash("Document déposé. Tu peux maintenant échanger sur cette version.", "success")
    return redirect(url_for("documents.detail_page", document_id=document_id), code=303)


def _render_detail(data: dict, error: str | None = None):
    return render_template(
        "documents/detail.html",
        **data,
        kinds=DOCUMENT_KINDS,
        is_owner=current_user.role == "student",
        error=error,
        values=request.form,
    )


@documents_bp.get("/<int:document_id>")
@login_required
def detail_page(document_id: int):
    raw = request.args.get("version")
    version_id = _identifier(raw) if raw else None
    return _render_detail(document_detail(_actor_id(), document_id, version_id))


@documents_bp.post("/<int:document_id>/versions")
@login_required
def upload_version_web(document_id: int):
    data = document_detail(_actor_id(), document_id)
    try:
        filename, content = _read_upload()
        _, version_id = upload_document(
            _actor_id(), filename, content, document_id=document_id
        )
    except DocumentInputError as error:
        return _render_detail(data, str(error)), 400
    flash(
        "Nouvelle version déposée. Les précédentes versions et leurs échanges sont conservés.",
        "success",
    )
    return redirect(
        url_for("documents.detail_page", document_id=document_id, version=version_id),
        code=303,
    )


@documents_bp.get("/versions/<int:version_id>/download")
@login_required
def download_web(version_id: int):
    metadata, content = download_document(_actor_id(), version_id)
    mime = (
        "application/pdf"
        if metadata["filename"].endswith(".pdf")
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    response = send_file(
        io.BytesIO(content),
        download_name=metadata["filename"],
        as_attachment=True,
        mimetype=mime,
        max_age=0,
    )
    response.headers["Content-Security-Policy"] = "sandbox; default-src 'none'"
    return response


@documents_bp.post("/<int:document_id>/versions/<int:version_id>/comments")
@login_required
def add_comment_web(document_id: int, version_id: int):
    data = document_detail(_actor_id(), document_id, version_id)
    try:
        raw_page = request.form.get("page", "").strip()
        try:
            page = int(raw_page) if raw_page else None
        except ValueError:
            raise DocumentInputError(
                "Saisis un numéro de page valide pour l'annotation."
            ) from None
        add_document_comment(
            _actor_id(),
            version_id,
            request.form.get("body", ""),
            kind=request.form.get("kind", "message"),
            page=page,
        )
    except DocumentInputError as error:
        return _render_detail(data, str(error)), 400
    return redirect(
        url_for(
            "documents.detail_page",
            document_id=document_id,
            version=version_id,
            _anchor="discussion",
        ),
        code=303,
    )


@documents_bp.post("/<int:document_id>/delete")
@login_required
def delete_document_web(document_id: int):
    delete_document(_actor_id(), document_id)
    flash("Document, versions et échanges supprimés.", "success")
    return redirect(url_for("documents.list_page"), code=303)
