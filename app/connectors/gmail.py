import json

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from app.oauth_store import locked_oauth_account, read_oauth_cache, write_oauth_cache
from app.settings import GMAIL_CREDENTIALS_FILE, GMAIL_TOKEN_FILE

SCOPES = ["https://mail.google.com/"]

CREDENTIALS_FILE = GMAIL_CREDENTIALS_FILE

TOKEN_FILE = GMAIL_TOKEN_FILE


def get_credentials() -> Credentials:
    credentials: Credentials | None = None

    if TOKEN_FILE.exists():
        try:
            credentials = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

        except ValueError, OSError:
            credentials = None

    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())

        except RefreshError:
            credentials = None

            try:
                TOKEN_FILE.unlink(missing_ok=True)
            except OSError:
                pass

    if not credentials or not credentials.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)

        credentials = flow.run_local_server(port=0)

    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)

    TOKEN_FILE.write_text(credentials.to_json(), encoding="utf-8")

    return credentials


def _get_owned_gmail_token_unlocked(
    user_id: int, account_id: int, expected_email: str
) -> str:
    """Récupère un jeton Gmail privé après vérification de l'identité."""

    content = read_oauth_cache(user_id, account_id, "gmail")

    if not content:
        raise RuntimeError(
            "Autorisation Gmail absente. Ce compte doit être connecté via OAuth."
        )

    try:
        info = json.loads(content)

        credentials = Credentials.from_authorized_user_info(info, SCOPES)

    except (ValueError, TypeError, KeyError) as error:
        raise RuntimeError("Cache OAuth Gmail invalide.") from error

    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())

        except RefreshError as error:
            raise RuntimeError("Autorisation Gmail expirée ou révoquée.") from error

    if not credentials.valid or not credentials.token:
        raise RuntimeError("Aucun jeton Gmail valide.")

    # Ne jamais se fier uniquement au nom de fichier.
    # On vérifie l'adresse réellement associée au jeton.
    with AuthorizedSession(credentials) as session:
        response = session.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/profile", timeout=15
        )

        response.raise_for_status()

        profile = response.json()

    actual_email = str(profile.get("emailAddress", "")).strip().casefold()

    if actual_email != expected_email.strip().casefold():
        raise RuntimeError(
            "L'identité Gmail autorisée ne correspond pas à la boîte IMAP configurée."
        )

    # Le cache n'est enregistré qu'après vérification.
    write_oauth_cache(user_id, account_id, "gmail", credentials.to_json())

    return str(credentials.token)


def get_owned_gmail_token(user_id: int, account_id: int, expected_email: str) -> str:
    """Lit, vérifie et renouvelle le jeton Gmail sous verrou."""

    with locked_oauth_account(user_id, account_id, "gmail"):
        return _get_owned_gmail_token_unlocked(user_id, account_id, expected_email)
