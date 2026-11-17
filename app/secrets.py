import keyring

SERVICE_NAME = "job-tracker-imap"


def set_imap_password(account_id: int, password: str) -> None:
    keyring.set_password(SERVICE_NAME, str(account_id), password)


def get_imap_password(account_id: int) -> str | None:
    return keyring.get_password(SERVICE_NAME, str(account_id))
