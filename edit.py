from app.database import (
    clear_manual_override,
    get_applications,
    create_manual_application,
    merge_applications,
    set_manual_status,
)


STATUS_CHOICES = {
    "1": ("SENT", "Envoyée"),
    "2": ("RECEIVED", "Reçue"),
    "3": ("INTERVIEW", "Entretien"),
    "4": ("REJECTED", "Refus"),
    "5": ("TEST", "Test technique"),
    "6": ("OFFER", "Offre"),
    "7": ("OTHER", "À analyser"),
}

def merge_application_menu() -> None:
    print_applications()

    print()
    print("=" * 50)
    print("FUSION DE CANDIDATURES")
    print("=" * 50)

    source_id = input(
        "ID du doublon à supprimer : "
    ).strip()

    target_id = input(
        "ID de la candidature à conserver : "
    ).strip()

    if (
        not source_id.isdigit()
        or not target_id.isdigit()
    ):
        print("❌ IDs invalides.")
        return

    source_application_id = int(source_id)
    target_application_id = int(target_id)

    if source_application_id == target_application_id:
        print(
            "❌ Les deux IDs sont identiques."
        )
        return

    print()
    confirmation = input(
        f"Fusionner {source_application_id} "
        f"dans {target_application_id} ? [o/N] : "
    ).strip().lower()

    if confirmation not in (
        "o",
        "oui",
        "y",
        "yes",
    ):
        print("Fusion annulée.")
        return

    try:
        merge_applications(
            source_application_id,
            target_application_id,
        )

    except ValueError as error:
        print(f"❌ {error}")
        return

    print()
    print(
        f"✅ Candidature {source_application_id} "
        f"fusionnée dans {target_application_id}."
    )

def create_application_manually() -> None:
    print()
    print("=" * 50)
    print("NOUVELLE CANDIDATURE")
    print("=" * 50)

    company = input(
        "Entreprise : "
    ).strip()

    if not company:
        print("❌ L'entreprise est obligatoire.")
        return

    job_title = input(
        "Poste : "
    ).strip()

    source = input(
        "Source [Centre de formation] : "
    ).strip()

    if not source:
        source = "Centre de formation"

    status = ask_status()

    print()
    note = input(
        "Note facultative : "
    ).strip()

    application_id = create_manual_application(
        company=company,
        job_title=job_title,
        source=source,
        status=status,
        note=note,
    )

    print()
    print(
        f"✅ Candidature créée avec l'ID {application_id}."
    )

def print_applications() -> None:
    applications = get_applications()

    print()
    print("=" * 100)
    print(
        f"{'ID':<5}"
        f"{'ENTREPRISE':<32}"
        f"{'POSTE':<45}"
        f"{'STATUT':<15}"
    )
    print("=" * 100)

    for app in applications:
        effective_status = (
            app["manual_status"]
            if app["manual_override"]
            else app["current_status"]
        )

        company = app["company"] or "-"
        job_title = app["job_title"] or "-"

        if len(company) > 30:
            company = company[:27] + "..."

        if len(job_title) > 43:
            job_title = job_title[:40] + "..."

        print(
            f"{app['id']:<5}"
            f"{company:<32}"
            f"{job_title:<45}"
            f"{effective_status:<15}"
        )

    print("=" * 100)


def ask_application_id() -> int:
    while True:
        value = input(
            "\nID de la candidature : "
        ).strip()

        if value.isdigit():
            return int(value)

        print("ID invalide.")


def ask_status() -> str:
    print()
    print("Nouveau statut :")

    for key, (_, label) in STATUS_CHOICES.items():
        print(f"  {key}. {label}")

    while True:
        choice = input(
            "\nChoix : "
        ).strip()

        if choice in STATUS_CHOICES:
            return STATUS_CHOICES[choice][0]

        print("Choix invalide.")


def edit_application() -> None:
    print_applications()

    application_id = ask_application_id()
    status = ask_status()

    print()
    note = input(
        "Note facultative : "
    ).strip()

    set_manual_status(
        application_id=application_id,
        status=status,
        note=note,
    )

    print()
    print("✅ Modification enregistrée.")


def clear_override() -> None:
    print_applications()

    application_id = ask_application_id()

    clear_manual_override(
        application_id
    )

    print()
    print("✅ Modification manuelle supprimée.")
    print("Le statut automatique est de nouveau utilisé.")


def main() -> None:
    while True:
        print()
        print("=" * 50)
        print("TABLEAU DE SUIVI - MODIFICATION")
        print("=" * 50)
        print("1. Modifier une candidature")
        print("2. Supprimer un override manuel")
        print("3. Afficher les candidatures")
        print("4. Créer une candidature")
        print("5. Fusionner deux candidatures")
        print("0. Quitter")

        choice = input(
            "\nChoix : "
        ).strip()

        if choice == "1":
            edit_application()

        elif choice == "2":
            clear_override()

        elif choice == "3":
            print_applications()

        elif choice == "4":
            create_application_manually()

        elif choice == "5":
            merge_application_menu()

        elif choice == "0":
            print("À bientôt 👋")
            break

        else:
            print("Choix invalide.")

if __name__ == "__main__":
    main()