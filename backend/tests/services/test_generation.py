import pytest

from app.models import Lesson, LessonPage
from app.schemas import GeneratedBatch, GeneratedChoice, GeneratedQuestion
from app.services.generation import (allocate, generate_questions_for_lesson,
                                     make_sections, question_targets)
from tests.fakes import FakeAI


def test_allocate_sums_to_total():
    assert sum(allocate(10, [1, 1, 1])) == 10
    # 7.5 / 2.5 tie on remainder: stable sort gives the extra unit to the earlier index
    assert allocate(10, [3, 1]) == [8, 2]
    assert sum(allocate(7, [0, 0])) == 7


def test_question_targets_clamped():
    assert question_targets(10) == (5, 5)
    assert question_targets(1750) == (10, 5)
    assert question_targets(1800) == (10, 5)
    assert question_targets(10**6) == (100, 100)


def test_make_sections_groups_sequentially():
    para = " ".join(["w"] * 500)
    sections = make_sections([para, para, para], target_words=900)
    assert len(sections) == 3


def _lesson(session, texts):
    lesson = Lesson(title="L", status="processing", page_count=len(texts))
    for i, t in enumerate(texts):
        lesson.pages.append(LessonPage(page_order=i, extracted_text=t))
    session.add(lesson); session.flush()
    return lesson


def test_generates_and_persists_questions(session_factory):
    ai = FakeAI()
    with session_factory() as s:
        lesson = _lesson(s, [" ".join(["word"] * 1800)])
        generate_questions_for_lesson(s, lesson, ai)
        s.commit()
        n_mcq, n_free = question_targets(1800)
        types = [q.type for q in lesson.questions]
        assert types.count("mcq_single") == n_mcq and types.count("free_text") == n_free
        assert sum(c[1] for c in ai.generate_calls) == n_mcq
        free = next(q for q in lesson.questions if q.type == "free_text")
        assert free.reference_answer


class BadAI(FakeAI):
    def __init__(self, q): super().__init__(); self.q = q
    def generate_questions(self, *a, **k): return GeneratedBatch(questions=[self.q])


@pytest.mark.parametrize("q", [
    GeneratedQuestion(type="mcq_single", question_text="q", explanation="e",
                      choices=[GeneratedChoice(text="a", is_correct=False), GeneratedChoice(text="b", is_correct=False)]),
    GeneratedQuestion(type="mcq_single", question_text="q", explanation="e",
                      choices=[GeneratedChoice(text="a", is_correct=True), GeneratedChoice(text="b", is_correct=True)]),
    GeneratedQuestion(type="free_text", question_text="q", explanation="e"),
])
def test_invalid_llm_output_raises(session_factory, q):
    with session_factory() as s:
        lesson = _lesson(s, ["some words here"])
        with pytest.raises(ValueError):
            generate_questions_for_lesson(s, lesson, BadAI(q))
