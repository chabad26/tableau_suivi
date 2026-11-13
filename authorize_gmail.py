"""Réautorisation Gmail explicite, depuis le terminal, pour une seule boîte."""

import argparse

from google.auth.transport.requests import AuthorizedSession
from google_auth_oauthlib.flow import InstalledAppFlow

from app.connectors import gmail
from app.oauth_store import locked_oauth_account, oauth_token_path, write_oauth_cache
from app.owned_imap import get_user_imap_account


def authorize_gmail_account(user_id: int, account_id: int) -> None:
    """Vérifie la propriété et l'identité Google avant toute écriture de cache."""
    # Valide utilisateur actif, propriétaire, fournisseur, méthode et activation.
    oauth_token_path(user_id, account_id, "gmail")
    account = get_user_imap_account(user_id, account_id)
    if account is None:
        raise ValueError("Compte introuvable.")
    expected = str(account["username"]).strip().casefold()
    flow = InstalledAppFlow.from_client_secrets_file(
        str(gmail.CREDENTIALS_FILE), gmail.SCOPES
    )
    credentials = flow.run_local_server(
        host="127.0.0.1",
        port=0,
        timeout_seconds=180,
        access_type="offline",
        prompt="consent",
        authorization_prompt_message="Ouvre ce lien pour autoriser la boîte Gmail configurée : {url}",
        success_message="Autorisation reçue. Reviens dans le terminal pour connaître le résultat de la vérification.",
    )
    if not credentials.valid or not credentials.refresh_token:
        raise ValueError("Autorisation Gmail renouvelable absente.")
    with AuthorizedSession(credentials) as session:
        response = session.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/profile", timeout=15
        )
        response.raise_for_status()
        actual = str(response.json().get("emailAddress", "")).strip().casefold()
    if actual != expected:
        raise ValueError(
            "Le compte Google choisi ne correspond pas à la boîte configurée."
        )
    with locked_oauth_account(user_id, account_id, "gmail"):
        current = get_user_imap_account(user_id, account_id)
        if current is None or str(current["username"]).strip().casefold() != expected:
            raise ValueError(
                "La configuration du compte a changé pendant l'autorisation."
            )
        write_oauth_cache(user_id, account_id, "gmail", credentials.to_json())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--account-id", type=int, required=True)
    args = parser.parse_args()
    try:
        authorize_gmail_account(args.user_id, args.account_id)
    except Exception as error:
        # Les réponses OAuth peuvent contenir des secrets : ne jamais les recopier.
        parser.exit(
            1,
            f"Autorisation non enregistrée ({type(error).__name__}). Vérifie le compte choisi, la configuration OAuth et le réseau ; le cache existant a été conservé.\n",
        )
    print(
        "Autorisation Gmail enregistrée après vérification de l'identité. Aucun email importé."
    )


if __name__ == "__main__":
    main()
