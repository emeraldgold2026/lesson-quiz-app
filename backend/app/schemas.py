from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


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
    # No default: OpenAI strict Structured Outputs rejects `default` in the schema.
    choices: list[GeneratedChoice]
    reference_answer: str | None = None  # pydantic default is dropped by to_strict_json_schema


class GeneratedBatch(BaseModel):
    questions: list[GeneratedQuestion]


class MoreQuestionsRequest(BaseModel):
    kind: Literal["mcq", "free_text"]
    count: int = Field(ge=1, le=20)


class MoreQuestionsOut(BaseModel):
    added: int
    total: int  # questions of this kind the lesson now has


class FreeTextVerdict(BaseModel):
    verdict: Literal["correct", "partially_correct", "incorrect"]
    feedback: str


class ChoiceOut(BaseModel):
    id: int
    text: str


class McqQuestionOut(BaseModel):
    id: int
    type: Literal["mcq_single", "mcq_multi"]
    question_text: str
    choices: list[ChoiceOut]


class FreeTextQuestionOut(BaseModel):
    id: int
    question_text: str


class McqSubmit(BaseModel):
    answers: dict[int, list[int]]  # question_id -> selected choice ids


class FreeTextSubmit(BaseModel):
    answers: dict[int, str]


class AnswerResultOut(BaseModel):
    question_id: int
    question_text: str
    question_type: str
    student_response: list[int] | str
    student_response_text: str  # readable answer: free text, or selected MCQ choice texts
    verdict: str
    feedback_text: str
    correct_answer_text: str


class AttemptSummaryOut(BaseModel):
    id: int
    lesson_id: int
    test_type: str
    started_at: datetime
    submitted_at: datetime | None
    score: float
    total_questions: int


class AttemptOut(AttemptSummaryOut):
    results: list[AnswerResultOut]
