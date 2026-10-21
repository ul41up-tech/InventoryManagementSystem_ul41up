"""應用工廠（app factory）。"""

from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, send_from_directory

from .config import Config
from .extensions import cors, db, migrate

# 前端打包產物（frontend/dist）；存在時由 Flask 一併託管，形成單一服務的部署方式
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


def create_app(config_object: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    # Flask 3.x：中文回應不轉成 \uXXXX
    app.json.ensure_ascii = False

    if not app.config.get("TESTING"):
        config_object.validate()

    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        supports_credentials=True,
    )

    from .api.audit import audit_bp
    from .api.masterdata import masterdata_bp
    from .api.purchase import purchase_bp
    from .api.receiving import receiving_bp
    from .api.stock import stock_bp
    from .api.users import users_bp
    from .auth import auth_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(masterdata_bp)
    app.register_blueprint(stock_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(purchase_bp)
    app.register_blueprint(receiving_bp)

    from .seed import register_seed_command

    register_seed_command(app)

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True, "service": "ailearn-inventory"})

    @app.teardown_appcontext
    def remove_session(exception=None):
        """請求結束後清除 session，避免交易狀態殘留到下一個請求。"""
        db.session.remove()

    @app.errorhandler(404)
    def not_found(_err):
        return jsonify({"error": "找不到資源"}), 404

    @app.errorhandler(500)
    def server_error(err):  # pragma: no cover
        db.session.rollback()
        app.logger.exception("未處理的伺服器錯誤: %s", err)
        return jsonify({"error": "伺服器錯誤"}), 500

    # 讓 `flask db` 等命令可以直接使用模型
    from . import models  # noqa: F401

    _register_frontend(app)
    return app


def _register_frontend(app: Flask) -> None:
    """若已有前端打包產物，由 Flask 託管（SPA：未知路徑一律回 index.html）。"""
    if not FRONTEND_DIST.exists() or not (FRONTEND_DIST / "index.html").exists():
        app.logger.info("找不到 frontend/dist，略過前端託管（開發時請另開 Vite）")
        return

    @app.get("/")
    def spa_index():
        return send_from_directory(FRONTEND_DIST, "index.html")

    @app.get("/<path:path>")
    def spa_fallback(path: str):
        if path.startswith("api/"):
            return jsonify({"error": "找不到資源"}), 404
        target = FRONTEND_DIST / path
        if target.is_file():
            return send_from_directory(FRONTEND_DIST, path)
        return send_from_directory(FRONTEND_DIST, "index.html")
