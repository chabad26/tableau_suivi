from app.database import init_database
from app.web import create_app

app = create_app()

if __name__ == "__main__":
    init_database()
    app.run(host="127.0.0.1", port=5000, debug=True)
