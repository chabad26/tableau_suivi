from app.database import get_applications
from app.statuses import STATUS_LABELS

def shorten(text: str | None, length: int) -> str:
    if not text:
        return "-"

    if len(text) <= length:
        return text

    return text[: length - 3] + "..."


def main() -> None:
    applications = get_applications()

    print()
    print("=" * 120)

    print(
        f"{'ID':<4}"
        f"{'ENTREPRISE':<28}"
        f"{'POSTE':<48}"
        f"{'SOURCE':<16}"
        f"{'STATUT':<15}"
    )

    print("=" * 120)

    for app in applications:

        company = shorten(
            app["company"],
            26
        )

        job_title = shorten(
            app["job_title"],
            46
        )

        source = shorten(
            app["source"],
            14
        )

        effective_status = (
            app["manual_status"]
            if app["manual_override"]
            else app["current_status"]
        )

        status = STATUS_LABELS.get(
            effective_status,
            effective_status
        )

        print(
            f"{app['id']:<4}"
            f"{company:<28}"
            f"{job_title:<48}"
            f"{source:<16}"
            f"{status:<15}"
        )

    print("=" * 120)

    print(
        f"{len(applications)} candidatures"
    )


if __name__ == "__main__":
    main()