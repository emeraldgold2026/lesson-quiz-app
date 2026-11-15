from dataclasses import dataclass
from typing import Protocol

from app.schemas import FreeTextVerdict, GeneratedBatch


@dataclass(frozen=True)
class ChunkRecord:
    page_order: int
    chunk_index: int
    text: str


class AIClient(Protocol):
    def extract_page_text(self, image_bytes: bytes, mime_type: str) -> str: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...
    def generate_questions(self, section_text: str, n_mcq: int, n_free_text: int,
                           avoid: list[str] | None = None) -> GeneratedBatch: ...
    def grade_free_text(self, question: str, student_answer: str, reference_answer: str,
                        grounding: list[str]) -> FreeTextVerdict: ...


class VectorStore(Protocol):
    def upsert_chunks(self, lesson_id: int, chunks: list[ChunkRecord],
                      vectors: list[list[float]]) -> None: ...
    def search(self, lesson_id: int, vector: list[float], k: int) -> list[str]: ...
    def delete_lesson(self, lesson_id: int) -> None: ...
