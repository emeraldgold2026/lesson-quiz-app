import pytest

from app.models import Question
from app.schemas import FreeTextVerdict
from app.services.grading import grade_free_text, grade_mcq, points
from tests.fakes import FakeAI, FakeStore


@pytest.mark.parametrize("correct,selected,expected", [
    ({1}, {1}, "correct"), ({1}, {2}, "incorrect"),
    ({1, 2}, {1}, "incorrect"), ({1, 2}, {1, 2, 3}, "incorrect"),
    ({1, 2}, {2, 1}, "correct"), ({1}, set(), "incorrect"),
])
def test_grade_mcq(correct, selected, expected):
    assert grade_mcq(correct, selected) == expected


def test_points():
    assert (points("correct"), points("partially_correct"), points("incorrect")) == (1.0, 0.5, 0.0)


def test_free_text_uses_reference_and_grounding(fake_store):
    fake_store.data[7] = ["chunk A", "chunk B"]
    ai = FakeAI(verdicts={"mine": FreeTextVerdict(verdict="partially_correct", feedback="half")})
    q = Question(id=1, lesson_id=7, type="free_text", question_text="Why?",
                 explanation="e", reference_answer="because")
    v = grade_free_text(q, "mine", ai, fake_store)
    assert v.verdict == "partially_correct"
    call = ai.grade_calls[0]
    assert call["reference_answer"] == "because" and call["grounding"] == ["chunk A", "chunk B"]


def test_free_text_propagates_ai_failure(fake_store):
    q = Question(id=1, lesson_id=7, type="free_text", question_text="Why?", explanation="e", reference_answer="r")
    with pytest.raises(RuntimeError):
        grade_free_text(q, "x", FakeAI(fail_grading=True), fake_store)
