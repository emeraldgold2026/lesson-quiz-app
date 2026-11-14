import pytest

from app.models import Lesson, LessonPage
from app.schemas import GeneratedBatch, GeneratedChoice, GeneratedQuestion
from app.services.generation import (allocate, make_sections, plan_questions,
                                     question_targets, store_questions)
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
    texts = [" ".join(["word"] * 1800)]
    planned = plan_questions(texts, ai)
    with session_factory() as s:
        lesson = _lesson(s, texts)
        store_questions(s, lesson, planned)
        s.commit()
        n_mcq, n_free = question_targets(1800)
        types = [q.type for q in lesson.questions]
        assert types.count("mcq_single") == n_mcq and types.count("free_text") == n_free
        assert sum(c[1] for c in ai.generate_calls) == n_mcq
        free = next(q for q in lesson.questions if q.type == "free_text")
        assert free.reference_answer
        mcq = next(q for q in lesson.questions if q.type == "mcq_single")
        assert [(c.choice_text, c.is_correct, c.order_index) for c in mcq.choices] == [
            ("right", True, 0), ("wrong", False, 1)]


def test_store_questions_replaces_existing(session_factory):
    planned = plan_questions(["some words here"], FakeAI())
    with session_factory() as s:
        lesson = _lesson(s, ["some words here"])
        store_questions(s, lesson, planned)
        store_questions(s, lesson, planned[:1])
        s.commit()
        assert len(s.get(Lesson, lesson.id).questions) == 1


class BadAI(FakeAI):
    def __init__(self, q): super().__init__(); self.q = q
    def generate_questions(self, *a, **k): return GeneratedBatch(questions=[self.q])


@pytest.mark.parametrize("q", [
    GeneratedQuestion(type="mcq_single", question_text="q", explanation="e",
                      choices=[GeneratedChoice(text="a", is_correct=False), GeneratedChoice(text="b", is_correct=False)]),
    GeneratedQuestion(type="mcq_single", question_text="q", explanation="e",
                      choices=[GeneratedChoice(text="a", is_correct=True), GeneratedChoice(text="b", is_correct=True)]),
    GeneratedQuestion(type="free_text", question_text="q", explanation="e", choices=[]),
])
def test_invalid_llm_output_raises(q):
    with pytest.raises(ValueError):
        plan_questions(["some words here"], BadAI(q))


def test_zero_generated_questions_raises():
    class EmptyAI(FakeAI):
        def generate_questions(self, *a, **k): return GeneratedBatch(questions=[])

    with pytest.raises(ValueError, match="question generation produced no questions"):
        plan_questions(["some words here"], EmptyAI())
