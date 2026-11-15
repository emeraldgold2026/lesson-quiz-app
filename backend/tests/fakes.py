import hashlib

from app.clients.protocols import ChunkRecord
from app.schemas import FreeTextVerdict, GeneratedBatch, GeneratedChoice, GeneratedQuestion


class FakeAI:
    def __init__(self, page_texts=None, fail_on_page=None, verdicts=None, fail_grading=False):
        self.page_texts = page_texts or []
        self.fail_on_page = fail_on_page
        self.verdicts = verdicts or {}
        self.fail_grading = fail_grading
        self.extract_calls = 0
        self.generate_calls: list[tuple[str, int, int]] = []
        self.avoid_calls: list[list[str] | None] = []
        self._fresh = 0
        self.grade_calls: list[dict] = []

    def extract_page_text(self, image_bytes, mime_type):
        i = self.extract_calls
        self.extract_calls += 1
        if self.fail_on_page == i:
            raise RuntimeError(f"vision failed on page {i}")
        return self.page_texts[i] if i < len(self.page_texts) else f"page {i} text"

    def embed(self, texts):
        return [[float(len(t)), 0.0] for t in texts]

    def generate_questions(self, section_text, n_mcq, n_free_text, avoid=None):
        self.generate_calls.append((section_text, n_mcq, n_free_text))
        self.avoid_calls.append(avoid)
        if avoid is None:  # initial generation
            return self.batch([f"MCQ {i}?" for i in range(n_mcq)], [f"Free {i}?" for i in range(n_free_text)])
        # "more questions" call: wording is distinct on every call, so nothing repeats by accident
        return self.batch([self.fresh_text("MCQ") for _ in range(n_mcq)],
                          [self.fresh_text("Free") for _ in range(n_free_text)])

    def fresh_text(self, prefix):
        self._fresh += 1
        return f"{prefix} {hashlib.sha1(str(self._fresh).encode()).hexdigest()[:24]}?"

    @staticmethod
    def batch(mcq_texts, free_texts):
        return GeneratedBatch(questions=[
            GeneratedQuestion(
                type="mcq_single", question_text=t, explanation="because",
                choices=[GeneratedChoice(text="right", is_correct=True),
                         GeneratedChoice(text="wrong", is_correct=False)])
            for t in mcq_texts
        ] + [
            GeneratedQuestion(type="free_text", question_text=t,
                              explanation="because", choices=[], reference_answer=f"ref {i}")
            for i, t in enumerate(free_texts)
        ])

    def grade_free_text(self, question, student_answer, reference_answer, grounding):
        if self.fail_grading:
            raise RuntimeError("openai unavailable")
        self.grade_calls.append(dict(question=question, student_answer=student_answer,
                                     reference_answer=reference_answer, grounding=grounding))
        return self.verdicts.get(student_answer, FreeTextVerdict(verdict="incorrect", feedback="nope"))


class FakeStore:
    def __init__(self):
        self.data: dict[int, list[str]] = {}

    def upsert_chunks(self, lesson_id, chunks: list[ChunkRecord], vectors):
        self.data.setdefault(lesson_id, []).extend(c.text for c in chunks)

    def search(self, lesson_id, vector, k):
        return self.data.get(lesson_id, [])[:k]

    def delete_lesson(self, lesson_id):
        self.data.pop(lesson_id, None)
