import pytest

from app.db import make_session_factory
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
