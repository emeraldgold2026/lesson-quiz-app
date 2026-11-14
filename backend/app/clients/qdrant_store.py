import uuid

from qdrant_client import QdrantClient, models

from app.clients.protocols import ChunkRecord


class QdrantStore:
    def __init__(self, url: str = "", api_key: str = "", client: QdrantClient | None = None,
                 collection: str = "lesson_chunks", vector_size: int = 1536):
        self._client = client if client is not None else QdrantClient(url=url, api_key=api_key)
        self._collection = collection
        self._vector_size = vector_size

    def ensure_collection(self) -> None:
        if self._client.collection_exists(self._collection):
            return
        self._client.create_collection(
            self._collection,
            vectors_config=models.VectorParams(size=self._vector_size, distance=models.Distance.COSINE),
        )
        self._client.create_payload_index(
            self._collection, field_name="lesson_id", field_schema=models.PayloadSchemaType.KEYWORD
        )

    @staticmethod
    def _lesson_filter(lesson_id: int) -> models.Filter:
        return models.Filter(must=[
            models.FieldCondition(key="lesson_id", match=models.MatchValue(value=str(lesson_id)))
        ])

    def upsert_chunks(self, lesson_id: int, chunks: list[ChunkRecord],
                      vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError(f"{len(chunks)} chunks but {len(vectors)} vectors")
        self.ensure_collection()
        points = [
            models.PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{lesson_id}:{c.chunk_index}")),
                vector=v,
                payload={"lesson_id": str(lesson_id), "page_order": c.page_order,
                         "chunk_index": c.chunk_index, "text": c.text},
            )
            for c, v in zip(chunks, vectors)
        ]
        self._client.upsert(self._collection, points=points)

    def search(self, lesson_id: int, vector: list[float], k: int) -> list[str]:
        self.ensure_collection()
        resp = self._client.query_points(
            self._collection, query=vector, query_filter=self._lesson_filter(lesson_id),
            limit=k, with_payload=True,
        )
        return [p.payload["text"] for p in resp.points]

    def delete_lesson(self, lesson_id: int) -> None:
        self.ensure_collection()
        self._client.delete(
            self._collection,
            points_selector=models.FilterSelector(filter=self._lesson_filter(lesson_id)),
        )
