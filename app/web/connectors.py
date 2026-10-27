from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from app.connectors.status import (
    get_connector_statuses,
)
from app.database import (
    create_imap_account,
    get_imap_accounts,
    update_imap_account,
)
from app.mail_providers import (
    detect_provider_smart,
)
from app.presentation import (
    format_datetime,
)
from app.secrets import (
    set_imap_password,
)
from app.web.jobs import (
    submit_job,
)


connectors_bp = Blueprint(
    "connectors",
    __name__,
)


def get_imap_account(
    account_id: int,
):
    for account in get_imap_accounts():
        if int(account["id"]) == account_id:
            return account

    return None


@connectors_bp.get("/connectors")
def connectors_page():
    connectors = (
        get_connector_statuses()
    )

    imap_accounts = []

    for row in get_imap_accounts():
        account = dict(row)

        account[
            "last_checked_display"
        ] = (
            format_datetime(
                row["last_checked_at"]
            )
            if row["last_checked_at"]
            else "Jamais"
        )

        imap_accounts.append(
            account
        )

    return render_template(
        "connectors.html",
        connectors=connectors,
        imap_accounts=imap_accounts,
    )


@connectors_bp.get(
    "/connectors/imap/add"
)
def add_imap_account():
    return render_template(
        "imap_add.html",
        detected=None,
        email_address="",
    )


@connectors_bp.post(
    "/connectors/imap/detect"
)
def detect_imap_account():
    email_address = (
        request.form.get(
            "email",
            "",
        ).strip()
    )

    provider = (
        detect_provider_smart(
            email_address
        )
    )

    return render_template(
        "imap_add.html",
        detected=provider,
        email_address=email_address,
    )


@connectors_bp.post(
    "/connectors/imap/add"
)
def save_imap_account():
    email_address = (
        request.form.get(
            "email",
            "",
        ).strip()
    )

    provider_key = (
        request.form.get(
            "provider",
            "",
        ).strip()
    )

    auth_method = (
        request.form.get(
            "auth_method",
            "password",
        )
        .strip()
        .casefold()
    )

    host = (
        request.form.get(
            "host",
            "",
        ).strip()
    )

    username = (
        request.form.get(
            "username",
            "",
        ).strip()
    )

    password = request.form.get(
        "password",
        "",
    )

    folder = (
        request.form.get(
            "folder",
            "INBOX",
        ).strip()
        or "INBOX"
    )

    try:
        port = int(
            request.form.get(
                "port",
                "993",
            )
        )
    except ValueError:
        abort(400)

    use_ssl = (
        request.form.get(
            "use_ssl"
        )
        == "on"
    )

    if not email_address:
        abort(400)

    if not host:
        abort(400)

    if not username:
        abort(400)

    if (
        auth_method == "password"
        and not password
    ):
        abort(400)

    if auth_method not in {
        "password",
        "oauth2",
    }:
        abort(400)

    account_id = (
        create_imap_account(
            email=email_address,
            provider=provider_key,
            host=host,
            port=port,
            use_ssl=use_ssl,
            username=username,
            folder=folder,
            auth_method=auth_method,
        )
    )

    if (
        auth_method == "password"
        and password
    ):
        set_imap_password(
            account_id,
            password,
        )

    flash(
        "Boîte IMAP ajoutée.",
        "success",
    )

    return redirect(
        url_for(
            "connectors.connectors_page"
        )
    )


@connectors_bp.post(
    "/connectors/imap/<int:account_id>/test"
)
def test_imap_account_web(
    account_id: int,
):
    account = get_imap_account(
        account_id
    )

    if account is None:
        abort(404)

    return submit_job(
        f"test:imap:{account_id}"
    )


@connectors_bp.get(
    "/connectors/imap/<int:account_id>/edit"
)
def edit_imap_account(
    account_id: int,
):
    account = get_imap_account(
        account_id
    )

    if account is None:
        abort(404)

    return render_template(
        "imap_edit.html",
        account=account,
    )


@connectors_bp.post(
    "/connectors/imap/<int:account_id>/edit"
)
def update_imap_account_web(
    account_id: int,
):
    account = get_imap_account(
        account_id
    )

    if account is None:
        abort(404)

    email_address = (
        request.form.get(
            "email",
            "",
        ).strip()
    )

    provider = (
        request.form.get(
            "provider",
            "",
        ).strip()
    )

    host = (
        request.form.get(
            "host",
            "",
        ).strip()
    )

    username = (
        request.form.get(
            "username",
            "",
        ).strip()
    )

    password = request.form.get(
        "password",
        "",
    )

    auth_method = (
        request.form.get(
            "auth_method",
            "password",
        )
        .strip()
        .casefold()
    )

    folder = (
        request.form.get(
            "folder",
            "INBOX",
        ).strip()
        or "INBOX"
    )

    try:
        port = int(
            request.form.get(
                "port",
                "993",
            )
        )
    except ValueError:
        abort(400)

    use_ssl = (
        request.form.get(
            "use_ssl"
        )
        == "on"
    )

    if not email_address:
        abort(400)

    if not host:
        abort(400)

    if not username:
        abort(400)

    if auth_method not in {
        "password",
        "oauth2",
    }:
        abort(400)

    update_imap_account(
        account_id=account_id,
        email=email_address,
        provider=provider,
        host=host,
        port=port,
        use_ssl=use_ssl,
        username=username,
        folder=folder,
        auth_method=auth_method,
    )

    if (
        auth_method == "password"
        and password
    ):
        set_imap_password(
            account_id,
            password,
        )

    flash(
        "Boîte IMAP mise à jour.",
        "success",
    )

    return redirect(
        url_for(
            "connectors.connectors_page"
        )
    )