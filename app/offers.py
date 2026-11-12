"""Validation du texte et du lien d'offre ; aucun accès réseau."""

from urllib.parse import urlsplit

MAX_OFFER_TEXT_LENGTH = 100_000
MAX_OFFER_URL_LENGTH = 2048


class OfferInputError(ValueError):
    """Message de validation fixe et affichable dans un formulaire."""


def validate_offer(offer_text: str = "", offer_url: str = "") -> tuple[str, str]:
    text = offer_text.strip()
    url = offer_url.strip()
    if len(text) > MAX_OFFER_TEXT_LENGTH:
        raise OfferInputError("Le texte de l'offre est limité à 100 000 caractères.")
    if len(url) > MAX_OFFER_URL_LENGTH:
        raise OfferInputError("Le lien de l'offre est limité à 2 048 caractères.")
    if url:
        try:
            parts = urlsplit(url)
            port = parts.port
            valid = (
                parts.scheme in {"https", "http"}
                and bool(parts.hostname)
                and parts.username is None
                and parts.password is None
                and (port is None or port > 0)
                and not any(
                    char.isspace() or ord(char) < 32 or ord(char) == 127 or char == "\\"
                    for char in url
                )
            )
        except ValueError:
            valid = False
        if not valid:
            raise OfferInputError(
                "Saisis un lien HTTP ou HTTPS valide, sans identifiants ni espaces."
            )
    return text, url
