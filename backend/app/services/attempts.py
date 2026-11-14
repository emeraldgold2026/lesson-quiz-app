from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.clients.protocols import AIClient, VectorStore
from app.models import Attempt, AttemptAnswer, Lesson, Question
from app.schemas import AnswerResultOut, AttemptOut, AttemptSummaryOut
from app.services.grading import grade_free_text, grade_mcq, points


class SubmissionError(ValueError):
    pass


class GradingUnavailable(RuntimeError):
    pass


def questions_for(lesson: Lesson, kind: str) -> list[Question]:
    wanted = {"mcq_single", "mcq_multi"} if kind == "mcq" else {"free_text"}
    return [q for q in lesson.questions if q.type in wanted]


def _check_keys(questions: list[Question], answers: dict) -> None:
    expected = {q.id for q in questions}
    if set(answers) != expected:
        raise SubmissionError(f"answers must cover exactly question ids {sorted(expected)}")


def submit_mcq(session: Session, lesson: Lesson, answers: dict[int, list[int]]) -> Attempt:
    questions = questions_for(lesson, "mcq")
    _check_keys(questions, answers)
    attempt = Attempt(lesson_id=lesson.id, test_type="mcq", total_questions=len(questions), score=0.0)
    for q in questions:
        valid = {c.id for c in q.choices}
        selected = set(answers[q.id])
        if not selected <= valid:
            raise SubmissionError(f"choices {sorted(selected - valid)} do not belong to question {q.id}")
        correct = {c.id for c in q.choices if c.is_correct}
        verdict = grade_mcq(correct, selected)
        attempt.score += points(verdict)
        attempt.answers.append(AttemptAnswer(
            question_id=q.id, student_response=sorted(selected), verdict=verdict,
            feedback_text=q.explanation,
            correct_answer_text="; ".join(c.choice_text for c in q.choices if c.is_correct)))
    attempt.submitted_at = datetime.now(timezone.utc)
    session.add(attempt)
    session.commit()
    return attempt


def submit_free_text(session: Session, lesson: Lesson, answers: dict[int, str],
                     ai: AIClient, store: VectorStore) -> Attempt:
    questions = questions_for(lesson, "free_text")
    _check_keys(questions, answers)
    attempt = Attempt(lesson_id=lesson.id, test_type="free_text", total_questions=len(questions), score=0.0)
    for q in questions:
        try:
            v = grade_free_text(q, answers[q.id], ai, store)
        except Exception as e:
            raise GradingUnavailable(f"grading failed for question {q.id}: {type(e).__name__}: {e}") from e
        attempt.score += points(v.verdict)
        attempt.answers.append(AttemptAnswer(
            question_id=q.id, student_response=answers[q.id], verdict=v.verdict,
            feedback_text=v.feedback, correct_answer_text=q.reference_answer))
    attempt.submitted_at = datetime.now(timezone.utc)
    session.add(attempt)
    session.commit()
    return attempt


def attempt_summary_out(attempt: Attempt) -> AttemptSummaryOut:
    return AttemptSummaryOut(
        id=attempt.id, lesson_id=attempt.lesson_id, test_type=attempt.test_type,
        started_at=attempt.started_at, submitted_at=attempt.submitted_at,
        score=attempt.score, total_questions=attempt.total_questions)


NO_SELECTION = "(no selection)"


def _response_text(a: AttemptAnswer) -> str:
    if a.question.type == "free_text":
        return a.student_response
    selected = set(a.student_response)
    texts = [c.choice_text for c in a.question.choices if c.id in selected]
    return "; ".join(texts) if texts else NO_SELECTION


def attempt_out(attempt: Attempt) -> AttemptOut:
    results = [AnswerResultOut(
        question_id=a.question_id, question_text=a.question.question_text,
        question_type=a.question.type, student_response=a.student_response,
        student_response_text=_response_text(a),
        verdict=a.verdict, feedback_text=a.feedback_text,
        correct_answer_text=a.correct_answer_text) for a in attempt.answers]
    return AttemptOut(**attempt_summary_out(attempt).model_dump(), results=results)
