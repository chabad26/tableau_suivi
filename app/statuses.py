STATUS_LABELS = {
    "PROPOSED": "Proposée",
    "SENT": "Envoyée",
    "RECEIVED": "Reçue",
    "INTERVIEW": "Entretien",
    "TEST": "Test technique",
    "OFFER": "Offre",
    "REJECTED": "Refus",
    "EXPIRED": "Sans réponse",
    "OTHER": "À analyser",
}


STATUS_ORDER = [
    "PROPOSED",
    "SENT",
    "RECEIVED",
    "INTERVIEW",
    "TEST",
    "OFFER",
    "REJECTED",
    "EXPIRED",
    "OTHER",
]


def get_status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)
