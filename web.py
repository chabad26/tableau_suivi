from flask import Flask

from app.database import (
    init_database,
)
from app.jobs import (
    init_jobs,
)
from app.maintenance import (
    expire_stale_applications,
)
from app.settings import (
    SECRET_KEY,
)
from app.web import (
    register_blueprints,
)


app = Flask(__name__)

app.secret_key = SECRET_KEY

register_blueprints(app)


@app.before_request
def ensure_storage():
    init_database()
    init_jobs()
    expire_stale_applications()


if __name__ == "__main__":
    init_database()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
    )