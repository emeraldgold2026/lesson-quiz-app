import random
import re
from collections import Counter
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from app.clients.protocols import AIClient
from app.models import Lesson, McqChoice, Question
from app.schemas import GeneratedQuestion

MCQ_WORDS_PER_Q = 175
FREE_WORDS_PER_Q = 350
MIN_Q, MAX_Q = 5, 100
DUPLICATE_SIMILARITY = 0.85  # normalized-text similarity at or above which a question counts as a repeat
TOP_UP_ROUNDS = 2  # extra generation rounds to replace duplicates that were dropped


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


def plan_questions(page_texts: list[str], ai: AIClient) -> list[GeneratedQuestion]:
    """Call the LLM per section and return validated questions. Touches no database."""
    sections = make_sections(page_texts)
    words = [len(s.split()) for s in sections]
    n_mcq, n_free = question_targets(sum(words))
    mcq_alloc, free_alloc = allocate(n_mcq, words), allocate(n_free, words)

    planned: list[GeneratedQuestion] = []
    for section, m, f in zip(sections, mcq_alloc, free_alloc):
        if m == 0 and f == 0:
            continue
        for gq in ai.generate_questions(section, m, f).questions:
            _validate(gq)
            planned.append(gq)
    if not planned:  # fail the lesson so it can be retried, rather than "ready" with no test
        raise ValueError("question generation produced no questions")
    return planned


def _normalize(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def _is_duplicate(a: str, b: str) -> bool:
    """Same question after ignoring case/punctuation, or near-identical wording."""
    return a == b or SequenceMatcher(None, a, b).ratio() >= DUPLICATE_SIMILARITY


def plan_more_questions(page_texts: list[str], kind: str, count: int, existing: list[str],
                        ai: AIClient) -> list[GeneratedQuestion]:
    """Generate `count` extra questions of `kind` ("mcq" or "free_text"), steering the model away
    from `existing` question texts. Sections are drawn at random, weighted by length, so repeated
    calls spread over the whole lesson. Touches no database."""
    sections = make_sections(page_texts)
    if not sections:
        raise ValueError("lesson has no text to generate questions from")
    weights = [len(s.split()) for s in sections]
    wanted = {"mcq_single", "mcq_multi"} if kind == "mcq" else {"free_text"}
    avoid = list(existing)
    seen = [_normalize(t) for t in existing]
    planned: list[GeneratedQuestion] = []
    for _ in range(1 + TOP_UP_ROUNDS):  # later rounds replace questions dropped as duplicates
        need = count - len(planned)
        if need <= 0:
            break
        per_section = Counter(random.choices(range(len(sections)), weights=weights, k=need))
        for i in sorted(per_section):
            n = per_section[i]
            batch = ai.generate_questions(sections[i], n if kind == "mcq" else 0,
                                          n if kind == "free_text" else 0, avoid)
            for gq in batch.questions:
                if gq.type not in wanted:
                    continue
                _validate(gq)
                norm = _normalize(gq.question_text)
                if any(_is_duplicate(norm, s) for s in seen):
                    continue
                planned.append(gq)
                seen.append(norm)
                avoid.append(gq.question_text)
    if not planned:
        raise ValueError("question generation produced no new questions (all were duplicates)")
    return planned[:count]


def append_questions(session: Session, lesson: Lesson, questions: list[GeneratedQuestion]) -> None:
    """Add to the lesson's questions, keeping existing ones (past attempts reference them)."""
    for gq in questions:
        q = Question(type=gq.type, question_text=gq.question_text,
                     explanation=gq.explanation, reference_answer=gq.reference_answer)
        q.choices = [McqChoice(choice_text=c.text, is_correct=c.is_correct, order_index=i)
                     for i, c in enumerate(gq.choices)]
        lesson.questions.append(q)
    session.commit()


def store_questions(session: Session, lesson: Lesson, questions: list[GeneratedQuestion]) -> None:
    """Replace the lesson's questions; the caller owns the (short) transaction."""
    lesson.questions.clear()
    session.flush()
    for gq in questions:
        q = Question(type=gq.type, question_text=gq.question_text,
                     explanation=gq.explanation, reference_answer=gq.reference_answer)
        q.choices = [McqChoice(choice_text=c.text, is_correct=c.is_correct, order_index=i)
                     for i, c in enumerate(gq.choices)]
        lesson.questions.append(q)
    session.flush()
