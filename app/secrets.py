import keyring
from keyring.errors import PasswordDeleteError


SERVICE_NAME = "job-tracker-imap"


def set_imap_password(
    account_id: int,
    password: str,
) -> None:
    keyring.set_password(
        SERVICE_NAME,
        str(account_id),
        password,
    )


def get_imap_password(
    account_id: int,
) -> str | None:
    return keyring.get_password(
        SERVICE_NAME,
        str(account_id),
    )


def delete_imap_password(
    account_id: int,
) -> None:
    try:
        keyring.delete_password(
            SERVICE_NAME,
            str(account_id),
        )
    except PasswordDeleteError:
        pass