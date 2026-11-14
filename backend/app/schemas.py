from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class LessonOut(BaseModel):
    id: int
    title: str
    status: str
    error_message: str | None
    page_count: int
    created_at: datetime
    has_questions: bool


class GeneratedChoice(BaseModel):
    text: str
    is_correct: bool


class GeneratedQuestion(BaseModel):
    type: Literal["mcq_single", "mcq_multi", "free_text"]
    question_text: str
    explanation: str
    choices: list[GeneratedChoice] = []
    reference_answer: str | None = None


class GeneratedBatch(BaseModel):
    questions: list[GeneratedQuestion]


class FreeTextVerdict(BaseModel):
    verdict: Literal["correct", "partially_correct", "incorrect"]
    feedback: str
