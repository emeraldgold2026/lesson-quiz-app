from app.db import make_session_factory
from app.models import Lesson, LessonPage, Question, McqChoice


def test_lesson_with_pages_and_question_roundtrip():
    sf = make_session_factory("sqlite://")
    with sf() as s:
        lesson = Lesson(title="Ch1", status="processing", page_count=1)
        lesson.pages.append(LessonPage(page_order=0, extracted_text="hello"))
        q = Question(type="mcq_single", question_text="Q?", explanation="because")
        q.choices.append(McqChoice(choice_text="A", is_correct=True, order_index=0))
        lesson.questions.append(q)
        s.add(lesson)
        s.commit()
        got = s.get(Lesson, lesson.id)
        assert got.pages[0].extracted_text == "hello"
        assert got.questions[0].choices[0].is_correct is True
        assert got.created_at is not None
