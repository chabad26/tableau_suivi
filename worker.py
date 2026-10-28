"""Worker persistant pour les tâches et la maintenance."""

import fcntl
import time

from app.accounts import init_users
from app.database import DATABASE_PATH, init_database
from app.jobs import init_jobs
from app.owned_jobs import recover_interrupted_user_jobs, run_next_user_job
from app.ownership import init_ownership


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
        recover_interrupted_user_jobs()

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
                        while True:
                            if not run_next_user_job():
                                time.sleep(1)

                    except KeyboardInterrupt:
                        print("Worker arrêté proprement.")

                if not run_next_user_job():
                    time.sleep(1)

        except KeyboardInterrupt:
            print(
                "Worker arrêté. "
                "Un travail interrompu sera "
                "signalé au prochain démarrage."
            )


if __name__ == "__main__":
    main()
