from __future__ import annotations

from dataclasses import dataclass
import dns.exception
import dns.resolver

@dataclass(frozen=True)
class MailProvider:
    key: str
    name: str
    domains: tuple[str, ...]
    imap_host: str
    imap_port: int = 993
    use_ssl: bool = True
    username_is_email: bool = True
    mx_suffixes: tuple[str, ...] = ()
    auth_method: str = "password"

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
        mx_suffixes=(
            "ovh.net",
        ),
    ),
    MailProvider(
        key="gmail",
        name="Gmail",
        domains=(
            "gmail.com",
            "googlemail.com",
        ),
        imap_host="imap.gmail.com",
        auth_method="oauth2",
    ),

    MailProvider(
        key="microsoft",
        name="Microsoft",
        domains=(
            "outlook.com",
            "hotmail.com",
            "live.com",
            "msn.com",
        ),
        imap_host="outlook.office365.com",
        auth_method="oauth2",
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

def get_mx_hosts(
    email_address: str,
) -> list[str]:
    domain = extract_domain(
        email_address
    )

    if not domain:
        return []

    try:
        answers = dns.resolver.resolve(
            domain,
            "MX",
            lifetime=3.0,
        )

    except (
        dns.resolver.NXDOMAIN,
        dns.resolver.NoAnswer,
        dns.resolver.NoNameservers,
        dns.exception.Timeout,
    ):
        return []

    hosts: list[str] = []

    for answer in answers:
        host = str(
            answer.exchange
        ).rstrip(
            "."
        ).casefold()

        hosts.append(host)

    return hosts

def detect_provider_by_mx(
    email_address: str,
) -> MailProvider | None:
    mx_hosts = get_mx_hosts(
        email_address
    )

    for provider in MAIL_PROVIDERS:

        if not provider.mx_suffixes:
            continue

        for host in mx_hosts:

            if any(
                host == suffix
                or host.endswith(
                    "." + suffix
                )
                for suffix
                in provider.mx_suffixes
            ):
                return provider

    return None

def detect_provider_smart(
    email_address: str,
) -> MailProvider | None:
    provider = detect_provider(
        email_address
    )

    if provider is not None:
        return provider

    return detect_provider_by_mx(
        email_address
    )

def get_provider(
    key: str,
) -> MailProvider | None:
    normalized_key = key.strip().casefold()

    for provider in MAIL_PROVIDERS:
        if provider.key == normalized_key:
            return provider

    return None