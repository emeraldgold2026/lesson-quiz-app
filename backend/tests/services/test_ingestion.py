from app.models import Lesson, LessonPage
from app.services.ingestion import run_ingestion, upload_path
from tests.fakes import FakeAI


def _seed(session_factory, tmp_path, n_pages=2):
    with session_factory() as s:
        lesson = Lesson(title="L", status="processing", page_count=n_pages)
        for i in range(n_pages):
            lesson.pages.append(LessonPage(page_order=i))
        s.add(lesson)
        s.commit()
        lid = lesson.id
    for i in range(n_pages):
        p = upload_path(str(tmp_path), lid, i, "png")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"img")
    return lid


def test_success_extracts_chunks_marks_ready_and_deletes_uploads(session_factory, fake_store, tmp_path):
    lid = _seed(session_factory, tmp_path)
    ai = FakeAI(page_texts=["alpha text", "beta text"])
    called = []
    run_ingestion(lid, session_factory=session_factory, ai=ai, store=fake_store,
                  upload_dir=str(tmp_path), after_ingest=lambda s, l: called.append(l.id))
    with session_factory() as s:
        lesson = s.get(Lesson, lid)
        assert lesson.status == "ready" and lesson.error_message is None
        assert [p.extracted_text for p in lesson.pages] == ["alpha text", "beta text"]
    assert fake_store.data[lid]
    assert called == [lid]
    assert not (tmp_path / str(lid)).exists()


def test_failure_marks_failed_keeps_uploads_and_clears_vectors(session_factory, fake_store, tmp_path):
    lid = _seed(session_factory, tmp_path)
    ai = FakeAI(fail_on_page=1)
    run_ingestion(lid, session_factory=session_factory, ai=ai, store=fake_store,
                  upload_dir=str(tmp_path), after_ingest=lambda s, l: None)
    with session_factory() as s:
        lesson = s.get(Lesson, lid)
        assert lesson.status == "failed"
        assert "vision failed on page 1" in lesson.error_message
    assert (tmp_path / str(lid)).exists()
    assert lid not in fake_store.data


def test_after_ingest_failure_also_marks_failed(session_factory, fake_store, tmp_path):
    lid = _seed(session_factory, tmp_path, 1)

    def boom(s, l):
        raise ValueError("gen broke")

    run_ingestion(lid, session_factory=session_factory, ai=FakeAI(), store=fake_store,
                  upload_dir=str(tmp_path), after_ingest=boom)
    with session_factory() as s:
        assert s.get(Lesson, lid).status == "failed"
