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
    "SENT",
    "RECEIVED",
    "INTERVIEW",
    "REJECTED",
    "EXPIRED",
    "OTHER",
]

EDITABLE_STATUS_LABELS = {
    "SENT": "Envoyée",
    "RECEIVED": "Reçue",
    "INTERVIEW": "Entretien",
    "REJECTED": "Refus",
    "EXPIRED": "Sans réponse",
    "OTHER": "À analyser",
}

def get_status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)
