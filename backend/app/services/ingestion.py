import logging
import mimetypes
import shutil
from pathlib import Path
from typing import Callable

from app.clients.protocols import AIClient, VectorStore
from app.models import Lesson
from app.schemas import GeneratedQuestion
from app.services.chunking import chunk_pages
from app.services.generation import store_questions

log = logging.getLogger(__name__)


def upload_path(upload_dir: str, lesson_id: int, page_order: int, ext: str) -> Path:
    return Path(upload_dir) / str(lesson_id) / f"{page_order}.{ext}"


def _find_image(upload_dir: str, lesson_id: int, page_order: int) -> Path:
    matches = sorted((Path(upload_dir) / str(lesson_id)).glob(f"{page_order}.*"))
    if not matches:
        raise FileNotFoundError(f"missing upload for lesson {lesson_id} page {page_order}")
    return matches[0]


def run_ingestion(lesson_id: int, *, session_factory, ai: AIClient, store: VectorStore,
                  upload_dir: str,
                  after_ingest: Callable[[list[str]], list[GeneratedQuestion]]) -> None:
    """Extract, embed and generate for a lesson, then mark it ready.

    No database transaction is held open across network/LLM calls: SQLite allows a
    single writer, so a long transaction would lock out every other request. Each
    write below is its own short transaction. ``after_ingest`` receives the page
    texts and returns the questions to store; it runs outside any transaction.
    """
    try:
        with session_factory() as session:
            page_orders = [p.page_order for p in session.get(Lesson, lesson_id).pages]

        store.delete_lesson(lesson_id)  # idempotent for retries
        texts: list[str] = []
        for order in page_orders:
            img = _find_image(upload_dir, lesson_id, order)
            mime = mimetypes.guess_type(img.name)[0] or "image/png"
            texts.append(ai.extract_page_text(img.read_bytes(), mime))

        with session_factory() as session:
            for page, text in zip(session.get(Lesson, lesson_id).pages, texts, strict=True):
                page.extracted_text = text
            session.commit()

        chunks = chunk_pages(list(zip(page_orders, texts)))
        if not chunks:
            raise ValueError("no text could be extracted from the uploaded pages")
        vectors = ai.embed([c.text for c in chunks])
        store.upsert_chunks(lesson_id, chunks, vectors)

        questions = after_ingest(texts)

        with session_factory() as session:
            lesson = session.get(Lesson, lesson_id)
            store_questions(session, lesson, questions)
            lesson.status, lesson.error_message = "ready", None
            session.commit()
        shutil.rmtree(Path(upload_dir) / str(lesson_id), ignore_errors=True)
    except Exception as e:  # recorded in DB; this runs as a background task
        log.exception("ingestion failed for lesson %s", lesson_id)
        # Fresh session: the failed one may be mid-transaction. Persist the original
        # failure first so a failing store cleanup cannot mask it.
        with session_factory() as session:
            lesson = session.get(Lesson, lesson_id)
            lesson.status = "failed"
            lesson.error_message = f"{type(e).__name__}: {e}"
            session.commit()
        store.delete_lesson(lesson_id)
