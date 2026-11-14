import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import make_session_factory
from app.deps import get_ai, get_session_factory, get_settings, get_store
from app.main import create_app
from tests.fakes import FakeAI, FakeStore


@pytest.fixture
def session_factory():
    return make_session_factory("sqlite://")


@pytest.fixture
def fake_ai():
    return FakeAI()


@pytest.fixture
def fake_store():
    return FakeStore()


@pytest.fixture
def make_client():
    def _make(session_factory, ai, store, tmp_path) -> TestClient:
        app = create_app()
        app.dependency_overrides[get_session_factory] = lambda: session_factory
        app.dependency_overrides[get_ai] = lambda: ai
        app.dependency_overrides[get_store] = lambda: store
        app.dependency_overrides[get_settings] = lambda: Settings(upload_dir=str(tmp_path))
        return TestClient(app)
    return _make
