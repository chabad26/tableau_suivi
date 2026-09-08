from pathlib import Path
import mailbox
import re
from datetime import datetime, timezone, timedelta
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

from dataclasses import dataclass
from email.message import Message
from typing import TypedDict

PROFILE = Path(
    "/home/oliv/snap/thunderbird/common/.thunderbird/jzmiasv2.default"
)

MAILBOXES: dict[str, Path] = {
    "Gmail": PROFILE / "ImapMail/imap.gmail.com/INBOX",
    "SFR": PROFILE / "ImapMail/imap.sfr.fr/INBOX",
    "Outlook": PROFILE / "ImapMail/outlook.office365.com/INBOX",
    "OVH": PROFILE / "ImapMail/ssl0.ovh.net/INBOX",
}

START_DATE = datetime(
    2026,
    8,
    1,
    0,
    0,
    0,
    tzinfo=timezone.utc
)


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


BLACKLIST_SENDERS = [
    "locservice",
    "locservice.fr",
]


STATUS_LABELS = {
    "SENT": "Candidature envoyée",
    "RECEIVED": "Candidature reçue",
    "INTERVIEW": "Entretien",
    "REJECTED": "Refus",
    "TEST": "Test technique",
    "OFFER": "Offre",
    "OTHER": "À analyser",
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


def decode_text(value: str | None) -> str:
    if not value:
        return ""

    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return str(value)


def normalize(text: str | None) -> str:
    text = decode_text(text).lower()
    text = text.replace("’", "'")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def get_body(message: Message) -> str:
    parts: list[str] = []

    if message.is_multipart():

        for part in message.walk():

            content_type: str = part.get_content_type()

            disposition = str(
                part.get("Content-Disposition", "")
            ).lower()

            if "attachment" in disposition:
                continue

            if content_type != "text/plain":
                continue

            try:
                payload = part.get_payload(decode=True)

                if not isinstance(payload, bytes):
                    continue

                charset: str = (
                    part.get_content_charset()
                    or "utf-8"
                )

                parts.append(
                    payload.decode(
                        charset,
                        errors="replace"
                    )
                )

            except Exception:
                continue

        return "\n".join(parts)

    try:
        payload = message.get_payload(decode=True)

        if not isinstance(payload, bytes):
            return ""

        charset: str = (
            message.get_content_charset()
            or "utf-8"
        )

        return payload.decode(
            charset,
            errors="replace"
        )

    except Exception:
        return ""

def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        date = parsedate_to_datetime(value)

        if date.tzinfo is None:
            date = date.replace(
                tzinfo=timezone.utc
            )

        return date

    except Exception:
        return None


def is_blacklisted_sender(sender: str) -> bool:
    sender = normalize(sender)

    return any(
        blocked in sender
        for blocked in BLACKLIST_SENDERS
    )


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
    ]

    if contains_any(subject_text, offer_subject):
        return "OFFER"

    # ------------------------------------------------------------------
    # CANDIDATURE ENVOYÉE
    # ------------------------------------------------------------------

    sent_subject = [
        "votre candidature a été envoyée",
        "votre candidature a ete envoyee",
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
    ]

    if contains_any(subject_text, received_subject):
        return "RECEIVED"

    # Cas du genre :
    # "Votre candidature : Développeur Full Stack..."
    if subject_text.startswith("votre candidature"):
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
    ]

    if contains_any(body_text, interview_body):
        return "INTERVIEW"

    test_body = [
        "nous vous invitons à réaliser un test technique",
        "nous vous invitons a realiser un test technique",
        "nous vous proposons un test technique",
        "nous vous proposons un exercice technique",
    ]

    if contains_any(body_text, test_body):
        return "TEST"

    offer_body = [
        "nous souhaitons vous proposer un contrat",
        "nous souhaitons vous faire une proposition d'embauche",
        "nous sommes heureux de vous proposer le poste",
        "nous avons le plaisir de vous proposer le poste",
    ]

    if contains_any(body_text, offer_body):
        return "OFFER"

    return "OTHER"

def score_message(message: Message) -> tuple[int, list[str], str]:

    subject = normalize(
        message.get("Subject")
    )

    sender = normalize(
        message.get("From")
    )

    score = 0
    reasons: list[str] = []
    
    # Sujet positif
    for keyword in POSITIVE_KEYWORDS:
        if keyword in subject:
            score += 5
            reasons.append(
                f"sujet:{keyword}"
            )

    # Expéditeur orienté recrutement
    for keyword in RECRUITMENT_SENDERS:
        if keyword in sender:
            score += 1
            reasons.append(
                f"expéditeur:{keyword}"
            )

    # Bruit évident
    for keyword in NEGATIVE_KEYWORDS:
        if keyword in subject:
            score -= 6
            reasons.append(
                f"bruit:{keyword}"
            )

    #
    # On ne décode le corps que si le mail
    # est encore potentiellement intéressant.
    #
    body = ""

    if -2 < score < 5:

        body = normalize(
            get_body(message)
        )

        for keyword in POSITIVE_KEYWORDS:
            if keyword in body:
                score += 2
                reasons.append(
                    f"corps:{keyword}"
                )

        for keyword in NEGATIVE_KEYWORDS:
            if keyword in body:
                score -= 2
                reasons.append(
                    f"bruit-corps:{keyword}"
                )

    return score, reasons, body


