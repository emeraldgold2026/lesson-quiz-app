def ready(make_client, session_factory, fake_store, tmp_path, ai=None):
    from tests.fakes import FakeAI
    ai = ai or FakeAI(page_texts=["word " * 2000])
    c = make_client(session_factory, ai, fake_store, tmp_path)
    lid = c.post("/lessons", data={"title": "T"}, files=[("files", ("p.png", b"x", "image/png"))]).json()["id"]
    return c, ai, lid


def test_mcq_test_hides_answers(make_client, session_factory, fake_store, tmp_path):
    c, _, lid = ready(make_client, session_factory, fake_store, tmp_path)
    r = c.get(f"/lessons/{lid}/mcq-test")
    qs = r.json()
    assert qs and all(q["choices"] for q in qs)
    assert all("explanation" not in q and "reference_answer" not in q for q in qs)
    assert all("is_correct" not in ch for q in qs for ch in q["choices"])
    assert "is_correct" not in r.text and "because" not in r.text


def test_mcq_submit_grades_and_persists(make_client, session_factory, fake_store, tmp_path):
    from app.models import McqChoice
    c, _, lid = ready(make_client, session_factory, fake_store, tmp_path)
    qs = c.get(f"/lessons/{lid}/mcq-test").json()
    with session_factory() as s:
        correct = {cid for (cid,) in s.query(McqChoice.id).filter(McqChoice.is_correct)}
    answers = {q["id"]: [ch["id"] for ch in q["choices"] if ch["id"] in correct] for q in qs}
    answers[qs[0]["id"]] = [qs[0]["choices"][1]["id"]]  # one wrong
    r = c.post(f"/lessons/{lid}/mcq-test/submit", json={"answers": answers}).json()
    assert r["total_questions"] == len(qs) and r["score"] == len(qs) - 1
    assert r["results"][0]["verdict"] == "incorrect" and r["results"][0]["correct_answer_text"] == "right"
    assert r["results"][0]["feedback_text"] == "because"
    assert r["results"][0]["student_response_text"] == "wrong"
    assert r["results"][1]["student_response_text"] == "right"
    replay = c.get(f"/attempts/{r['id']}").json()
    assert [x["student_response_text"] for x in replay["results"]] == \
        [x["student_response_text"] for x in r["results"]]
    assert c.get(f"/attempts/{r['id']}").json()["score"] == r["score"]
    assert len(c.get(f"/lessons/{lid}/attempts").json()) == 1


def test_mcq_submit_rejects_missing_or_foreign_choices(make_client, session_factory, fake_store, tmp_path):
    c, _, lid = ready(make_client, session_factory, fake_store, tmp_path)
    qs = c.get(f"/lessons/{lid}/mcq-test").json()
    assert c.post(f"/lessons/{lid}/mcq-test/submit", json={"answers": {}}).status_code == 422
    bad = {q["id"]: [999999] for q in qs}
    assert c.post(f"/lessons/{lid}/mcq-test/submit", json={"answers": bad}).status_code == 422
    assert c.get(f"/lessons/{lid}/attempts").json() == []


def test_free_text_flow_scores_partial_as_half(make_client, session_factory, fake_store, tmp_path):
    from app.schemas import FreeTextVerdict
    from tests.fakes import FakeAI
    ai = FakeAI(page_texts=["word " * 2000], verdicts={
        "a1": FreeTextVerdict(verdict="correct", feedback="good"),
        "a2": FreeTextVerdict(verdict="partially_correct", feedback="half")})
    c, _, lid = ready(make_client, session_factory, fake_store, tmp_path, ai)
    r = c.get(f"/lessons/{lid}/free-text-test")
    qs = r.json()
    assert qs and all("reference_answer" not in q for q in qs)
    assert "ref 0" not in r.text
    answers = {q["id"]: "zzz" for q in qs}
    answers[qs[0]["id"]], answers[qs[1]["id"]] = "a1", "a2"
    r = c.post(f"/lessons/{lid}/free-text-test/submit", json={"answers": answers}).json()
    assert r["score"] == 1.5
    assert r["results"][0]["correct_answer_text"] == "ref 0"
    assert [x["student_response_text"] for x in r["results"][:3]] == ["a1", "a2", "zzz"]


def test_free_text_grading_failure_persists_nothing(make_client, session_factory, fake_store, tmp_path):
    from tests.fakes import FakeAI
    ai = FakeAI(page_texts=["word " * 2000])
    c, _, lid = ready(make_client, session_factory, fake_store, tmp_path, ai)
    qs = c.get(f"/lessons/{lid}/free-text-test").json()
    ai.fail_grading = True
    r = c.post(f"/lessons/{lid}/free-text-test/submit", json={"answers": {q["id"]: "x" for q in qs}})
    assert r.status_code == 502
    assert c.get(f"/lessons/{lid}/attempts").json() == []


def test_mcq_result_text_lists_selected_choices_or_placeholder(make_client, session_factory, fake_store, tmp_path):
    c, _, lid = ready(make_client, session_factory, fake_store, tmp_path)
    qs = c.get(f"/lessons/{lid}/mcq-test").json()
    answers = {q["id"]: [] for q in qs}
    answers[qs[0]["id"]] = [ch["id"] for ch in qs[0]["choices"]]
    r = c.post(f"/lessons/{lid}/mcq-test/submit", json={"answers": answers}).json()
    assert r["results"][0]["student_response_text"] == "right; wrong"
    assert r["results"][1]["student_response_text"] == "(no selection)"


def test_timestamps_keep_utc_offset_after_db_roundtrip(make_client, session_factory, fake_store, tmp_path):
    from datetime import datetime, timedelta
    c, _, lid = ready(make_client, session_factory, fake_store, tmp_path)
    qs = c.get(f"/lessons/{lid}/mcq-test").json()
    aid = c.post(f"/lessons/{lid}/mcq-test/submit",
                 json={"answers": {q["id"]: [] for q in qs}}).json()["id"]
    attempt = c.get(f"/attempts/{aid}").json()
    stamps = [c.get("/lessons").json()[0]["created_at"], c.get(f"/lessons/{lid}").json()["created_at"],
              attempt["started_at"], attempt["submitted_at"],
              c.get(f"/lessons/{lid}/attempts").json()[0]["submitted_at"]]
    for s in stamps:
        assert datetime.fromisoformat(s).utcoffset() == timedelta(0), s


def test_tests_unavailable_until_ready(make_client, session_factory, fake_store, tmp_path):
    from tests.fakes import FakeAI
    c = make_client(session_factory, FakeAI(fail_on_page=0), fake_store, tmp_path)
    lid = c.post("/lessons", data={"title": "T"}, files=[("files", ("p.png", b"x", "image/png"))]).json()["id"]
    assert c.get(f"/lessons/{lid}/mcq-test").status_code == 409
