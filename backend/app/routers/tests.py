from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_ai, get_session, get_store
from app.models import Lesson
from app.schemas import (AttemptOut, ChoiceOut, FreeTextQuestionOut, FreeTextSubmit,
                         McqQuestionOut, McqSubmit, MoreQuestionsOut, MoreQuestionsRequest)
from app.services.generation import append_questions, plan_more_questions
from app.services.attempts import (GradingUnavailable, SubmissionError, attempt_out,
                                   questions_for, submit_free_text, submit_mcq)

router = APIRouter(prefix="/lessons", tags=["tests"])


def _ready_lesson(session: Session, lesson_id: int, kind: str) -> Lesson:
    lesson = session.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, f"lesson {lesson_id} not found")
    if lesson.status != "ready":
        raise HTTPException(409, f"lesson is {lesson.status}; tests are only available when ready")
    if not questions_for(lesson, kind):
        raise HTTPException(409, f"lesson has no {kind} questions")
    return lesson


@router.get("/{lesson_id}/mcq-test", response_model=list[McqQuestionOut])
def mcq_test(lesson_id: int, session: Session = Depends(get_session)):
    lesson = _ready_lesson(session, lesson_id, "mcq")
    return [McqQuestionOut(id=q.id, type=q.type, question_text=q.question_text,
                           choices=[ChoiceOut(id=c.id, text=c.choice_text) for c in q.choices])
            for q in questions_for(lesson, "mcq")]


@router.post("/{lesson_id}/mcq-test/submit", response_model=AttemptOut)
def mcq_submit(lesson_id: int, body: McqSubmit, session: Session = Depends(get_session)):
    lesson = _ready_lesson(session, lesson_id, "mcq")
    try:
        return attempt_out(submit_mcq(session, lesson, body.answers))
    except SubmissionError as e:
        raise HTTPException(422, str(e)) from e


@router.get("/{lesson_id}/free-text-test", response_model=list[FreeTextQuestionOut])
def free_text_test(lesson_id: int, session: Session = Depends(get_session)):
    lesson = _ready_lesson(session, lesson_id, "free_text")
    return [FreeTextQuestionOut(id=q.id, question_text=q.question_text)
            for q in questions_for(lesson, "free_text")]


@router.post("/{lesson_id}/free-text-test/submit", response_model=AttemptOut)
def free_text_submit(lesson_id: int, body: FreeTextSubmit, session: Session = Depends(get_session),
                     ai=Depends(get_ai), store=Depends(get_store)):
    lesson = _ready_lesson(session, lesson_id, "free_text")
    try:
        return attempt_out(submit_free_text(session, lesson, body.answers, ai, store))
    except SubmissionError as e:
        raise HTTPException(422, str(e)) from e
    except GradingUnavailable as e:
        raise HTTPException(502, str(e)) from e


@router.post("/{lesson_id}/questions", response_model=MoreQuestionsOut)
def generate_more_questions(lesson_id: int, body: MoreQuestionsRequest,
                            session: Session = Depends(get_session), ai=Depends(get_ai)):
    lesson = session.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, f"lesson {lesson_id} not found")
    if lesson.status != "ready":
        raise HTTPException(409, f"lesson is {lesson.status}; questions can only be added when ready")
    page_texts = [p.extracted_text or "" for p in lesson.pages]
    existing = [q.question_text for q in questions_for(lesson, body.kind)]
    session.commit()  # end the read transaction: none stays open during the LLM calls
    try:
        planned = plan_more_questions(page_texts, body.kind, body.count, existing, ai)
    except Exception as e:  # nothing is stored on failure; report the cause to the caller
        raise HTTPException(502, f"question generation failed: {type(e).__name__}: {e}") from e
    append_questions(session, lesson, planned)
    return MoreQuestionsOut(added=len(planned), total=len(questions_for(lesson, body.kind)))
