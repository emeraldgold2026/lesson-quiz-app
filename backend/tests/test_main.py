from fastapi.testclient import TestClient

from app.main import INTERRUPTED_MESSAGE, create_app
from app.models import Lesson


def test_health():
    assert TestClient(create_app()).get("/health").json() == {"status": "ok"}


def test_startup_fails_lessons_left_processing(session_factory):
    with session_factory() as s:
        s.add_all([Lesson(title="stuck", status="processing"),
                   Lesson(title="done", status="ready")])
        s.commit()

    with TestClient(create_app(session_factory=session_factory)) as c:
        # requests share the factory
        assert {l["title"]: l["status"] for l in c.get("/lessons").json()} == {
            "stuck": "failed", "done": "ready"}

    with session_factory() as s:
        got = {l.title: (l.status, l.error_message) for l in s.query(Lesson)}
    assert got == {"stuck": ("failed", INTERRUPTED_MESSAGE), "done": ("ready", None)}
    assert INTERRUPTED_MESSAGE == "Interrupted by a server restart; use Retry."
