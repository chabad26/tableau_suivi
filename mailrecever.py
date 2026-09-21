import html
import mailbox
import re
import unicodedata
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import TypedDict

from app.settings import MAILBOX_START_DATE, configured_mailboxes

PROFILE = Path("/home/oliv/snap/thunderbird/common/.thunderbird/jzmiasv2.default")


MAILBOXES: dict[str, Path] = {
    "Gmail": PROFILE / "ImapMail/imap.gmail.com/INBOX",
    "Outlook": PROFILE / "ImapMail/outlook.office365.com/INBOX",
    "OVH": PROFILE / "ImapMail/ssl0.ovh.net/INBOX",
}

MAILBOXES = configured_mailboxes(MAILBOXES)
START_DATE = MAILBOX_START_DATE


POSITIVE_KEYWORDS = [
    "votre candidature",
    "merci pour votre candidature",
    "merci d'avoir postulé",
    "merci d’avoir postulé",
    "suite à votre candidature",
    "réception de votre candidature",
    "nous avons bien reçu votre candidature",
    "candidature est arrivée",
    "candidature pour l'offre",
    "candidature pour l’offre",
    "candidature retenue",
    "candidature non retenue",
    "confirmation de votre candidature",
    "entretien",
    "convocation",
    "processus de recrutement",
    "échange téléphonique",
    "entretien téléphonique",
    "entretien technique",
    "test technique",
]


RECRUITMENT_SENDERS = [
    "teamtailor",
    "beetween",
    "icims",
    "jobs2web",
    "careers",
    "recrutement",
    "talent",
    "hrsystem",
    "hellowork",
    "indeed",
    "linkedin",
    "recruitee",
    "digitalrecruiters",
]


NEGATIVE_KEYWORDS = [
    "alerte emploi",
    "alertes linkedin jobs",
    "nouvelles offres",
    "nouvelle offre",
    "recrute au poste de",
    "jobs disponibles",
    "offres d'emploi",
    "offres emploi",
    "job alert",
    "jobalert",
    "newsletter",
    "votre profil est apparu",
    "ajoutez ",
    "déposez votre candidature maintenant",
    "deposez votre candidature maintenant",
]


BLACKLIST_SENDERS = ["locservice", "locservice.fr"]


STATUS_LABELS = {
    "SENT": "Candidature envoyée",
    "RECEIVED": "Candidature reçue",
    "INTERVIEW": "Entretien",
    "REJECTED": "Refus",
    "TEST": "Test technique",
    "OFFER": "Offre",
    "OTHER": "À analyser",
    "PROPOSED": "Proposée",
}


@dataclass
class DetectedEmail:
    mailbox: str
    date: datetime
    sender: str
    subject: str
    message_id: str
    score: int
    status: str
    reasons: list[str]


EmailResult = TypedDict(
    "EmailResult",
    {
        "mailbox": str,
        "date": datetime,
        "from": str,
        "subject": str,
        "message_id": str,
        "score": int,
        "status": str,
        "reasons": list[str],
    },
)


def html_to_text(content: str) -> str:
    """
    Conversion HTML légère vers texte brut.
    Suffisant pour l'analyse des emails de recrutement.
    """

    # Supprime scripts et styles
    content = re.sub(
        r"<(script|style).*?>.*?</\1>", " ", content, flags=re.IGNORECASE | re.DOTALL
    )

    # Quelques balises doivent devenir des espaces / retours
    content = re.sub(r"<br\s*/?>", "\n", content, flags=re.IGNORECASE)

    content = re.sub(r"</p\s*>", "\n", content, flags=re.IGNORECASE)

    # Supprime toutes les autres balises
    content = re.sub(r"<[^>]+>", " ", content)

    content = html.unescape(content)

    content = re.sub(r"[ \t]+", " ", content)

    content = re.sub(r"\n\s*\n+", "\n", content)

    return content.strip()


def decode_text(value: str | None) -> str:
    if not value:
        return ""

    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return str(value)


def normalize(text: str | None) -> str:
    if not text:
        return ""

    #
    # Décode les entités HTML :
    # &eacute; -> é
    # &nbsp;   -> espace
    # &#39;    -> '
    #
    text = html.unescape(text)

    #
    # Normalisation Unicode
    #
    text = unicodedata.normalize("NFKC", text)

    #
    # Espaces Unicode / caractères invisibles
    #
    invisible_chars = [
        "\u200b",  # zero width space
        "\u200c",
        "\u200d",
        "\u2060",
        "\ufeff",
        "\u00ad",
    ]
    text = re.sub(
        r"\b(pourrons|pouvons|pourrait|pourra|sera)pas\b",
        r"\1 pas",
        text,
        flags=re.IGNORECASE,
    )

    for char in invisible_chars:
        text = text.replace(char, "")

    text = text.replace("\u00a0", " ")

    #
    # Espaces multiples / retours ligne
    #
    text = re.sub(r"\s+", " ", text)

    return text.strip().casefold()


