from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings
from app.routers import lessons


def create_app() -> FastAPI:
    settings = Settings()
    app = FastAPI(title="Lesson Quiz")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_methods=["*"], allow_headers=["*"])

    app.include_router(lessons.router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
