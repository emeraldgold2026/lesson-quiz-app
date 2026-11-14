import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import update
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.deps import get_session_factory
from app.models import Lesson
from app.routers import attempts, lessons, tests

log = logging.getLogger(__name__)

INTERRUPTED_MESSAGE = "Interrupted by a server restart; use Retry."


def fail_interrupted_lessons(session_factory: sessionmaker) -> int:
    """Ingestion runs in-process, so any lesson still `processing` at startup was orphaned."""
    with session_factory() as session:
        result = session.execute(
            update(Lesson).where(Lesson.status == "processing")
            .values(status="failed", error_message=INTERRUPTED_MESSAGE))
        session.commit()
    return result.rowcount


def create_app(session_factory: sessionmaker | None = None) -> FastAPI:
    settings = Settings()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        n = fail_interrupted_lessons(session_factory or get_session_factory())
        if n:
            log.warning("marked %d interrupted lesson(s) as failed", n)
        yield

    app = FastAPI(title="Lesson Quiz", lifespan=lifespan)
    if session_factory is not None:  # requests use the same database as the startup sweep
        app.dependency_overrides[get_session_factory] = lambda: session_factory
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_methods=["*"], allow_headers=["*"])

    app.include_router(lessons.router)
    app.include_router(tests.router)
    app.include_router(attempts.router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
