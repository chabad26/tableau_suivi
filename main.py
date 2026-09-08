from app.database import init_database


def main() -> None:
    init_database()

    print("Base SQLite initialisée.")


if __name__ == "__main__":
    main()