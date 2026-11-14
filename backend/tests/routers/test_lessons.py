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


def test_list_and_404(make_client, session_factory, fake_store, tmp_path):
    c = make_client(session_factory, FakeAI(), fake_store, tmp_path)
    assert c.get("/lessons").json() == []
    assert c.get("/lessons/999").status_code == 404
