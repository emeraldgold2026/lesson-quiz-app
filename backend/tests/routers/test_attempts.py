def test_unknown_lesson_and_attempt_are_404(make_client, session_factory, fake_store, tmp_path):
    from tests.fakes import FakeAI
    c = make_client(session_factory, FakeAI(), fake_store, tmp_path)
    assert c.get("/lessons/999/mcq-test").status_code == 404
    assert c.get("/lessons/999/attempts").status_code == 404
    assert c.get("/attempts/999").status_code == 404
