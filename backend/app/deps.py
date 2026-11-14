from functools import lru_cache
from typing import Iterator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.clients.protocols import AIClient, VectorStore
from app.config import Settings
from app.db import make_session_factory


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_session_factory():
    return make_session_factory(get_settings().database_url)


def get_session(sf=Depends(get_session_factory)) -> Iterator[Session]:
    with sf() as session:
        yield session


@lru_cache
def get_ai() -> AIClient:
    from app.clients.openai_client import OpenAIClient
    return OpenAIClient(api_key=get_settings().openai_api_key)


@lru_cache
def get_store() -> VectorStore:
    from app.clients.qdrant_store import QdrantStore
    s = get_settings()
    return QdrantStore(url=s.qdrant_url, api_key=s.qdrant_api_key)
