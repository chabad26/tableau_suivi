"""Serveur IMAP en mémoire : aucun socket ni fournisseur réel."""

from email.message import EmailMessage


def recruitment_message(uid: int, mailbox: str) -> bytes:
    message = EmailMessage()
    message["From"] = "Recrutement <rh@entreprise.invalid>"
    message["To"] = mailbox
    message["Subject"] = "Votre candidature au poste de Développeur Python"
    message["Date"] = "Mon, 02 Nov 2026 10:00:00 +0000"
    message["Message-ID"] = f"<{mailbox.replace('@', '-')}-{uid}@demo.invalid>"
    message.set_content(
        "Nous avons bien reçu votre candidature chez Entreprise Fictive."
    )
    return message.as_bytes()


class FakeImap:
    def __init__(self, mailbox: str, *, failed_uids=(), unavailable=False):
        self.mailbox = mailbox
        self.messages = {uid: recruitment_message(uid, mailbox) for uid in (1, 2, 3)}
        self.failed_uids = set(failed_uids)
        self.unavailable = unavailable
        self.uid_validity: int | None = 777
        self.fetched: list[int] = []

    def login(self, username, password):
        return "OK", []

    def select(self, folder, readonly=True):
        if self.unavailable:
            raise RuntimeError("Boîte fictive indisponible")
        assert readonly
        return "OK", [b"3"]

    def response(self, name):
        assert name == "UIDVALIDITY"
        return "OK", [str(self.uid_validity).encode() if self.uid_validity else None]

    def uid(self, command, *args):
        if command == "search":
            minimum = int(args[-1].split(":")[0]) if args[1] == "UID" else 1
            return "OK", [
                " ".join(str(uid) for uid in self.messages if uid >= minimum).encode()
            ]
        if command == "fetch":
            uid = int(args[0])
            self.fetched.append(uid)
            if uid in self.failed_uids:
                return "NO", []
            return "OK", [(b"fixture", self.messages[uid])]
        raise AssertionError("Commande IMAP inattendue")

    def logout(self):
        return "BYE", []
