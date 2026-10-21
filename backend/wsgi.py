"""WSGI 進入點。`flask --app wsgi db upgrade`、`flask --app wsgi seed` 皆以此為應用。"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
