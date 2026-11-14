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


def test_datetimes_roundtrip_as_utc_and_reject_naive():
    from datetime import datetime, timedelta, timezone

    import pytest
    from sqlalchemy.exc import StatementError

    sf = make_session_factory("sqlite://")
    plus2 = timezone(timedelta(hours=2))
    with sf() as s:
        s.add(Lesson(title="A", status="ready", created_at=datetime(2026, 1, 1, 12, tzinfo=plus2)))
        s.commit()
    with sf() as s:
        got = s.query(Lesson).one().created_at
        assert got == datetime(2026, 1, 1, 10, tzinfo=timezone.utc) and got.tzinfo is timezone.utc
        s.add(Lesson(title="B", status="ready", created_at=datetime(2026, 1, 1)))
        with pytest.raises(StatementError, match="naive datetime"):
            s.commit()
