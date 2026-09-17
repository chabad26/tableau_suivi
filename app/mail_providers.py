from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MailProvider:
    key: str
    name: str
    domains: tuple[str, ...]
    imap_host: str
    imap_port: int = 993
    use_ssl: bool = True
    username_is_email: bool = True


MAIL_PROVIDERS: tuple[MailProvider, ...] = (
    MailProvider(
        key="sfr",
        name="SFR",
        domains=(
            "sfr.fr",
            "neuf.fr",
            "cegetel.net",
            "9online.fr",
            "club-internet.fr",
        ),
        imap_host="imap.sfr.fr",
    ),
    MailProvider(
        key="orange",
        name="Orange",
        domains=(
            "orange.fr",
            "wanadoo.fr",
        ),
        imap_host="imap.orange.fr",
    ),
    MailProvider(
        key="free",
        name="Free",
        domains=(
            "free.fr",
        ),
        imap_host="imap.free.fr",
    ),
    MailProvider(
        key="laposte",
        name="LaPoste.net",
        domains=(
            "laposte.net",
        ),
        imap_host="imap.laposte.net",
    ),
    MailProvider(
        key="infomaniak",
        name="Infomaniak",
        domains=(),
        imap_host="mail.infomaniak.com",
    ),
    MailProvider(
        key="ovh",
        name="OVHcloud",
        domains=(),
        imap_host="ssl0.ovh.net",
    ),
)

def extract_domain(email_address: str) -> str:
    value = email_address.strip().casefold()

    if "@" not in value:
        return ""

    _, domain = value.rsplit("@", 1)

    return domain.strip()


def detect_provider(
    email_address: str,
) -> MailProvider | None:
    domain = extract_domain(
        email_address
    )

    if not domain:
        return None

    for provider in MAIL_PROVIDERS:
        if domain in provider.domains:
            return provider

    return None


def get_provider(
    key: str,
) -> MailProvider | None:
    normalized_key = key.strip().casefold()

    for provider in MAIL_PROVIDERS:
        if provider.key == normalized_key:
            return provider

    return None