import logging
import mimetypes
import shutil
from pathlib import Path
from typing import Callable

from sqlalchemy.orm import Session

from app.clients.protocols import AIClient, VectorStore
from app.models import Lesson
from app.services.chunking import chunk_pages

log = logging.getLogger(__name__)


def upload_path(upload_dir: str, lesson_id: int, page_order: int, ext: str) -> Path:
    return Path(upload_dir) / str(lesson_id) / f"{page_order}.{ext}"


def _find_image(upload_dir: str, lesson_id: int, page_order: int) -> Path:
    matches = sorted((Path(upload_dir) / str(lesson_id)).glob(f"{page_order}.*"))
    if not matches:
        raise FileNotFoundError(f"missing upload for lesson {lesson_id} page {page_order}")
    return matches[0]


def run_ingestion(lesson_id: int, *, session_factory, ai: AIClient, store: VectorStore,
                  upload_dir: str, after_ingest: Callable[[Session, Lesson], None]) -> None:
    with session_factory() as session:
        lesson = session.get(Lesson, lesson_id)
        try:
            store.delete_lesson(lesson_id)  # idempotent for retries
            for page in lesson.pages:
                img = _find_image(upload_dir, lesson_id, page.page_order)
                mime = mimetypes.guess_type(img.name)[0] or "image/png"
                page.extracted_text = ai.extract_page_text(img.read_bytes(), mime)
            session.flush()

            chunks = chunk_pages([(p.page_order, p.extracted_text) for p in lesson.pages])
            if not chunks:
                raise ValueError("no text could be extracted from the uploaded pages")
            vectors = ai.embed([c.text for c in chunks])
            store.upsert_chunks(lesson_id, chunks, vectors)

            after_ingest(session, lesson)
            lesson.status, lesson.error_message = "ready", None
            session.commit()
            shutil.rmtree(Path(upload_dir) / str(lesson_id), ignore_errors=True)
        except Exception as e:  # recorded in DB; this runs as a background task
            log.exception("ingestion failed for lesson %s", lesson_id)
            session.rollback()
            # Persist the original failure first so a failing store cleanup cannot mask it.
            lesson = session.get(Lesson, lesson_id)
            lesson.status = "failed"
            lesson.error_message = f"{type(e).__name__}: {e}"
            session.commit()
            store.delete_lesson(lesson_id)
