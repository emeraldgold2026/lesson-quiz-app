from typing import Literal

from app.clients.protocols import AIClient, VectorStore
from app.models import Question
from app.schemas import FreeTextVerdict

_POINTS = {"correct": 1.0, "partially_correct": 0.5, "incorrect": 0.0}


def grade_mcq(correct_choice_ids: set[int], selected_choice_ids: set[int]) -> Literal["correct", "incorrect"]:
    return "correct" if correct_choice_ids == selected_choice_ids else "incorrect"


def points(verdict: str) -> float:
    return _POINTS[verdict]


def grade_free_text(question: Question, answer: str, ai: AIClient, store: VectorStore,
                    top_k: int = 4) -> FreeTextVerdict:
    [vector] = ai.embed([f"{question.question_text}\n{answer}"])
    grounding = store.search(question.lesson_id, vector, top_k)
    return ai.grade_free_text(question.question_text, answer, question.reference_answer, grounding)
