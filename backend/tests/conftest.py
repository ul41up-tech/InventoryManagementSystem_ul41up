"""pytest 共用 fixture：以 SQLite 記憶體資料庫測試 API（不需 PostgreSQL）。"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from app.config import TestConfig  # noqa: E402
from app.extensions import db as _db  # noqa: E402
from app.seed import _seed  # noqa: E402


@pytest.fixture()
def app():
    application = create_app(TestConfig)
    with application.app_context():
        _db.session.remove()
        _db.drop_all()
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def seeded(app):
    with app.app_context():
        _seed(app.config["SEED_PASSWORD"])
    return app


def login(client, username="warehouse", password="Test@1234"):
    return client.post("/api/auth/login", json={"username": username, "password": password})
