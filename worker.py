"""Worker persistant pour les tâches et la maintenance."""

import fcntl
import time

from app.accounts import init_users
from app.database import DATABASE_PATH, init_database
from app.jobs import init_jobs, recover_interrupted, run_next
from app.maintenance import expire_stale_applications
from app.ownership import init_ownership

MAINTENANCE_INTERVAL = 60


def main() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    lock_path = DATABASE_PATH.with_suffix(".worker.lock")

    with lock_path.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)

        except BlockingIOError:
            raise SystemExit("Un worker utilise déjà cette base.")

        init_database()
        init_jobs()
        init_users()
        init_ownership()

        # Le verrou garantit que l'ancien worker
        # ne traite plus de tâches.
        recover_interrupted()

        print(
            "Worker prêt. Les instructions OAuth apparaîtront dans ce terminal.",
            flush=True,
        )

        next_maintenance = time.monotonic()

        try:
            while True:
                now = time.monotonic()

                if now >= next_maintenance:
                    try:
                        expired = expire_stale_applications()

                        if expired:
                            print(
                                f"⏳ {expired} candidature(s) "
                                "passée(s) en Sans réponse.",
                                flush=True,
                            )

                    except Exception as error:
                        print(
                            f"❌ Maintenance : {type(error).__name__}: {error}",
                            flush=True,
                        )

                    finally:
                        next_maintenance = time.monotonic() + MAINTENANCE_INTERVAL

                if not run_next():
                    time.sleep(1)

        except KeyboardInterrupt:
            print(
                "Worker arrêté. "
                "Un travail interrompu sera "
                "signalé au prochain démarrage."
            )


if __name__ == "__main__":
    main()
