"""Colonnes communes aux exports CSV et Excel."""

from app.presentation import PreparedApplication

EXPORT_HEADERS = (
    "Entreprise",
    "Poste",
    "Source",
    "Boîte mail",
    "Statut",
    "Note",
    "Première détection",
    "Dernière mise à jour",
    "Modification manuelle",
)

EXPORT_COLUMN_WIDTHS = {
    "A": 28,
    "B": 50,
    "C": 25,
    "D": 32,
    "E": 20,
    "F": 45,
    "G": 22,
    "H": 22,
    "I": 22,
}


def application_export_row(
    application: PreparedApplication,
) -> list[str]:
    return [
        application["company"],
        application["job_title"],
        application["source"],
        application["mailbox"],
        application["status_label"],
        application["note"],
        application["first_seen"],
        application["last_update"],
        (
            "Oui"
            if application["manual_override"]
            else "Non"
        ),
    ]
