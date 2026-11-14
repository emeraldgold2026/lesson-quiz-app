import pytest
from qdrant_client import QdrantClient

from app.clients.protocols import ChunkRecord
from app.clients.qdrant_store import QdrantStore

# The in-memory engine warns that payload indexes have no effect; real servers honour them.
pytestmark = pytest.mark.filterwarnings("ignore:Payload indexes have no effect:UserWarning")


@pytest.fixture
def store():
    return QdrantStore(url="", api_key="", client=QdrantClient(":memory:"), vector_size=2)


def _seed(store):
    store.upsert_chunks(1, [ChunkRecord(1, 0, "l1-x"), ChunkRecord(1, 1, "l1-y")],
                        [[1.0, 0.0], [0.0, 1.0]])
    store.upsert_chunks(2, [ChunkRecord(1, 0, "l2-x")], [[1.0, 0.0]])


def test_search_is_scoped_to_lesson_and_ordered(store):
    _seed(store)
    assert store.search(1, [0.9, 0.1], k=5) == ["l1-x", "l1-y"]
    assert store.search(2, [0.0, 1.0], k=5) == ["l2-x"]


def test_search_respects_k(store):
    _seed(store)
    assert store.search(1, [0.0, 1.0], k=1) == ["l1-y"]


def test_delete_lesson_removes_only_that_lesson(store):
    _seed(store)
    store.delete_lesson(1)
    assert store.search(1, [1.0, 0.0], k=5) == []
    assert store.search(2, [1.0, 0.0], k=5) == ["l2-x"]


def test_upsert_is_idempotent_and_ensure_collection_repeatable(store):
    _seed(store)
    store.ensure_collection()
    store.upsert_chunks(1, [ChunkRecord(1, 0, "l1-x-new")], [[1.0, 0.0]])
    assert store.search(1, [1.0, 0.0], k=5)[0] == "l1-x-new"
    assert len(store.search(1, [1.0, 0.0], k=5)) == 2


def test_mismatched_lengths_raise(store):
    with pytest.raises(ValueError):
        store.upsert_chunks(1, [ChunkRecord(1, 0, "a")], [])


def test_empty_chunks_raise_clear_error(store):
    with pytest.raises(ValueError, match="requires at least one chunk"):
        store.upsert_chunks(1, [], [])