def get_body(message: Message) -> str:
    """
    Extrait le texte d'un email, qu'il soit text/plain,
    text/html ou multipart.
    """

    plain_parts: list[str] = []
    html_parts: list[str] = []

    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()

            disposition = part.get_content_disposition()

            # Ignore les pièces jointes
            if disposition == "attachment":
                continue

            if content_type not in ("text/plain", "text/html"):
                continue

            payload = part.get_payload(decode=True)

            if not isinstance(payload, bytes):
                continue

            charset = part.get_content_charset() or "utf-8"

            try:
                text = payload.decode(charset, errors="replace")
            except LookupError:
                text = payload.decode("utf-8", errors="replace")

            if content_type == "text/plain":
                plain_parts.append(text)

            elif content_type == "text/html":
                html_parts.append(html_to_text(text))

    else:
        content_type = message.get_content_type()

        payload = message.get_payload(decode=True)

        if isinstance(payload, bytes):
            charset = message.get_content_charset() or "utf-8"

            try:
                text = payload.decode(charset, errors="replace")
            except LookupError:
                text = payload.decode("utf-8", errors="replace")

            if content_type == "text/html":
                html_parts.append(html_to_text(text))
            else:
                plain_parts.append(text)

    #
    # On privilégie text/plain.
    # HTML sert de fallback si le mail n'a pas de version texte.
    #
    if plain_parts:
        return "\n".join(plain_parts).strip()

    if html_parts:
        return "\n".join(html_parts).strip()

    return ""


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        date = parsedate_to_datetime(value)

        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)

        return date

    except Exception:
        return None


def is_blacklisted_sender(sender: str) -> bool:
    sender = normalize(sender)

    return any(blocked in sender for blocked in BLACKLIST_SENDERS)


def contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def detect_status(subject: str, body: str) -> str:
    """
    Détermine le statut d'une candidature.

    Principe :
    1. Le sujet du mail est prioritaire.
    2. Le corps n'est utilisé que si le sujet ne permet pas
       de déterminer clairement le statut.
    3. Dans le corps, on n'utilise que des formulations fortes
       pour éviter les faux positifs.
    """

    subject_text = normalize(subject)
    body_text = normalize(body)

    # ------------------------------------------------------------------
    # REFUS
    # ------------------------------------------------------------------

    rejected_subject = [
        "n'est pas retenue",
        "n'est pas retenu",
        "n'a pas été retenue",
        "n'a pas été retenu",
        "candidature non retenue",
        "profil non retenu",
        "ne donnerons pas suite",
        "ne donnons pas suite",
        "ne donnerons malheureusement pas suite",
        "ne donnons malheureusement pas suite",
        "nous ne donnerons pas suite",
        "nous ne donnons pas suite",
        "ne pourrons pas donner suite",
        "ne pouvons pas donner suite",
        "ne pourrons malheureusement pas donner suite",
        "ne pouvons malheureusement pas donner suite",
        "nous ne pourrons pas donner suite",
        "nous ne pouvons pas donner suite",
        "nous ne pourrons malheureusement pas donner suite",
        "nous ne pouvons malheureusement pas donner suite",
        "candidature rejetée",
        "candidature rejetee",
        "candidature refusée",
        "candidature refusee",
        r"\bne\s+(?:pourrons|pouvons|pourrions|donnerons)\s+pas\s+donner\s+suite\b",
        r"\bne\s+donnerons\s+pas\s+suite\b",
        r"\bne\s+pouvons\s+pas\s+donner\s+suite\b",
        r"\bne\s+pourrons\s+pas\s+donner\s+suite\b",
        # English
        "application unsuccessful",
        "application not successful",
        "application was unsuccessful",
        "not moving forward",
        "will not be moving forward",
        "not selected",
        "not been selected",
        "application declined",
        "application rejected",
        "we regret to inform you",
        "we regret to inform you that",
        "we regret to inform you that your application",
        "we regret to inform you that your application has not been successful",
        "we regret to inform you that your application has not been successful at this time",
        "we regret to inform you that your application has not been successful at this time and we will not be progressing your application",
        "we regret to inform you that your application has not been successful at this time and we will not be progressing your application further",
    ]

    if contains_any(subject_text, rejected_subject):
        return "REJECTED"

    # ------------------------------------------------------------------
    # ENTRETIEN
    # ------------------------------------------------------------------

    interview_subject = [
        "invitation à un entretien",
        "invitation a un entretien",
        "entretien téléphonique",
        "entretien telephonique",
        "entretien technique",
        "entretien rh",
        "convocation entretien",
        "rendez-vous entretien",
        # English
        "interview invitation",
        "invitation to interview",
        "phone interview",
        "telephone interview",
        "technical interview",
        "hr interview",
        "video interview",
        "interview scheduled",
        "interview confirmation",
    ]

    if contains_any(subject_text, interview_subject):
        return "INTERVIEW"

    # ------------------------------------------------------------------
    # TEST TECHNIQUE
    # ------------------------------------------------------------------

    test_subject = [
        "test technique",
        "coding test",
        "technical test",
        "technical assessment",
        "exercice technique",
        "cas pratique",
        # English
        "coding challenge",
        "coding assessment",
        "technical challenge",
        "take-home test",
        "take home test",
        "online assessment",
        "skills assessment",
    ]

    if contains_any(subject_text, test_subject):
        return "TEST"

    # ------------------------------------------------------------------
    # OFFRE
    # ------------------------------------------------------------------

    # Attention : on évite volontairement "offre d'emploi".
    offer_subject = [
        "offre d'embauche",
        "proposition d'embauche",
        "promesse d'embauche",
        "proposition salariale",
        "nous souhaitons vous faire une offre",
        # English
        "job offer",
        "employment offer",
        "offer of employment",
        "offer letter",
        "employment proposal",
        "salary offer",
    ]

    if contains_any(subject_text, offer_subject):
        return "OFFER"

    # ------------------------------------------------------------------
    # CANDIDATURE ENVOYÉE
    # ------------------------------------------------------------------

    sent_subject = [
        "votre candidature a été envoyée",
        "votre candidature a ete envoyee",
        # English
        "your application has been sent",
        "application submitted",
        "application successfully submitted",
        "your application was submitted",
    ]

    if contains_any(subject_text, sent_subject):
        return "SENT"

    # ------------------------------------------------------------------
    # CANDIDATURE REÇUE
    # ------------------------------------------------------------------

    received_subject = [
        "merci pour votre candidature",
        "merci de votre candidature",
        "merci d'avoir postulé",
        "merci d'avoir envoye votre candidature",
        "nous avons bien reçu votre candidature",
        "nous avons bien recu votre candidature",
        "réception de votre candidature",
        "reception de votre candidature",
        "candidature est arrivée",
        "candidature est arrivee",
        "confirmation de votre candidature",
        "confirmation de l'enregistrement de votre candidature",
        # English
        "thank you for your application",
        "thank you for applying",
        "we received your application",
        "we have received your application",
        "application received",
        "application confirmation",
        "confirmation of your application",
    ]

    if contains_any(subject_text, received_subject):
        return "RECEIVED"

    # ------------------------------------------------------------------
    # ANALYSE DU CORPS
    #
    # Seulement si le sujet n'a rien permis de déterminer.
    # Les expressions utilisées ici sont volontairement plus strictes.
    # ------------------------------------------------------------------

    rejected_body = [
        "nous avons décidé de ne pas donner suite à votre candidature",
        "nous avons decide de ne pas donner suite a votre candidature",
        "nous ne donnerons malheureusement pas suite à votre candidature",
        "nous ne donnerons malheureusement pas suite a votre candidature",
        "votre candidature n'a pas été retenue",
        "votre candidature n'a pas ete retenue",
        "nous avons retenu un autre candidat",
        "nous avons retenu une autre candidature",
        "votre profil ne correspond malheureusement pas aux opportunités ouvertes actuellement",
        "votre profil ne correspond malheureusement pas aux opportunites ouvertes actuellement",
        "votre profil ne correspond pas aux opportunités ouvertes actuellement",
        "votre profil ne correspond pas aux opportunites ouvertes actuellement",
        "votre profil ne correspond malheureusement pas à nos besoins actuels",
        "votre profil ne correspond malheureusement pas a nos besoins actuels",
        "nous ne sommes pas en mesure de donner une suite favorable à votre candidature",
        "nous ne sommes pas en mesure de donner une suite favorable a votre candidature",
        "nous ne pouvons malheureusement pas donner suite à votre candidature",
        "nous ne pouvons malheureusement pas donner suite a votre candidature",
        "nous avons choisi de poursuivre avec d'autres candidats",
        "nous avons choisi de poursuivre avec d’autres candidats",
        # English
        "we have decided not to move forward with your application",
        "we have decided not to proceed with your application",
        "we will not be moving forward with your application",
        "we will not be proceeding with your application",
        "we are not moving forward with your application",
        "we are unable to move forward with your application",
        "we have decided to move forward with other candidates",
        "we have chosen to move forward with other candidates",
        "we have selected another candidate",
        "we have selected other candidates",
        "your application was not successful",
        "your application has not been successful",
        "your application was unsuccessful",
        "your application has been unsuccessful",
        "your application was not selected",
        "your application has not been selected",
        "your profile does not match our current needs",
        "your profile does not match our current requirements",
        "your experience does not match our current needs",
        "unfortunately we will not be progressing your application",
        "unfortunately we will not be proceeding with your application",
        "we regret to inform you that",
    ]

    if contains_any(body_text, rejected_body):
        return "REJECTED"

    interview_body = [
        "nous souhaitons vous rencontrer",
        "nous souhaiterions vous rencontrer",
        "nous vous proposons un entretien",
        "nous souhaitons organiser un entretien",
        "nous souhaiterions organiser un entretien",
        "nous vous invitons à un entretien",
        "nous vous invitons a un entretien",
        "nous souhaitons échanger avec vous",
        "nous souhaitons echanger avec vous",
        # English
        "we would like to invite you to an interview",
        "we would like to schedule an interview",
        "we would like to arrange an interview",
        "we would like to speak with you",
        "we would like to discuss your application",
        "we would like to meet with you",
        "we would like to schedule a call",
        "we would like to arrange a call",
    ]

    if contains_any(body_text, interview_body):
        return "INTERVIEW"

    test_body = [
        "nous vous invitons à réaliser un test technique",
        "nous vous invitons a realiser un test technique",
        "nous vous proposons un test technique",
        "nous vous proposons un exercice technique",
        # English
        "we would like you to complete a technical test",
        "we would like you to complete a coding test",
        "we would like you to complete a coding challenge",
        "we invite you to complete a technical assessment",
        "please complete the technical assessment",
        "please complete the coding challenge",
    ]

    if contains_any(body_text, test_body):
        return "TEST"

    offer_body = [
        "nous souhaitons vous proposer un contrat",
        "nous souhaitons vous faire une proposition d'embauche",
        "nous sommes heureux de vous proposer le poste",
        "nous avons le plaisir de vous proposer le poste",
        # English
        "we are pleased to offer you the position",
        "we are happy to offer you the position",
        "we would like to offer you the position",
        "we would like to offer you the role",
        "we are pleased to offer you employment",
        "we would like to make you an offer",
    ]

    if contains_any(body_text, offer_body):
        return "OFFER"
    # Cas du genre :
    # "Votre candidature : Développeur Full Stack..."
    if subject_text.startswith("votre candidature"):
        return "RECEIVED"
    return "OTHER"


