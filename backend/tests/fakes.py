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
        self.grade_calls: list[dict] = []

    def extract_page_text(self, image_bytes, mime_type):
        i = self.extract_calls
        self.extract_calls += 1
        if self.fail_on_page == i:
            raise RuntimeError(f"vision failed on page {i}")
        return self.page_texts[i] if i < len(self.page_texts) else f"page {i} text"

    def embed(self, texts):
        return [[float(len(t)), 0.0] for t in texts]

    def generate_questions(self, section_text, n_mcq, n_free_text):
        self.generate_calls.append((section_text, n_mcq, n_free_text))
        qs = [
            GeneratedQuestion(
                type="mcq_single", question_text=f"MCQ {i}?", explanation="because",
                choices=[GeneratedChoice(text="right", is_correct=True),
                         GeneratedChoice(text="wrong", is_correct=False)])
            for i in range(n_mcq)
        ] + [
            GeneratedQuestion(type="free_text", question_text=f"Free {i}?",
                              explanation="because", reference_answer=f"ref {i}")
            for i in range(n_free_text)
        ]
        return GeneratedBatch(questions=qs)

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
