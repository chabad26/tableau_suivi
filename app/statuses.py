STATUS_LABELS = {
    "RECEIVED": "Reçue",
    "INTERVIEW": "Entretien",
    "REJECTED": "Refus",
    "ACCEPTED": "Acceptée",
    "EXPIRED": "Sans réponse",
    "OTHER": "À analyser",
}

STATUS_ORDER = list(STATUS_LABELS)


def get_status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)