def score_message(message: Message) -> tuple[int, list[str], str]:

    subject = normalize(message.get("Subject"))

    sender = normalize(message.get("From"))

    score = 0
    reasons: list[str] = []

    # Sujet positif
    for keyword in POSITIVE_KEYWORDS:
        if keyword in subject:
            score += 5
            reasons.append(f"sujet:{keyword}")

    # Expéditeur orienté recrutement
    for keyword in RECRUITMENT_SENDERS:
        if keyword in sender:
            score += 1
            reasons.append(f"expéditeur:{keyword}")

    # Bruit évident
    for keyword in NEGATIVE_KEYWORDS:
        if keyword in subject:
            score -= 6
            reasons.append(f"bruit:{keyword}")

    #
    # On ne décode le corps que si le mail
    # est encore potentiellement intéressant.
    #
    body = ""

    if -2 < score < 5:
        body = normalize(get_body(message))

        for keyword in POSITIVE_KEYWORDS:
            if keyword in body:
                score += 2
                reasons.append(f"corps:{keyword}")

        for keyword in NEGATIVE_KEYWORDS:
            if keyword in body:
                score -= 2
                reasons.append(f"bruit-corps:{keyword}")

    if not body:
        body = normalize(get_body(message))

    return score, reasons, body


def scan_mailbox(name: str, path: Path) -> list[EmailResult]:
    if not path.exists():
        print(f"⚠ Boîte introuvable : {path}")

        return []

    print()
    print("=" * 100)
    print(f"📬 Analyse de la boîte {name}")
    print("=" * 100)

    results: list[EmailResult] = []

    mbox = mailbox.mbox(path, create=False)

    scanned = 0
    ignored_old = 0
    ignored_blacklist = 0
    ignored_noise = 0

    with closing(mbox):
        for message in mbox:
            scanned += 1

            #
            # DATE
            #
            date = parse_date(message.get("Date"))

            if date is None:
                continue

            date_utc = date.astimezone(timezone.utc)

            if date_utc < START_DATE:
                ignored_old += 1
                continue

            #
            # EXPÉDITEUR
            #
            sender = decode_text(message.get("From"))

            if is_blacklisted_sender(sender):
                ignored_blacklist += 1
                continue

            #
            # SCORE
            #
            score, reasons, body = score_message(message)

            if score < 4:
                ignored_noise += 1
                continue

            #
            # Si score_message n'a pas eu besoin
            # du corps, on le récupère maintenant
            # pour classifier correctement le statut.
            #
            if not body:
                body = get_body(message)

            subject = decode_text(message.get("Subject"))

            status = detect_status(subject, body)

            results.append(
                {
                    "mailbox": name,
                    "date": date,
                    "from": sender,
                    "subject": subject,
                    "message_id": decode_text(message.get("Message-ID")),
                    "score": score,
                    "status": status,
                    "reasons": reasons,
                }
            )

    print(f"{scanned} mails parcourus")

    print(f"{ignored_old} ignorés car antérieurs au 01/08/2026")

    print(f"{ignored_blacklist} ignorés car leur expéditeur figure sur la liste noire")

    print(f"{ignored_noise} ignorés comme bruit")

    print(f"{len(results)} candidatures potentielles trouvées")

    return results


