import sys

from app.database import init_database
from app.importer import import_emails
from app.reclassifier import reclassify_emails


def main() -> None:
    init_database()

    if "--reclassify" in sys.argv:
        reclassify_emails()
        return

    result = import_emails()

    print()
    print("=" * 80)
    print("IMPORT TERMINÉ")
    print("=" * 80)
    print(f"Mails détectés       : {result.detected}")
    print(f"Mails ajoutés         : {result.added}")
    print(f"Candidatures traitées : {result.processed}")


if __name__ == "__main__":
    main()
