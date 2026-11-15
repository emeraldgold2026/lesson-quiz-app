import pytest
from fastapi import HTTPException

from app import deps
from app.config import Settings


@pytest.mark.parametrize("getter, missing", [(deps.get_ai, "OPENAI_API_KEY"), (deps.get_store, "QDRANT_URL")])
def test_missing_config_fails_loudly(monkeypatch, getter, missing):
    monkeypatch.setattr(deps, "get_settings", lambda: Settings(openai_api_key="", qdrant_url=""))
    getter.cache_clear()
    with pytest.raises(HTTPException) as exc:
        getter()
    assert exc.value.status_code == 503
    assert missing in exc.value.detail
