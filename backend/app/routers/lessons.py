import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.deps import get_ai, get_session, get_session_factory, get_settings, get_store
from app.models import Lesson, LessonPage
from app.schemas import LessonOut
from app.services.generation import generate_questions_for_lesson
from app.services.ingestion import run_ingestion, upload_path

router = APIRouter(prefix="/lessons", tags=["lessons"])
ALLOWED = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


def to_out(lesson: Lesson) -> LessonOut:
    return LessonOut(id=lesson.id, title=lesson.title, status=lesson.status,
                     error_message=lesson.error_message, page_count=lesson.page_count,
                     created_at=lesson.created_at, has_questions=bool(lesson.questions))


def _get_or_404(session: Session, lesson_id: int) -> Lesson:
    lesson = session.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, f"lesson {lesson_id} not found")
    return lesson


def _schedule(bg: BackgroundTasks, lesson_id, sf, ai, store, settings):
    bg.add_task(run_ingestion, lesson_id, session_factory=sf, ai=ai, store=store,
                upload_dir=settings.upload_dir,
                after_ingest=lambda s, l: generate_questions_for_lesson(s, l, ai))


@router.post("", status_code=202, response_model=LessonOut)
async def create_lesson(bg: BackgroundTasks, title: str = Form(...),
                        files: list[UploadFile] = File(default=[]),
                        session: Session = Depends(get_session), sf=Depends(get_session_factory),
                        ai=Depends(get_ai), store=Depends(get_store),
                        settings: Settings = Depends(get_settings)):
    if not title.strip():
        raise HTTPException(422, "title must not be blank")
    if not files:
        raise HTTPException(422, "at least one image is required")
    bad = [f.filename for f in files if f.content_type not in ALLOWED]
    if bad:
        raise HTTPException(422, f"unsupported file type for: {bad}; use PNG, JPEG or WebP")

    lesson = Lesson(title=title.strip(), status="processing", page_count=len(files))
    lesson.pages = [LessonPage(page_order=i) for i in range(len(files))]
    session.add(lesson)
    session.flush()  # assigns lesson.id; nothing is persisted until the uploads are on disk
    try:
        for i, f in enumerate(files):
            path = upload_path(settings.upload_dir, lesson.id, i, ALLOWED[f.content_type])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(await f.read())
    except BaseException:
        shutil.rmtree(Path(settings.upload_dir) / str(lesson.id), ignore_errors=True)
        session.rollback()
        raise
    session.commit()
    _schedule(bg, lesson.id, sf, ai, store, settings)
    return to_out(lesson)


@router.get("", response_model=list[LessonOut])
def list_lessons(session: Session = Depends(get_session)):
    rows = session.scalars(select(Lesson).order_by(Lesson.created_at.desc(), Lesson.id.desc()))
    return [to_out(l) for l in rows]


@router.get("/{lesson_id}", response_model=LessonOut)
def get_lesson(lesson_id: int, session: Session = Depends(get_session)):
    return to_out(_get_or_404(session, lesson_id))


@router.post("/{lesson_id}/retry", status_code=202, response_model=LessonOut)
def retry_lesson(lesson_id: int, bg: BackgroundTasks, session: Session = Depends(get_session),
                 sf=Depends(get_session_factory), ai=Depends(get_ai), store=Depends(get_store),
                 settings: Settings = Depends(get_settings)):
    lesson = _get_or_404(session, lesson_id)
    if lesson.status != "failed":
        raise HTTPException(409, f"lesson is {lesson.status}; only failed lessons can be retried")
    lesson.status, lesson.error_message = "processing", None
    session.commit()
    _schedule(bg, lesson.id, sf, ai, store, settings)
    return to_out(lesson)
