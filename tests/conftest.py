import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from app.config import Config  # noqa: E402
from app.services import health  # noqa: E402

OFFLINE = {"ok": False, "version": None, "error": "offline (teste)", "checked_at": ""}
ONLINE = {"ok": True, "version": "v4.6.2", "error": None, "checked_at": ""}


def _test_config(tmp_path):
    class TestConfig(Config):
        TESTING = True
        DB_PATH = tmp_path / "test.db"
        DATA_DIR = tmp_path
        CACHE_TTL = 0
        HEALTH_TTL = 0
        SECRET_KEY = "test"

    return TestConfig


@pytest.fixture(autouse=True)
def _reset_health_cache():
    health.invalidate()
    yield
    health.invalidate()


@pytest.fixture
def app(tmp_path, monkeypatch):
    application = create_app(_test_config(tmp_path))
    monkeypatch.setattr(health, "check", lambda force=False: dict(OFFLINE))
    yield application


@pytest.fixture
def real_app(tmp_path):
    """App sem o health check mockado (para testes de integração)."""
    return create_app(_test_config(tmp_path))


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def online(app, monkeypatch):
    """Faz o health check responder como se o qBittorrent estivesse no ar."""
    monkeypatch.setattr(health, "check", lambda force=False: dict(ONLINE))
    return app
