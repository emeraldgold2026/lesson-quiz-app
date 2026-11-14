import threading

import pytest

from app.db import make_session_factory
from tests.fakes import FakeAI

PNG = ("p.png", b"\x89PNG", "image/png")


def test_create_lesson_runs_ingestion_and_generation(make_client, session_factory, fake_store, tmp_path):
    ai = FakeAI(page_texts=["alpha " * 100, "beta " * 100])
    c = make_client(session_factory, ai, fake_store, tmp_path)
    r = c.post("/lessons", data={"title": "Ch1"}, files=[("files", PNG), ("files", PNG)])
    assert r.status_code == 202 and r.json()["status"] == "processing"
    got = c.get(f"/lessons/{r.json()['id']}").json()  # TestClient ran the background task already
    assert got["status"] == "ready" and got["page_count"] == 2 and got["has_questions"] is True


def test_create_lesson_validates_input(make_client, session_factory, fake_store, tmp_path):
    c = make_client(session_factory, FakeAI(), fake_store, tmp_path)
    assert c.post("/lessons", data={"title": "x"}, files=[("files", ("a.txt", b"x", "text/plain"))]).status_code == 422
    assert c.post("/lessons", data={"title": " "}, files=[("files", PNG)]).status_code == 422
    assert c.post("/lessons", data={"title": "x"}).status_code == 422


def test_failed_lesson_can_be_retried(make_client, session_factory, fake_store, tmp_path):
    ai = FakeAI(fail_on_page=0)
    c = make_client(session_factory, ai, fake_store, tmp_path)
    lid = c.post("/lessons", data={"title": "T"}, files=[("files", PNG)]).json()["id"]
    assert c.get(f"/lessons/{lid}").json()["status"] == "failed"
    ai.extract_calls = 0
    ai.fail_on_page = None
    assert c.post(f"/lessons/{lid}/retry").status_code == 202
    assert c.get(f"/lessons/{lid}").json()["status"] == "ready"
    assert c.post(f"/lessons/{lid}/retry").status_code == 409


def test_failed_upload_write_persists_nothing(make_client, session_factory, fake_store, tmp_path):
    (tmp_path / "blocked").write_text("not a directory")
    c = make_client(session_factory, FakeAI(), fake_store, tmp_path / "blocked" / "x")
    with pytest.raises(OSError):
        c.post("/lessons", data={"title": "T"}, files=[("files", PNG)])
    assert c.get("/lessons").json() == []
    assert [p.name for p in tmp_path.iterdir()] == ["blocked"]


def test_list_and_404(make_client, session_factory, fake_store, tmp_path):
    c = make_client(session_factory, FakeAI(), fake_store, tmp_path)
    assert c.get("/lessons").json() == []
    assert c.get("/lessons/999").status_code == 404


def test_retry_unknown_lesson_is_404(make_client, session_factory, fake_store, tmp_path):
    c = make_client(session_factory, FakeAI(), fake_store, tmp_path)
    assert c.post("/lessons/999/retry").status_code == 404


def test_retry_is_atomic_against_a_concurrent_retry(make_client, fake_store, tmp_path):
    """A competing retry that commits just before ours writes must make ours 409."""
    import sqlite3

    from sqlalchemy import event

    db = tmp_path / "app.db"
    sf = make_session_factory(f"sqlite:///{db}")
    ai = FakeAI(fail_on_page=0)
    c = make_client(sf, ai, fake_store, tmp_path / "uploads")
    lid = c.post("/lessons", data={"title": "T"}, files=[("files", PNG)]).json()["id"]
    assert c.get(f"/lessons/{lid}").json()["status"] == "failed"
    ai.extract_calls, ai.fail_on_page = 0, None

    competitor: dict = {}

    def race(conn, cursor, statement, params, context, executemany):
        if statement.startswith("UPDATE lessons") and "won" not in competitor:
            with sqlite3.connect(db) as other:  # the other request's retry, landing first
                competitor["won"] = other.execute(
                    "UPDATE lessons SET status='processing', error_message=NULL "
                    "WHERE id=? AND status='failed'", (lid,)).rowcount == 1

    event.listen(sf.kw["bind"], "before_cursor_execute", race)
    r = c.post(f"/lessons/{lid}/retry")
    event.remove(sf.kw["bind"], "before_cursor_execute", race)
    assert competitor["won"] is True
    assert r.status_code == 409  # only one of the two retries may schedule ingestion


class HoldingAI(FakeAI):
    """Blocks the first generate_questions call until released, to model a slow LLM."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.generating = threading.Event()
        self.release = threading.Event()
        self._held = False

    def generate_questions(self, section_text, n_mcq, n_free_text):
        if not self._held:
            self._held = True
            self.generating.set()
            assert self.release.wait(timeout=60), "test never released generation"
        return super().generate_questions(section_text, n_mcq, n_free_text)


def test_writes_succeed_while_another_lesson_is_generating(make_client, fake_store, tmp_path):
    sf = make_session_factory(f"sqlite:///{tmp_path / 'app.db'}")
    ai = HoldingAI()
    c = make_client(sf, ai, fake_store, tmp_path / "uploads")
    first: dict = {}

    def upload_first():
        first["resp"] = c.post("/lessons", data={"title": "A"}, files=[("files", PNG)])

    t = threading.Thread(target=upload_first)
    t.start()
    try:
        assert ai.generating.wait(timeout=10)
        # A second upload (insert + its own full ingestion) must not hit "database is locked".
        r2 = c.post("/lessons", data={"title": "B"}, files=[("files", PNG)])
        assert r2.status_code == 202
        assert c.get(f"/lessons/{r2.json()['id']}").json()["status"] == "ready"
    finally:
        ai.release.set()
        t.join(timeout=30)
    assert first["resp"].status_code == 202
    assert c.get(f"/lessons/{first['resp'].json()['id']}").json()["status"] == "ready"
