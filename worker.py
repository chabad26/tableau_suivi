"""Lancer avec .venv/bin/python worker.py, dans un terminal dédié à OAuth."""

import fcntl
import time

from app.database import DATABASE_PATH, get_connection, init_database
from app.jobs import init_jobs, recover_interrupted, run_next


def main() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DATABASE_PATH.with_suffix(".worker.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("Un worker utilise déjà cette base.")
        init_database()
        init_jobs()
        # Le verrou garantit que le précédent worker ne travaille plus.
        recover_interrupted()
        print(
            "Worker prêt. Les instructions OAuth apparaîtront dans ce terminal.",
            flush=True,
        )
        try:
            while True:
                if not run_next():
                    time.sleep(1)
        except KeyboardInterrupt:
            print(
                "Worker arrêté. Un travail interrompu sera signalé au prochain démarrage."
            )


if __name__ == "__main__":
    main()
