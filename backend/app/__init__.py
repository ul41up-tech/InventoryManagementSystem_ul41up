"""應用工廠（app factory）。"""

from __future__ import annotations

from flask import Flask, jsonify

from .config import Config
from .extensions import cors, db, migrate


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
    from .api.stock import stock_bp
    from .auth import auth_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(masterdata_bp)
    app.register_blueprint(stock_bp)
    app.register_blueprint(audit_bp)

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

    return app