def print_review_section(results: list[EmailResult]) -> None:
    print()
    print("=" * 100)
    print("🔎 À VÉRIFIER")
    print("=" * 100)

    review = [r for r in results if r["status"] in {"OFFER", "OTHER"}]

    if not review:
        print("Aucun cas douteux.")
        return

    for result in review:
        print()
        print("-" * 100)
        print(f"Date    : {result['date'].strftime('%d/%m/%Y %H:%M')}")
        print(f"Boîte   : {result['mailbox']}")
        print(f"De      : {result['from']}")
        print(f"Sujet   : {result['subject']}")
        print(f"Statut  : {STATUS_LABELS[result['status']]} [{result['status']}]")
        print(f"Score   : {result['score']}")


def print_recent_results(results: list[EmailResult], hours: int = 24) -> None:
    now = datetime.now(timezone.utc)
    limit = now - timedelta(hours=hours)

    recent = [r for r in results if r["date"].astimezone(timezone.utc) >= limit]

    print()
    print("=" * 100)
    print(f"🆕 CANDIDATURES DÉTECTÉES SUR LES {hours} DERNIÈRES HEURES")
    print("=" * 100)

    if not recent:
        print("Aucune nouvelle candidature détectée.")
        return

    for result in recent:
        print()
        print("-" * 100)
        print(f"Date    : {result['date'].strftime('%d/%m/%Y %H:%M')}")
        print(f"Boîte   : {result['mailbox']}")
        print(f"De      : {result['from']}")
        print(f"Sujet   : {result['subject']}")
        print(f"Statut  : {STATUS_LABELS[result['status']]} [{result['status']}]")


def main() -> None:

    all_results: list[EmailResult] = []

    for name, path in MAILBOXES.items():
        results = scan_mailbox(name, path)

        all_results.extend(results)

    #
    # Du plus récent au plus ancien
    #
    all_results.sort(
        key=lambda x: x["date"].timestamp() if x["date"] else 0, reverse=True
    )

    print()
    print()
    print("#" * 100)
    print("🎯 CANDIDATURES DÉTECTÉES")
    print("#" * 100)

    status_counter = {status: 0 for status in STATUS_LABELS}

    for result in all_results:
        status_counter[result["status"]] += 1

        print()
        print("-" * 100)

        print("Date    : " + result["date"].strftime("%d/%m/%Y %H:%M"))

        print(f"Boîte   : {result['mailbox']}")

        print(f"De      : {result['from']}")

        print(f"Sujet   : {result['subject']}")

        print(f"Statut  : {STATUS_LABELS[result['status']]} [{result['status']}]")

        print(f"Score   : {result['score']}")

        if result["message_id"]:
            print(f"ID      : {result['message_id']}")

        print("Raisons : " + ", ".join(result["reasons"]))

    print()
    print("=" * 100)
    print("📊 RÉSUMÉ")
    print("=" * 100)

    print(f"Total : {len(all_results)}")

    for status, label in STATUS_LABELS.items():
        count = status_counter[status]

        if count:
            print(f"{label:<25} : {count}")

    print("=" * 100)

    print_review_section(all_results)
    print_recent_results(all_results, hours=24)


if __name__ == "__main__":
    main()