def scan_mailbox(name: str, path: Path) -> list[EmailResult]:
    if not path.exists():
        print(
            f"⚠ Boîte introuvable : {path}"
        )

        return []

    print()
    print("=" * 100)
    print(f"📬 Analyse de la boîte {name}")
    print("=" * 100)

    results: list[EmailResult] = []

    mbox = mailbox.mbox(
        path,
        create=False
    )

    scanned = 0
    ignored_old = 0
    ignored_blacklist = 0
    ignored_noise = 0

    for message in mbox:

        scanned += 1

        #
        # DATE
        #
        date = parse_date(
            message.get("Date")
        )

        if date is None:
            continue

        date_utc = date.astimezone(
            timezone.utc
        )

        if date_utc < START_DATE:
            ignored_old += 1
            continue

        #
        # EXPÉDITEUR
        #
        sender = decode_text(
            message.get("From")
        )

        if is_blacklisted_sender(sender):
            ignored_blacklist += 1
            continue

        #
        # SCORE
        #
        score, reasons, body = score_message(
            message
        )

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

        subject = decode_text(
            message.get("Subject")
        )

        status = detect_status(
            subject,
            body
        )

        results.append({
            "mailbox": name,
            "date": date,
            "from": sender,
            "subject": subject,
            "message_id": decode_text(
                message.get("Message-ID")
            ),
            "score": score,
            "status": status,
            "reasons": reasons,
        })

    print(
        f"{scanned} mails parcourus"
    )

    print(
        f"{ignored_old} ignorés car antérieurs au 01/08/2026"
    )

    print(
        f"{ignored_blacklist} ignorés car leur expéditeur figure sur la liste noire"
    )

    print(
        f"{ignored_noise} ignorés comme bruit"
    )

    print(
        f"{len(results)} candidatures potentielles trouvées"
    )

    return results

def print_review_section(results: list[EmailResult]) -> None:
    print()
    print("=" * 100)
    print("🔎 À VÉRIFIER")
    print("=" * 100)

    review = [
        r for r in results
        if r["status"] in {"OFFER", "OTHER"}
    ]

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
        print(
            f"Statut  : "
            f"{STATUS_LABELS[result['status']]} "
            f"[{result['status']}]"
        )
        print(f"Score   : {result['score']}")


def print_recent_results(results: list[EmailResult], hours: int = 24) -> None:
    now = datetime.now(timezone.utc)
    limit = now - timedelta(hours=hours)

    recent = [
        r for r in results
        if r["date"].astimezone(timezone.utc) >= limit
    ]

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
        print(
            f"Statut  : "
            f"{STATUS_LABELS[result['status']]} "
            f"[{result['status']}]"
        )

def main() -> None:

    all_results: list[EmailResult] = []

    for name, path in MAILBOXES.items():

        results = scan_mailbox(
            name,
            path
        )

        all_results.extend(
            results
        )

    #
    # Du plus récent au plus ancien
    #
    all_results.sort(
        key=lambda x: (
            x["date"].timestamp()
            if x["date"]
            else 0
        ),
        reverse=True
    )

    print()
    print()
    print("#" * 100)
    print("🎯 CANDIDATURES DÉTECTÉES")
    print("#" * 100)

    status_counter = {
        status: 0
        for status in STATUS_LABELS
    }

    for result in all_results:

        status_counter[
            result["status"]
        ] += 1

        print()
        print("-" * 100)

        print(
            "Date    : "
            + result["date"].strftime(
                "%d/%m/%Y %H:%M"
            )
        )

        print(
            f"Boîte   : {result['mailbox']}"
        )

        print(
            f"De      : {result['from']}"
        )

        print(
            f"Sujet   : {result['subject']}"
        )

        print(
            f"Statut  : "
            f"{STATUS_LABELS[result['status']]}"
            f" [{result['status']}]"
        )

        print(
            f"Score   : {result['score']}"
        )

        if result["message_id"]:
            print(
                f"ID      : "
                f"{result['message_id']}"
            )

        print(
            "Raisons : "
            + ", ".join(
                result["reasons"]
            )
        )

    print()
    print("=" * 100)
    print("📊 RÉSUMÉ")
    print("=" * 100)

    print(
        f"Total : {len(all_results)}"
    )

    for status, label in STATUS_LABELS.items():

        count = status_counter[
            status
        ]

        if count:
            print(
                f"{label:<25} : {count}"
            )

    print("=" * 100)

    print_review_section(all_results)
    print_recent_results(all_results, hours=24)


if __name__ == "__main__":
    main()
