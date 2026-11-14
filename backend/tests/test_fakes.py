from tests.fakes import FakeAI, FakeStore
from app.clients.protocols import ChunkRecord


def test_fake_ai_generates_requested_counts():
    batch = FakeAI().generate_questions("text", n_mcq=2, n_free_text=1)
    assert [q.type for q in batch.questions].count("free_text") == 1
    assert len(batch.questions) == 3
    assert all(any(c.is_correct for c in q.choices) for q in batch.questions if q.type != "free_text")


def test_fake_store_scoped_by_lesson():
    s = FakeStore()
    s.upsert_chunks(1, [ChunkRecord(0, 0, "a")], [[1.0]])
    s.upsert_chunks(2, [ChunkRecord(0, 0, "b")], [[1.0]])
    assert s.search(1, [1.0], 5) == ["a"]
