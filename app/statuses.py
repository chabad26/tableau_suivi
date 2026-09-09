STATUS_LABELS = {
    "PROPOSED": "Proposée",
    "SENT": "Envoyée",
    "RECEIVED": "Reçue",
    "INTERVIEW": "Entretien",
    "TEST": "Test technique",
    "OFFER": "Offre",
    "REJECTED": "Refus",
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
    "OTHER",
]


def get_status_label(
    status: str,
) -> str:
    return STATUS_LABELS.get(
        status,
        status,
    )