from app.mail_providers import detect_provider


for address in (
    "test@sfr.fr",
    "test@neuf.fr",
    "test@orange.fr",
    "test@wanadoo.fr",
    "test@free.fr",
    "test@laposte.net",
    "test@sabledoux.fr",
):
    provider = detect_provider(address)

    print(
        address,
        "->",
        provider.name
        if provider
        else "Inconnu",
    )