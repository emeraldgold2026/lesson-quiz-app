from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_session
from app.models import Attempt, Lesson
from app.schemas import AttemptOut, AttemptSummaryOut
from app.services.attempts import attempt_out, attempt_summary_out

router = APIRouter(tags=["attempts"])


@router.get("/lessons/{lesson_id}/attempts", response_model=list[AttemptSummaryOut])
def list_attempts(lesson_id: int, session: Session = Depends(get_session)):
    if session.get(Lesson, lesson_id) is None:
        raise HTTPException(404, f"lesson {lesson_id} not found")
    rows = session.scalars(select(Attempt).where(Attempt.lesson_id == lesson_id)
                           .order_by(Attempt.started_at.desc(), Attempt.id.desc()))
    return [attempt_summary_out(a) for a in rows]


@router.get("/attempts/{attempt_id}", response_model=AttemptOut)
def get_attempt(attempt_id: int, session: Session = Depends(get_session)):
    attempt = session.get(Attempt, attempt_id)
    if attempt is None:
        raise HTTPException(404, f"attempt {attempt_id} not found")
    return attempt_out(attempt)
