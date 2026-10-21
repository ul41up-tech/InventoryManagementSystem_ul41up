"""WSGI 進入點。`flask --app wsgi db upgrade`、`flask --app wsgi seed` 皆以此為應用。"""

import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    # 開發模式由環境變數控制（正式環境不得開啟 Werkzeug 互動式除錯器）
    app.run(
        host="127.0.0.1",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "").lower() in {"1", "true", "yes", "on"},
    )
