from sqlalchemy.orm import Session

from app.clients.protocols import AIClient
from app.models import Lesson, McqChoice, Question
from app.schemas import GeneratedQuestion

MCQ_WORDS_PER_Q = 175
FREE_WORDS_PER_Q = 350
MIN_Q, MAX_Q = 5, 100


def _clamp(n: int) -> int:
    return max(MIN_Q, min(MAX_Q, n))


def question_targets(word_count: int) -> tuple[int, int]:
    return _clamp(word_count // MCQ_WORDS_PER_Q), _clamp(word_count // FREE_WORDS_PER_Q)


def allocate(total: int, weights: list[int]) -> list[int]:
    """Largest-remainder split of total; ties go to the earlier index (stable sort)."""
    if sum(weights) == 0:
        weights = [1] * len(weights)
    s = sum(weights)
    raw = [total * w / s for w in weights]
    out = [int(r) for r in raw]
    order = sorted(range(len(raw)), key=lambda i: raw[i] - out[i], reverse=True)
    for i in order[: total - sum(out)]:
        out[i] += 1
    return out


def make_sections(page_texts: list[str], target_words: int = 900) -> list[str]:
    paragraphs = [p.strip() for t in page_texts for p in t.split("\n\n") if p.strip()]
    sections: list[list[str]] = []
    count = 0
    for p in paragraphs:
        n = len(p.split())
        if not sections or count + n > target_words:
            sections.append([]); count = 0
        sections[-1].append(p); count += n
    return ["\n\n".join(s) for s in sections]


def _validate(q: GeneratedQuestion) -> None:
    if q.type == "free_text":
        if not q.reference_answer:
            raise ValueError(f"free-text question missing reference_answer: {q.question_text!r}")
        return
    correct = sum(c.is_correct for c in q.choices)
    if len(q.choices) < 2:
        raise ValueError(f"MCQ needs >=2 choices: {q.question_text!r}")
    if correct == 0 or (q.type == "mcq_single" and correct != 1):
        raise ValueError(f"{q.type} has {correct} correct choices: {q.question_text!r}")


def generate_questions_for_lesson(session: Session, lesson: Lesson, ai: AIClient) -> None:
    lesson.questions.clear()
    session.flush()
    texts = [p.extracted_text or "" for p in lesson.pages]
    sections = make_sections(texts)
    words = [len(s.split()) for s in sections]
    n_mcq, n_free = question_targets(sum(words))
    mcq_alloc, free_alloc = allocate(n_mcq, words), allocate(n_free, words)

    for section, m, f in zip(sections, mcq_alloc, free_alloc):
        if m == 0 and f == 0:
            continue
        for gq in ai.generate_questions(section, m, f).questions:
            _validate(gq)
            q = Question(type=gq.type, question_text=gq.question_text,
                         explanation=gq.explanation, reference_answer=gq.reference_answer)
            q.choices = [McqChoice(choice_text=c.text, is_correct=c.is_correct, order_index=i)
                         for i, c in enumerate(gq.choices)]
            lesson.questions.append(q)
    session.flush()
