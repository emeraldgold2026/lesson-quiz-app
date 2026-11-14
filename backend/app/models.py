from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Lesson(Base):
    __tablename__ = "lessons"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)  # processing/ready/failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    pages: Mapped[list["LessonPage"]] = relationship(
        back_populates="lesson", order_by="LessonPage.page_order", cascade="all, delete-orphan")
    questions: Mapped[list["Question"]] = relationship(
        back_populates="lesson", order_by="Question.id", cascade="all, delete-orphan")


class LessonPage(Base):
    __tablename__ = "lesson_pages"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"))
    page_order: Mapped[int] = mapped_column(Integer)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    lesson: Mapped[Lesson] = relationship(back_populates="pages")


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"))
    type: Mapped[str] = mapped_column(String)  # mcq_single/mcq_multi/free_text
    question_text: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)
    reference_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    lesson: Mapped[Lesson] = relationship(back_populates="questions")
    choices: Mapped[list["McqChoice"]] = relationship(
        back_populates="question", order_by="McqChoice.order_index", cascade="all, delete-orphan")


class McqChoice(Base):
    __tablename__ = "mcq_choices"
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    choice_text: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    order_index: Mapped[int] = mapped_column(Integer)
    question: Mapped[Question] = relationship(back_populates="choices")


class Attempt(Base):
    __tablename__ = "attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"))
    test_type: Mapped[str] = mapped_column(String)  # mcq/free_text
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    total_questions: Mapped[int] = mapped_column(Integer, default=0)
    answers: Mapped[list["AttemptAnswer"]] = relationship(
        back_populates="attempt", order_by="AttemptAnswer.id", cascade="all, delete-orphan")


class AttemptAnswer(Base):
    __tablename__ = "attempt_answers"
    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    student_response: Mapped[dict | list | str] = mapped_column(JSON)
    verdict: Mapped[str] = mapped_column(String)
    feedback_text: Mapped[str] = mapped_column(Text)
    correct_answer_text: Mapped[str] = mapped_column(Text)
    attempt: Mapped[Attempt] = relationship(back_populates="answers")
    question: Mapped[Question] = relationship()
