# Lesson Quiz App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single-user app that ingests textbook page photos, generates MCQ and free-text tests from them, grades submissions, and stores attempt history.

**Architecture:** FastAPI backend (SQLite via SQLAlchemy for relational data, Qdrant for chunk embeddings, OpenAI for vision/embeddings/generation/grading) behind narrow `AIClient` and `VectorStore` protocols so everything is testable with fakes. Next.js App Router frontend talks to the backend over REST only.

**Tech Stack:** Python 3.12, uv, FastAPI, SQLAlchemy 2.x, Pydantic Settings, openai SDK, qdrant-client, pytest; Next.js (App Router, TypeScript), React, Tailwind CSS, Vitest + React Testing Library.

**Spec:** `docs/superpowers/specs/2026-11-14-lesson-quiz-app-design.md`

## Global Constraints

- Python work uses `uv` only (`uv init`, `uv add`, `uv run`, `uv sync`); `uv init` is followed by creating `requirements.txt` (kept in sync via `uv export --no-hashes -o requirements.txt`).
- Backend: Python + FastAPI, Pydantic models for request/response schemas, run with `uv run uvicorn app.main:app --reload`.
- Frontend: Next.js + React function components/hooks + Tailwind utility classes; no CSS files beyond the generated `globals.css`, no CSS-in-JS, no class components.
- Tests: `pytest` under `backend/tests/` mirroring `backend/app/`; Vitest + React Testing Library for frontend. Tests are written with each feature. MCQ grading tested without mocks; ingestion/generation/free-text grading tested against fake `AIClient`/`VectorStore`.
- Secrets `OPENAI_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY` live only in a gitignored backend `.env`, loaded via Pydantic Settings. Frontend never sees them.
- Models: GPT-5 for vision, `text-embedding-3-small` for embeddings. Qdrant: single collection `lesson_chunks`, payload `lesson_id`, `page_order`, `chunk_index`, `text`.
- Chunks ~500–800 tokens with slight overlap, boundaries on paragraph breaks.
- Question counts: ~1 MCQ per 150–200 words, ~1 free-text per 300–400 words, each clamped to [5, 100].
- Scoring: MCQ correct=1/incorrect=0; free-text correct=1, partially_correct=0.5, incorrect=0.
- MCQ correct iff selected set == correct set. No LLM at MCQ grading time.
- Fail fast: validate only at system boundaries; no swallowed exceptions; ingestion failures set `status=failed` + `error_message`; grading-call failures fail the submission (no fabricated verdicts).
- No auth, no review/edit UI, no job queue (FastAPI `BackgroundTasks`), no per-lesson collections.
- Never use `--no-verify`; one logical change per commit; do not commit failing tests.

**Plan decisions beyond the spec:**
- Spec says images are discarded after processing but also requires a retry affordance on failure. Resolution: uploaded bytes are written to `backend/data/uploads/<lesson_id>/<page_order>.<ext>` during processing, deleted on success, and kept on failure so `POST /lessons/{id}/retry` can re-run. (Adds one endpoint to the spec's API list.)
- Question generation runs as the final step of the same background task (chained after chunks are upserted, before status becomes `ready`), so `ready` means "tests are available".

## File Structure

```
backend/
  pyproject.toml, requirements.txt, .env.example, .gitignore
  app/
    main.py            # app factory, CORS, router includes
    config.py          # Settings (pydantic-settings)
    db.py              # engine, SessionLocal factory, Base, get_session
    models.py          # SQLAlchemy ORM tables
    schemas.py         # Pydantic API + LLM structured-output schemas
    deps.py            # get_ai, get_store, get_session_factory (overridable)
    clients/
      protocols.py     # AIClient, VectorStore protocols
      openai_client.py # OpenAIClient implements AIClient
      qdrant_store.py  # QdrantStore implements VectorStore
    services/
      chunking.py      # chunk_text
      ingestion.py     # run_ingestion(lesson_id, ...)
      generation.py    # allocate, make_sections, generate_questions
      grading.py       # grade_mcq (pure), grade_free_text, score helpers
      attempts.py      # build/submit tests, persist attempts
    routers/
      lessons.py       # /lessons...
      tests.py         # mcq/free-text test + submit
      attempts.py      # /attempts, /lessons/{id}/attempts
  tests/               # mirrors app/; conftest.py + fakes.py
frontend/              # create-next-app output + src/lib/api.ts, components, pages
```

---

### Task 1: Backend scaffold, config, DB models

**Files:**
- Create: `backend/pyproject.toml` (via uv), `backend/requirements.txt`, `backend/.env.example`, `backend/.gitignore`
- Create: `backend/app/__init__.py`, `config.py`, `db.py`, `models.py`, `main.py`
- Test: `backend/tests/test_models.py`, `backend/tests/test_main.py`

**Interfaces:**
- Produces: `Settings` (fields `openai_api_key, qdrant_url, qdrant_api_key, database_url="sqlite:///data/app.db", upload_dir="data/uploads", cors_origins=["http://localhost:3000"]`); `Base`, `make_session_factory(url) -> sessionmaker`; ORM classes `Lesson, LessonPage, Question, McqChoice, Attempt, AttemptAnswer` with fields exactly as spec §3; `create_app() -> FastAPI` with `GET /health`.

- [ ] **Step 1: Scaffold**

```bash
cd /Users/emeraldtech/workspace/lesson-test
uv init backend --app --no-workspace
cd backend
uv add fastapi "uvicorn[standard]" sqlalchemy pydantic-settings openai qdrant-client python-multipart
uv add --dev pytest httpx
uv export --no-hashes --no-dev -o requirements.txt
printf '.env\n.venv/\n__pycache__/\ndata/\n.pytest_cache/\n' > .gitignore
printf 'OPENAI_API_KEY=\nQDRANT_URL=\nQDRANT_API_KEY=\n' > .env.example
rm -f main.py hello.py; mkdir -p app/clients app/services app/routers tests && touch app/__init__.py app/clients/__init__.py app/services/__init__.py app/routers/__init__.py
```

- [ ] **Step 2: Write failing tests**

`backend/tests/test_models.py`:
```python
from app.db import Base, make_session_factory
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
```

`backend/tests/test_main.py`:
```python
from fastapi.testclient import TestClient
from app.main import create_app


def test_health():
    assert TestClient(create_app()).get("/health").json() == {"status": "ok"}
```

- [ ] **Step 3: Run — expect FAIL (ImportError)**

Run: `cd backend && uv run pytest -v`

- [ ] **Step 4: Implement**

`app/config.py`:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    database_url: str = "sqlite:///data/app.db"
    upload_dir: str = "data/uploads"
    cors_origins: list[str] = ["http://localhost:3000"]
```

`app/db.py`:
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


def make_session_factory(url: str) -> sessionmaker:
    kwargs = {}
    if url == "sqlite://":  # in-memory: share one connection across threads
        kwargs = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
    elif url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}}
    engine = create_engine(url, **kwargs)
    from app import models  # noqa: F401  (register tables)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)
```

`app/models.py`:
```python
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
```

`app/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings


def create_app() -> FastAPI:
    settings = Settings()
    app = FastAPI(title="Lesson Quiz")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_methods=["*"], allow_headers=["*"])

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 5: Run — expect PASS.** `cd backend && uv run pytest -v`

- [ ] **Step 6: Commit**

```bash
git add backend && git commit -m "Scaffold FastAPI backend with SQLAlchemy models"
```

---

### Task 2: Schemas, client protocols, fakes

**Files:**
- Create: `backend/app/schemas.py`, `backend/app/clients/protocols.py`, `backend/tests/fakes.py`, `backend/tests/conftest.py`
- Test: `backend/tests/test_fakes.py`

**Interfaces:**
- Produces (schemas.py, Pydantic):
  - `GeneratedChoice(text: str, is_correct: bool)`
  - `GeneratedQuestion(type: Literal["mcq_single","mcq_multi","free_text"], question_text: str, explanation: str, choices: list[GeneratedChoice] = [], reference_answer: str | None = None)`
  - `GeneratedBatch(questions: list[GeneratedQuestion])`
  - `FreeTextVerdict(verdict: Literal["correct","partially_correct","incorrect"], feedback: str)`
- Produces (protocols.py):
  - `ChunkRecord(page_order: int, chunk_index: int, text: str)` dataclass
  - `AIClient`: `extract_page_text(image_bytes: bytes, mime_type: str) -> str`; `embed(texts: list[str]) -> list[list[float]]`; `generate_questions(section_text: str, n_mcq: int, n_free_text: int) -> GeneratedBatch`; `grade_free_text(question: str, student_answer: str, reference_answer: str, grounding: list[str]) -> FreeTextVerdict`
  - `VectorStore`: `upsert_chunks(lesson_id: int, chunks: list[ChunkRecord], vectors: list[list[float]]) -> None`; `search(lesson_id: int, vector: list[float], k: int) -> list[str]`; `delete_lesson(lesson_id: int) -> None`
- Produces (fakes.py): `FakeAI` (records calls; configurable `page_texts: list[str]`, `fail_on_page: int | None`, `verdicts: dict[str, FreeTextVerdict]`; `generate_questions` returns exactly `n_mcq` single-choice + `n_free_text` free-text questions; `embed` returns `[[float(len(t)), 0.0]]` per text), `FakeStore` (in-memory dict keyed by lesson_id; `search` returns first `k` stored texts).
- conftest fixtures: `session_factory`, `fake_ai`, `fake_store`, `client` (TestClient with deps overridden — wired in Task 7 once `deps.py` exists; define `session_factory`, `fake_ai`, `fake_store` now).

- [ ] **Step 1: Write failing test** `tests/test_fakes.py`:

```python
from tests.fakes import FakeAI, FakeStore
from app.clients.protocols import ChunkRecord


def test_fake_ai_generates_requested_counts():
    batch = FakeAI().generate_questions("text", n_mcq=2, n_free_text=1)
    assert [q.type for q in batch.questions].count("free_text") == 1
    assert len(batch.questions) == 3
    assert all(any(c.is_correct for c in q.choices) for q in batch.questions if q.type != "free_text")


def test_fake_store_scoped_by_lesson():
    s = FakeStore()
    s.upsert_chunks(1, [ChunkRecord(0, 0, "a")], [[1.0]])
    s.upsert_chunks(2, [ChunkRecord(0, 0, "b")], [[1.0]])
    assert s.search(1, [1.0], 5) == ["a"]
```

- [ ] **Step 2: Run — expect FAIL.** `uv run pytest tests/test_fakes.py -v`

- [ ] **Step 3: Implement**

`app/schemas.py` (LLM schemas; API response schemas are added in Tasks 6–8):
```python
from typing import Literal

from pydantic import BaseModel


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
```

`app/clients/protocols.py`:
```python
from dataclasses import dataclass
from typing import Protocol

from app.schemas import FreeTextVerdict, GeneratedBatch


@dataclass(frozen=True)
class ChunkRecord:
    page_order: int
    chunk_index: int
    text: str


class AIClient(Protocol):
    def extract_page_text(self, image_bytes: bytes, mime_type: str) -> str: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...
    def generate_questions(self, section_text: str, n_mcq: int, n_free_text: int) -> GeneratedBatch: ...
    def grade_free_text(self, question: str, student_answer: str, reference_answer: str,
                        grounding: list[str]) -> FreeTextVerdict: ...


class VectorStore(Protocol):
    def upsert_chunks(self, lesson_id: int, chunks: list[ChunkRecord],
                      vectors: list[list[float]]) -> None: ...
    def search(self, lesson_id: int, vector: list[float], k: int) -> list[str]: ...
    def delete_lesson(self, lesson_id: int) -> None: ...
```

`tests/fakes.py`:
```python
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
```

`tests/conftest.py`:
```python
import pytest

from app.db import make_session_factory
from tests.fakes import FakeAI, FakeStore


@pytest.fixture
def session_factory():
    return make_session_factory("sqlite://")


@pytest.fixture
def fake_ai():
    return FakeAI()


@pytest.fixture
def fake_store():
    return FakeStore()
```
Add empty `tests/__init__.py`.

- [ ] **Step 4: Run — expect PASS.** **Step 5: Commit** `git commit -am "Add AI/vector-store protocols and test fakes"` (after `git add backend`).

---

### Task 3: Chunking

**Files:** Create `backend/app/services/chunking.py`; Test `backend/tests/services/test_chunking.py` (add `tests/services/__init__.py`).

**Interfaces:**
- Produces: `chunk_pages(pages: list[tuple[int, str]], max_tokens: int = 650, overlap_tokens: int = 60) -> list[ChunkRecord]` — input is `(page_order, text)` in page order; chunks never exceed `max_tokens` (token ≈ whitespace word × 1.3), split on blank-line paragraph boundaries; a paragraph larger than the limit is split by words; each chunk after the first in a page-run begins with the last `overlap_tokens` words of the previous chunk. `chunk_index` is global and sequential from 0. `page_order` is the page the chunk's first paragraph came from.

- [ ] **Step 1: Failing tests**

```python
from app.services.chunking import chunk_pages


def words(n, tag="w"):
    return " ".join(f"{tag}{i}" for i in range(n))


def test_short_text_single_chunk():
    chunks = chunk_pages([(0, "one para\n\nsecond para")])
    assert len(chunks) == 1 and chunks[0].chunk_index == 0 and chunks[0].page_order == 0


def test_splits_on_paragraph_boundaries_and_indexes_sequentially():
    pages = [(0, words(300, "a") + "\n\n" + words(300, "b")), (1, words(300, "c"))]
    chunks = chunk_pages(pages, max_tokens=500, overlap_tokens=20)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert len(chunks) >= 2
    assert chunks[-1].page_order == 1


def test_overlap_repeats_tail_of_previous_chunk():
    chunks = chunk_pages([(0, words(300, "a") + "\n\n" + words(300, "b"))], max_tokens=500, overlap_tokens=20)
    tail = chunks[0].text.split()[-20:]
    assert chunks[1].text.split()[:20] == tail


def test_oversized_paragraph_is_split_by_words():
    chunks = chunk_pages([(0, words(2000))], max_tokens=500, overlap_tokens=0)
    assert len(chunks) > 1
    assert all(len(c.text.split()) * 1.3 <= 500 + 1 for c in chunks)
```

- [ ] **Step 2: Run — FAIL.** **Step 3: Implement**

```python
from app.clients.protocols import ChunkRecord

TOKENS_PER_WORD = 1.3


def chunk_pages(pages: list[tuple[int, str]], max_tokens: int = 650,
                overlap_tokens: int = 60) -> list[ChunkRecord]:
    max_words = int(max_tokens / TOKENS_PER_WORD)
    overlap_words = int(overlap_tokens / TOKENS_PER_WORD) if overlap_tokens else 0

    # flatten to (page_order, paragraph_words), splitting oversized paragraphs
    units: list[tuple[int, list[str]]] = []
    for page_order, text in pages:
        for para in (p.strip() for p in text.split("\n\n")):
            if not para:
                continue
            ws = para.split()
            for i in range(0, len(ws), max_words):
                units.append((page_order, ws[i:i + max_words]))

    chunks: list[ChunkRecord] = []
    cur: list[str] = []
    cur_page = 0
    carry: list[str] = []

    def flush():
        nonlocal cur, carry
        if not cur:
            return
        chunks.append(ChunkRecord(cur_page, len(chunks), " ".join(carry + cur)))
        carry = cur[-overlap_words:] if overlap_words else []
        cur = []

    for page_order, ws in units:
        if cur and len(carry) + len(cur) + len(ws) > max_words:
            flush()
        if not cur:
            cur_page = page_order
        cur.extend(ws)
    flush()
    return chunks
```
Note: overlap is counted in the size check via `len(carry)`; with `overlap_tokens=0` carry is empty.

- [ ] **Step 4: Run — PASS** (if the oversize test fails by an off-by-one, fix the implementation, not the test). **Step 5: Commit** `Add paragraph-aware chunking`.

---

### Task 4: Ingestion service

**Files:** Create `backend/app/services/ingestion.py`; Test `backend/tests/services/test_ingestion.py`.

**Interfaces:**
- Consumes: `chunk_pages`, `AIClient`, `VectorStore`, models, `generate_questions_for_lesson` (Task 5 — **import lazily is not needed**; ingestion takes it as a callable parameter so this task is independently testable).
- Produces: `upload_path(upload_dir: str, lesson_id: int, page_order: int, ext: str) -> Path`; `run_ingestion(lesson_id: int, *, session_factory, ai: AIClient, store: VectorStore, upload_dir: str, after_ingest: Callable[[Session, Lesson], None]) -> None`. Behaviour: sets pages' `extracted_text` from images found at `upload_dir/<lesson_id>/<page_order>.<ext>`; chunks, embeds, upserts; calls `after_ingest(session, lesson)`; on success sets `ready` and deletes upload dir; on any exception sets `failed`, `error_message=f"{type(e).__name__}: {e}"`, keeps uploads, and calls `store.delete_lesson(lesson_id)` so retry doesn't duplicate chunks. Never re-raises (it is a background task; the failure is recorded in the DB, which is the user-visible surface). Retry re-running is safe: it re-extracts all pages and `store.delete_lesson` first.

- [ ] **Step 1: Failing tests**

```python
from pathlib import Path

from app.models import Lesson, LessonPage
from app.services.ingestion import run_ingestion, upload_path
from tests.fakes import FakeAI


def _seed(session_factory, tmp_path, n_pages=2):
    with session_factory() as s:
        lesson = Lesson(title="L", status="processing", page_count=n_pages)
        for i in range(n_pages):
            lesson.pages.append(LessonPage(page_order=i))
        s.add(lesson); s.commit()
        lid = lesson.id
    for i in range(n_pages):
        p = upload_path(str(tmp_path), lid, i, "png")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"img")
    return lid


def test_success_extracts_chunks_marks_ready_and_deletes_uploads(session_factory, fake_store, tmp_path):
    lid = _seed(session_factory, tmp_path)
    ai = FakeAI(page_texts=["alpha text", "beta text"])
    called = []
    run_ingestion(lid, session_factory=session_factory, ai=ai, store=fake_store,
                  upload_dir=str(tmp_path), after_ingest=lambda s, l: called.append(l.id))
    with session_factory() as s:
        lesson = s.get(Lesson, lid)
        assert lesson.status == "ready" and lesson.error_message is None
        assert [p.extracted_text for p in lesson.pages] == ["alpha text", "beta text"]
    assert fake_store.data[lid]
    assert called == [lid]
    assert not (tmp_path / str(lid)).exists()


def test_failure_marks_failed_keeps_uploads_and_clears_vectors(session_factory, fake_store, tmp_path):
    lid = _seed(session_factory, tmp_path)
    ai = FakeAI(fail_on_page=1)
    run_ingestion(lid, session_factory=session_factory, ai=ai, store=fake_store,
                  upload_dir=str(tmp_path), after_ingest=lambda s, l: None)
    with session_factory() as s:
        lesson = s.get(Lesson, lid)
        assert lesson.status == "failed"
        assert "vision failed on page 1" in lesson.error_message
    assert (tmp_path / str(lid)).exists()
    assert lid not in fake_store.data


def test_after_ingest_failure_also_marks_failed(session_factory, fake_store, tmp_path):
    lid = _seed(session_factory, tmp_path, 1)
    def boom(s, l): raise ValueError("gen broke")
    run_ingestion(lid, session_factory=session_factory, ai=FakeAI(), store=fake_store,
                  upload_dir=str(tmp_path), after_ingest=boom)
    with session_factory() as s:
        assert s.get(Lesson, lid).status == "failed"
```

- [ ] **Step 2: Run — FAIL.** **Step 3: Implement**

```python
import logging
import mimetypes
import shutil
from pathlib import Path
from typing import Callable

from sqlalchemy.orm import Session

from app.clients.protocols import AIClient, VectorStore
from app.models import Lesson
from app.services.chunking import chunk_pages

log = logging.getLogger(__name__)


def upload_path(upload_dir: str, lesson_id: int, page_order: int, ext: str) -> Path:
    return Path(upload_dir) / str(lesson_id) / f"{page_order}.{ext}"


def _find_image(upload_dir: str, lesson_id: int, page_order: int) -> Path:
    matches = sorted((Path(upload_dir) / str(lesson_id)).glob(f"{page_order}.*"))
    if not matches:
        raise FileNotFoundError(f"missing upload for lesson {lesson_id} page {page_order}")
    return matches[0]


def run_ingestion(lesson_id: int, *, session_factory, ai: AIClient, store: VectorStore,
                  upload_dir: str, after_ingest: Callable[[Session, Lesson], None]) -> None:
    with session_factory() as session:
        lesson = session.get(Lesson, lesson_id)
        try:
            store.delete_lesson(lesson_id)  # idempotent for retries
            for page in lesson.pages:
                img = _find_image(upload_dir, lesson_id, page.page_order)
                mime = mimetypes.guess_type(img.name)[0] or "image/png"
                page.extracted_text = ai.extract_page_text(img.read_bytes(), mime)
            session.flush()

            chunks = chunk_pages([(p.page_order, p.extracted_text) for p in lesson.pages])
            vectors = ai.embed([c.text for c in chunks])
            store.upsert_chunks(lesson_id, chunks, vectors)

            after_ingest(session, lesson)
            lesson.status, lesson.error_message = "ready", None
            session.commit()
            shutil.rmtree(Path(upload_dir) / str(lesson_id), ignore_errors=True)
        except Exception as e:  # recorded in DB; this runs as a background task
            log.exception("ingestion failed for lesson %s", lesson_id)
            session.rollback()
            store.delete_lesson(lesson_id)
            lesson = session.get(Lesson, lesson_id)
            lesson.status = "failed"
            lesson.error_message = f"{type(e).__name__}: {e}"
            session.commit()
```
(The `except Exception` here is deliberate and logs + persists; it is the documented boundary where a background task must record its failure.)

- [ ] **Step 4: Run — PASS. Step 5: Commit** `Add ingestion pipeline`.

---

### Task 5: Question generation

**Files:** Create `backend/app/services/generation.py`; Test `backend/tests/services/test_generation.py`.

**Interfaces:**
- Consumes: `AIClient.generate_questions`, models, `chunk_pages`.
- Produces: `allocate(total: int, weights: list[int]) -> list[int]` (largest-remainder; sums to `total`; all-zero weights → even spread); `make_sections(page_texts: list[str], target_words: int = 900) -> list[str]` (sequential, paragraph-respecting grouping in page order); `question_targets(word_count: int) -> tuple[int, int]` returning `(n_mcq, n_free_text)` = `clamp(words // 175, 5, 100)`, `clamp(words // 350, 5, 100)`; `generate_questions_for_lesson(session: Session, lesson: Lesson, ai: AIClient) -> None` — adds `Question`/`McqChoice` rows to the session (no commit). Retry safety: deletes the lesson's existing questions first. Validates LLM output at the boundary: an MCQ with no correct choice, `mcq_single` with ≠1 correct, fewer than 2 choices, or a free-text question without `reference_answer` raises `ValueError` (→ lesson fails, per fail-fast).

- [ ] **Step 1: Failing tests**

```python
import pytest

from app.models import Lesson, LessonPage
from app.schemas import GeneratedBatch, GeneratedChoice, GeneratedQuestion
from app.services.generation import (allocate, generate_questions_for_lesson,
                                     make_sections, question_targets)
from tests.fakes import FakeAI


def test_allocate_sums_to_total():
    assert sum(allocate(10, [1, 1, 1])) == 10
    assert allocate(10, [3, 1]) == [8, 2] or sum(allocate(10, [3, 1])) == 10
    assert sum(allocate(7, [0, 0])) == 7


def test_question_targets_clamped():
    assert question_targets(10) == (5, 5)
    assert question_targets(1750) == (10, 5)
    assert question_targets(10**6) == (100, 100)


def test_make_sections_groups_sequentially():
    para = " ".join(["w"] * 500)
    sections = make_sections([para, para, para], target_words=900)
    assert len(sections) == 2 and sections[0].count("w") == 500 + 500 - 0 or len(sections) >= 2


def _lesson(session, texts):
    lesson = Lesson(title="L", status="processing", page_count=len(texts))
    for i, t in enumerate(texts):
        lesson.pages.append(LessonPage(page_order=i, extracted_text=t))
    session.add(lesson); session.flush()
    return lesson


def test_generates_and_persists_questions(session_factory):
    ai = FakeAI()
    with session_factory() as s:
        lesson = _lesson(s, [" ".join(["word"] * 1800)])
        generate_questions_for_lesson(s, lesson, ai)
        s.commit()
        n_mcq, n_free = question_targets(1800)
        types = [q.type for q in lesson.questions]
        assert types.count("mcq_single") == n_mcq and types.count("free_text") == n_free
        assert sum(c[1] for c in ai.generate_calls) == n_mcq
        free = next(q for q in lesson.questions if q.type == "free_text")
        assert free.reference_answer


class BadAI(FakeAI):
    def __init__(self, q): super().__init__(); self.q = q
    def generate_questions(self, *a, **k): return GeneratedBatch(questions=[self.q])


@pytest.mark.parametrize("q", [
    GeneratedQuestion(type="mcq_single", question_text="q", explanation="e",
                      choices=[GeneratedChoice(text="a", is_correct=False), GeneratedChoice(text="b", is_correct=False)]),
    GeneratedQuestion(type="mcq_single", question_text="q", explanation="e",
                      choices=[GeneratedChoice(text="a", is_correct=True), GeneratedChoice(text="b", is_correct=True)]),
    GeneratedQuestion(type="free_text", question_text="q", explanation="e"),
])
def test_invalid_llm_output_raises(session_factory, q):
    with session_factory() as s:
        lesson = _lesson(s, ["some words here"])
        with pytest.raises(ValueError):
            generate_questions_for_lesson(s, lesson, BadAI(q))
```

- [ ] **Step 2: Run — FAIL. Step 3: Implement**

```python
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
```
Tighten the two loose assertions in `test_allocate_sums_to_total`/`test_make_sections_*` to exact values once the implementation passes (`allocate(10,[3,1]) == [8, 2]`; for three 500-word paragraphs with target 900 → `len(sections) == 3`, since 500+500 > 900).

- [ ] **Step 4: Run — PASS. Step 5: Commit** `Add section-based question generation`.

---

### Task 6: Grading (MCQ pure function, free-text, scoring)

**Files:** Create `backend/app/services/grading.py`; Test `backend/tests/services/test_grading.py`.

**Interfaces:**
- Produces: `grade_mcq(correct_choice_ids: set[int], selected_choice_ids: set[int]) -> Literal["correct","incorrect"]`; `points(verdict: str) -> float` (`correct`→1.0, `partially_correct`→0.5, else 0.0); `grade_free_text(question: Question, answer: str, ai: AIClient, store: VectorStore, top_k: int = 4) -> FreeTextVerdict` — embeds `f"{question.question_text}\n{answer}"`, retrieves top-k for `question.lesson_id`, calls `ai.grade_free_text(...)`. Exceptions propagate (no fabricated verdict).

- [ ] **Step 1: Failing tests**

```python
import pytest

from app.models import Question
from app.schemas import FreeTextVerdict
from app.services.grading import grade_free_text, grade_mcq, points
from tests.fakes import FakeAI, FakeStore


@pytest.mark.parametrize("correct,selected,expected", [
    ({1}, {1}, "correct"), ({1}, {2}, "incorrect"),
    ({1, 2}, {1}, "incorrect"), ({1, 2}, {1, 2, 3}, "incorrect"),
    ({1, 2}, {2, 1}, "correct"), ({1}, set(), "incorrect"),
])
def test_grade_mcq(correct, selected, expected):
    assert grade_mcq(correct, selected) == expected


def test_points():
    assert (points("correct"), points("partially_correct"), points("incorrect")) == (1.0, 0.5, 0.0)


def test_free_text_uses_reference_and_grounding(fake_store):
    fake_store.data[7] = ["chunk A", "chunk B"]
    ai = FakeAI(verdicts={"mine": FreeTextVerdict(verdict="partially_correct", feedback="half")})
    q = Question(id=1, lesson_id=7, type="free_text", question_text="Why?",
                 explanation="e", reference_answer="because")
    v = grade_free_text(q, "mine", ai, fake_store)
    assert v.verdict == "partially_correct"
    call = ai.grade_calls[0]
    assert call["reference_answer"] == "because" and call["grounding"] == ["chunk A", "chunk B"]


def test_free_text_propagates_ai_failure(fake_store):
    q = Question(id=1, lesson_id=7, type="free_text", question_text="Why?", explanation="e", reference_answer="r")
    with pytest.raises(RuntimeError):
        grade_free_text(q, "x", FakeAI(fail_grading=True), fake_store)
```

- [ ] **Step 2: Run — FAIL. Step 3: Implement**

```python
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
```

- [ ] **Step 4: Run — PASS. Step 5: Commit** `Add MCQ and free-text grading`.

---

### Task 7: Lessons API (create, list, detail, retry) + DI

**Files:** Create `backend/app/deps.py`, `backend/app/routers/lessons.py`; Modify `backend/app/main.py`, `backend/app/schemas.py`, `backend/tests/conftest.py`; Test `backend/tests/routers/test_lessons.py` (+ `__init__.py`).

**Interfaces:**
- Produces (deps.py): `get_settings() -> Settings`, `get_session_factory() -> sessionmaker`, `get_ai() -> AIClient`, `get_store() -> VectorStore`, `get_session(sf = Depends(get_session_factory)) -> Iterator[Session]`. Real implementations built from Settings (cached with `functools.lru_cache`) — `OpenAIClient`/`QdrantStore` imported inside the getters so tests never construct them.
- Produces (schemas.py): `LessonOut(id, title, status, error_message: str|None, page_count, created_at: datetime, has_questions: bool)`.
- Endpoints: `POST /lessons` (multipart: `title: str`, `files: list[UploadFile]`) → 202 `LessonOut`; `GET /lessons` → `list[LessonOut]` newest first; `GET /lessons/{id}` → `LessonOut` (404 if missing); `POST /lessons/{id}/retry` → 202 `LessonOut` (409 unless `failed`).
- Upload validation (boundary): ≥1 file, each `content_type` in `{image/png, image/jpeg, image/webp}` else 422; empty title → 422. Page order = order of `files` in the form.
- conftest additions: `client` fixture that builds `create_app()` and sets `app.dependency_overrides` for `get_session_factory`, `get_ai`, `get_store`, `get_settings` (upload_dir → `tmp_path`).

- [ ] **Step 1: Failing tests**

```python
from fastapi.testclient import TestClient

from app.deps import get_ai, get_session_factory, get_settings, get_store
from app.config import Settings
from app.main import create_app
from tests.fakes import FakeAI

PNG = ("p.png", b"\x89PNG", "image/png")


def make_client(session_factory, ai, store, tmp_path):
    app = create_app()
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    app.dependency_overrides[get_ai] = lambda: ai
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_settings] = lambda: Settings(upload_dir=str(tmp_path))
    return TestClient(app)


def test_create_lesson_runs_ingestion_and_generation(session_factory, fake_store, tmp_path):
    ai = FakeAI(page_texts=["alpha " * 100, "beta " * 100])
    c = make_client(session_factory, ai, fake_store, tmp_path)
    r = c.post("/lessons", data={"title": "Ch1"}, files=[("files", PNG), ("files", PNG)])
    assert r.status_code == 202 and r.json()["status"] == "processing"
    got = c.get(f"/lessons/{r.json()['id']}").json()  # TestClient ran the background task already
    assert got["status"] == "ready" and got["page_count"] == 2 and got["has_questions"] is True


def test_create_lesson_validates_input(session_factory, fake_store, tmp_path):
    c = make_client(session_factory, FakeAI(), fake_store, tmp_path)
    assert c.post("/lessons", data={"title": "x"}, files=[("files", ("a.txt", b"x", "text/plain"))]).status_code == 422
    assert c.post("/lessons", data={"title": " "}, files=[("files", PNG)]).status_code == 422
    assert c.post("/lessons", data={"title": "x"}).status_code == 422


def test_failed_lesson_can_be_retried(session_factory, fake_store, tmp_path):
    ai = FakeAI(fail_on_page=0)
    c = make_client(session_factory, ai, fake_store, tmp_path)
    lid = c.post("/lessons", data={"title": "T"}, files=[("files", PNG)]).json()["id"]
    assert c.get(f"/lessons/{lid}").json()["status"] == "failed"
    ai.fail_on_page = None
    assert c.post(f"/lessons/{lid}/retry").status_code == 202
    assert c.get(f"/lessons/{lid}").json()["status"] == "ready"
    assert c.post(f"/lessons/{lid}/retry").status_code == 409


def test_list_and_404(session_factory, fake_store, tmp_path):
    c = make_client(session_factory, FakeAI(), fake_store, tmp_path)
    assert c.get("/lessons").json() == []
    assert c.get("/lessons/999").status_code == 404
```
Note: `FakeAI.extract_calls` is cumulative, so in the retry test reset `ai.extract_calls = 0` along with `fail_on_page = None` before retrying (or key failure to a flag) — adjust the test accordingly when running.

- [ ] **Step 2: Run — FAIL. Step 3: Implement**

`app/deps.py`:
```python
from functools import lru_cache
from typing import Iterator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.clients.protocols import AIClient, VectorStore
from app.config import Settings
from app.db import make_session_factory


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_session_factory():
    return make_session_factory(get_settings().database_url)


def get_session(sf=Depends(get_session_factory)) -> Iterator[Session]:
    with sf() as session:
        yield session


@lru_cache
def get_ai() -> AIClient:
    from app.clients.openai_client import OpenAIClient
    return OpenAIClient(api_key=get_settings().openai_api_key)


@lru_cache
def get_store() -> VectorStore:
    from app.clients.qdrant_store import QdrantStore
    s = get_settings()
    return QdrantStore(url=s.qdrant_url, api_key=s.qdrant_api_key)
```
Also `Path(database_url path).parent.mkdir` — in `make_session_factory`, for file-based sqlite create the parent dir:
```python
if url.startswith("sqlite:///"):
    Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
```
(add `from pathlib import Path` to `db.py`).

`LessonOut` in `schemas.py`:
```python
from datetime import datetime

class LessonOut(BaseModel):
    id: int
    title: str
    status: str
    error_message: str | None
    page_count: int
    created_at: datetime
    has_questions: bool
```

`app/routers/lessons.py`:
```python
from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.deps import get_ai, get_session, get_session_factory, get_settings, get_store
from app.models import Lesson, LessonPage
from app.schemas import LessonOut
from app.services.generation import generate_questions_for_lesson
from app.services.ingestion import run_ingestion, upload_path

router = APIRouter(prefix="/lessons", tags=["lessons"])
ALLOWED = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


def to_out(lesson: Lesson) -> LessonOut:
    return LessonOut(id=lesson.id, title=lesson.title, status=lesson.status,
                     error_message=lesson.error_message, page_count=lesson.page_count,
                     created_at=lesson.created_at, has_questions=bool(lesson.questions))


def _get_or_404(session: Session, lesson_id: int) -> Lesson:
    lesson = session.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, f"lesson {lesson_id} not found")
    return lesson


def _schedule(bg: BackgroundTasks, lesson_id, sf, ai, store, settings):
    bg.add_task(run_ingestion, lesson_id, session_factory=sf, ai=ai, store=store,
                upload_dir=settings.upload_dir,
                after_ingest=lambda s, l: generate_questions_for_lesson(s, l, ai))


@router.post("", status_code=202, response_model=LessonOut)
async def create_lesson(bg: BackgroundTasks, title: str = Form(...), files: list[UploadFile] = [],
                        session: Session = Depends(get_session), sf=Depends(get_session_factory),
                        ai=Depends(get_ai), store=Depends(get_store),
                        settings: Settings = Depends(get_settings)):
    if not title.strip():
        raise HTTPException(422, "title must not be blank")
    if not files:
        raise HTTPException(422, "at least one image is required")
    bad = [f.filename for f in files if f.content_type not in ALLOWED]
    if bad:
        raise HTTPException(422, f"unsupported file type for: {bad}; use PNG, JPEG or WebP")

    lesson = Lesson(title=title.strip(), status="processing", page_count=len(files))
    lesson.pages = [LessonPage(page_order=i) for i in range(len(files))]
    session.add(lesson)
    session.commit()
    for i, f in enumerate(files):
        path = upload_path(settings.upload_dir, lesson.id, i, ALLOWED[f.content_type])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(await f.read())
    _schedule(bg, lesson.id, sf, ai, store, settings)
    return to_out(lesson)


@router.get("", response_model=list[LessonOut])
def list_lessons(session: Session = Depends(get_session)):
    rows = session.scalars(select(Lesson).order_by(Lesson.created_at.desc(), Lesson.id.desc()))
    return [to_out(l) for l in rows]


@router.get("/{lesson_id}", response_model=LessonOut)
def get_lesson(lesson_id: int, session: Session = Depends(get_session)):
    return to_out(_get_or_404(session, lesson_id))


@router.post("/{lesson_id}/retry", status_code=202, response_model=LessonOut)
def retry_lesson(lesson_id: int, bg: BackgroundTasks, session: Session = Depends(get_session),
                 sf=Depends(get_session_factory), ai=Depends(get_ai), store=Depends(get_store),
                 settings: Settings = Depends(get_settings)):
    lesson = _get_or_404(session, lesson_id)
    if lesson.status != "failed":
        raise HTTPException(409, f"lesson is {lesson.status}; only failed lessons can be retried")
    lesson.status, lesson.error_message = "processing", None
    session.commit()
    _schedule(bg, lesson.id, sf, ai, store, settings)
    return to_out(lesson)
```
Include router in `main.py`: `app.include_router(lessons.router)`.

- [ ] **Step 4: Run — PASS. Step 5: Commit** `Add lessons API with background ingestion`.

---

### Task 8: Test-taking & attempts API

**Files:** Create `backend/app/services/attempts.py`, `backend/app/routers/tests.py`, `backend/app/routers/attempts.py`; Modify `backend/app/schemas.py`, `backend/app/main.py`; Test `backend/tests/routers/test_tests.py`, `backend/tests/routers/test_attempts.py`.

**Interfaces:**
- Consumes: `grade_mcq`, `grade_free_text`, `points`, deps from Task 7, `make_client` helper (move it from `test_lessons.py` into `tests/conftest.py` as a `make_client` fixture-factory so both test files share it).
- Produces (schemas.py):
  - `ChoiceOut(id, text)`; `McqQuestionOut(id, type, question_text, choices: list[ChoiceOut])`; `FreeTextQuestionOut(id, question_text)`
  - `McqSubmit(answers: dict[int, list[int]])` (question_id → selected choice ids); `FreeTextSubmit(answers: dict[int, str])`
  - `AnswerResultOut(question_id, question_text, question_type, student_response: list[int] | str, verdict, feedback_text, correct_answer_text)`
  - `AttemptOut(id, lesson_id, test_type, started_at, submitted_at, score: float, total_questions: int, results: list[AnswerResultOut])`; `AttemptSummaryOut` = same minus `results`.
- Endpoints: `GET /lessons/{id}/mcq-test`, `POST /lessons/{id}/mcq-test/submit`, `GET /lessons/{id}/free-text-test`, `POST /lessons/{id}/free-text-test/submit`, `GET /lessons/{id}/attempts`, `GET /attempts/{id}`.
- Rules: tests only available when lesson `ready` (409 otherwise); no questions of that kind → 409. Submit validation: answer keys must be exactly the set of test question IDs and every selected choice must belong to its question, else 422. Free-text blank answers are allowed (graded as incorrect by the LLM). MCQ `correct_answer_text` = correct choice texts joined by `"; "`, `feedback_text` = stored `explanation`. Free-text `correct_answer_text` = stored `reference_answer` verbatim, `feedback_text` = verdict feedback. If any grading call raises, **nothing is persisted** and the response is 502 with `detail` naming the failure.

- [ ] **Step 1: Failing tests** (`tests/routers/test_tests.py`; helper `ready_lesson(c, ...)` uploads one PNG with `FakeAI(page_texts=["word " * 2000])` so questions exist)

```python
def ready(make_client, session_factory, fake_store, tmp_path, ai=None):
    from tests.fakes import FakeAI
    ai = ai or FakeAI(page_texts=["word " * 2000])
    c = make_client(session_factory, ai, fake_store, tmp_path)
    lid = c.post("/lessons", data={"title": "T"}, files=[("files", ("p.png", b"x", "image/png"))]).json()["id"]
    return c, ai, lid


def test_mcq_test_hides_answers(make_client, session_factory, fake_store, tmp_path):
    c, _, lid = ready(make_client, session_factory, fake_store, tmp_path)
    qs = c.get(f"/lessons/{lid}/mcq-test").json()
    assert qs and all("is_correct" not in ch and "explanation" not in q
                      for q in qs for ch in q["choices"])


def test_mcq_submit_grades_and_persists(make_client, session_factory, fake_store, tmp_path):
    from app.models import McqChoice
    c, _, lid = ready(make_client, session_factory, fake_store, tmp_path)
    qs = c.get(f"/lessons/{lid}/mcq-test").json()
    with session_factory() as s:
        correct = {cid for (cid,) in s.query(McqChoice.id).filter(McqChoice.is_correct)}
    answers = {q["id"]: [ch["id"] for ch in q["choices"] if ch["id"] in correct] for q in qs}
    answers[qs[0]["id"]] = [qs[0]["choices"][1]["id"]]  # one wrong
    r = c.post(f"/lessons/{lid}/mcq-test/submit", json={"answers": answers}).json()
    assert r["total_questions"] == len(qs) and r["score"] == len(qs) - 1
    assert r["results"][0]["verdict"] == "incorrect" and r["results"][0]["correct_answer_text"] == "right"
    assert r["results"][0]["feedback_text"] == "because"
    assert c.get(f"/attempts/{r['id']}").json()["score"] == r["score"]
    assert len(c.get(f"/lessons/{lid}/attempts").json()) == 1


def test_mcq_submit_rejects_missing_or_foreign_choices(make_client, session_factory, fake_store, tmp_path):
    c, _, lid = ready(make_client, session_factory, fake_store, tmp_path)
    qs = c.get(f"/lessons/{lid}/mcq-test").json()
    assert c.post(f"/lessons/{lid}/mcq-test/submit", json={"answers": {}}).status_code == 422
    bad = {q["id"]: [999999] for q in qs}
    assert c.post(f"/lessons/{lid}/mcq-test/submit", json={"answers": bad}).status_code == 422


def test_free_text_flow_scores_partial_as_half(make_client, session_factory, fake_store, tmp_path):
    from app.schemas import FreeTextVerdict
    from tests.fakes import FakeAI
    ai = FakeAI(page_texts=["word " * 2000], verdicts={
        "a1": FreeTextVerdict(verdict="correct", feedback="good"),
        "a2": FreeTextVerdict(verdict="partially_correct", feedback="half")})
    c, _, lid = ready(make_client, session_factory, fake_store, tmp_path, ai)
    qs = c.get(f"/lessons/{lid}/free-text-test").json()
    assert all("reference_answer" not in q for q in qs)
    answers = {q["id"]: "zzz" for q in qs}
    answers[qs[0]["id"]], answers[qs[1]["id"]] = "a1", "a2"
    r = c.post(f"/lessons/{lid}/free-text-test/submit", json={"answers": answers}).json()
    assert r["score"] == 1.5
    assert r["results"][0]["correct_answer_text"] == "ref 0"


def test_free_text_grading_failure_persists_nothing(make_client, session_factory, fake_store, tmp_path):
    from tests.fakes import FakeAI
    ai = FakeAI(page_texts=["word " * 2000])
    c, _, lid = ready(make_client, session_factory, fake_store, tmp_path, ai)
    qs = c.get(f"/lessons/{lid}/free-text-test").json()
    ai.fail_grading = True
    r = c.post(f"/lessons/{lid}/free-text-test/submit", json={"answers": {q["id"]: "x" for q in qs}})
    assert r.status_code == 502
    assert c.get(f"/lessons/{lid}/attempts").json() == []


def test_tests_unavailable_until_ready(make_client, session_factory, fake_store, tmp_path):
    from tests.fakes import FakeAI
    c = make_client(session_factory, FakeAI(fail_on_page=0), fake_store, tmp_path)
    lid = c.post("/lessons", data={"title": "T"}, files=[("files", ("p.png", b"x", "image/png"))]).json()["id"]
    assert c.get(f"/lessons/{lid}/mcq-test").status_code == 409
```

- [ ] **Step 2: Run — FAIL. Step 3: Implement**

`app/services/attempts.py` — the service raises `HTTPException` subclasses? No: keep services HTTP-free; define `class SubmissionError(ValueError)` and `class GradingUnavailable(RuntimeError)`; routers map them to 422/502.

```python
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.clients.protocols import AIClient, VectorStore
from app.models import Attempt, AttemptAnswer, Lesson, Question
from app.services.grading import grade_free_text, grade_mcq, points


class SubmissionError(ValueError):
    pass


class GradingUnavailable(RuntimeError):
    pass


def questions_for(lesson: Lesson, kind: str) -> list[Question]:
    wanted = {"mcq_single", "mcq_multi"} if kind == "mcq" else {"free_text"}
    return [q for q in lesson.questions if q.type in wanted]


def _check_keys(questions: list[Question], answers: dict) -> None:
    expected = {q.id for q in questions}
    if set(answers) != expected:
        raise SubmissionError(f"answers must cover exactly question ids {sorted(expected)}")


def submit_mcq(session: Session, lesson: Lesson, answers: dict[int, list[int]]) -> Attempt:
    questions = questions_for(lesson, "mcq")
    _check_keys(questions, answers)
    attempt = Attempt(lesson_id=lesson.id, test_type="mcq", total_questions=len(questions))
    for q in questions:
        valid = {c.id for c in q.choices}
        selected = set(answers[q.id])
        if not selected <= valid:
            raise SubmissionError(f"choices {sorted(selected - valid)} do not belong to question {q.id}")
        correct = {c.id for c in q.choices if c.is_correct}
        verdict = grade_mcq(correct, selected)
        attempt.score += points(verdict)
        attempt.answers.append(AttemptAnswer(
            question_id=q.id, student_response=sorted(selected), verdict=verdict,
            feedback_text=q.explanation,
            correct_answer_text="; ".join(c.choice_text for c in q.choices if c.is_correct)))
    attempt.submitted_at = datetime.now(timezone.utc)
    session.add(attempt)
    session.commit()
    return attempt


def submit_free_text(session: Session, lesson: Lesson, answers: dict[int, str],
                     ai: AIClient, store: VectorStore) -> Attempt:
    questions = questions_for(lesson, "free_text")
    _check_keys(questions, answers)
    attempt = Attempt(lesson_id=lesson.id, test_type="free_text", total_questions=len(questions))
    for q in questions:
        try:
            v = grade_free_text(q, answers[q.id], ai, store)
        except Exception as e:
            raise GradingUnavailable(f"grading failed for question {q.id}: {type(e).__name__}: {e}") from e
        attempt.score += points(v.verdict)
        attempt.answers.append(AttemptAnswer(
            question_id=q.id, student_response=answers[q.id], verdict=v.verdict,
            feedback_text=v.feedback, correct_answer_text=q.reference_answer))
    attempt.submitted_at = datetime.now(timezone.utc)
    session.add(attempt)
    session.commit()
    return attempt
```
(Attempt is only added to the session after all grading succeeds, so a failure persists nothing. Initialise `score` default via `Attempt(..., score=0.0)` to avoid `None += float`.)

Routers: `tests.py` has the four endpoints (shared `_ready_lesson(session, lesson_id, kind)` helper → 404/409), builds `McqQuestionOut`/`FreeTextQuestionOut` explicitly (never serialise ORM objects directly, so `is_correct`/`explanation`/`reference_answer` cannot leak), maps `SubmissionError`→422, `GradingUnavailable`→502, returns `attempt_out(attempt)`. `attempts.py` has `GET /lessons/{id}/attempts` (newest first, summaries) and `GET /attempts/{id}` (404 if missing) using a shared `attempt_out` converter placed in `schemas.py`/`services/attempts.py`: `student_response` for MCQ is the stored id list, for free-text the stored string. Register both routers in `main.py`.

- [ ] **Step 4: Run all backend tests — PASS** (`uv run pytest -v`). **Step 5: Commit** `Add test-taking, grading and attempt-history endpoints`.

---

### Task 9: Real OpenAI + Qdrant adapters

**Files:** Create `backend/app/clients/openai_client.py`, `backend/app/clients/qdrant_store.py`; Test `backend/tests/clients/test_qdrant_store.py`, `backend/tests/clients/test_openai_client.py` (+ `__init__.py`).

**Interfaces:**
- Produces: `OpenAIClient(api_key: str, client: openai.OpenAI | None = None, chat_model: str = "gpt-5", embedding_model: str = "text-embedding-3-small")` implementing `AIClient`; `QdrantStore(url: str, api_key: str, client: QdrantClient | None = None, collection: str = "lesson_chunks", vector_size: int = 1536)` implementing `VectorStore`. Collection is created lazily on first upsert (`ensure_collection`) with a keyword payload index on `lesson_id`. Point IDs are deterministic: `uuid5(NAMESPACE_URL, f"{lesson_id}:{chunk_index}")`.

- [ ] **Step 1: Check current SDK APIs before writing** (the user's CLAUDE.md requires checking for an installed skill first; none covers OpenAI. Qdrant skill `qdrant:qdrant-clients-sdk` does — invoke it for `QdrantClient` usage; confirm the OpenAI structured-output call shape (`client.chat.completions.parse(..., response_format=PydanticModel)` → `.choices[0].message.parsed`) against the installed `openai` version with `uv run python -c "import openai; print(openai.__version__)"` and its docs.)

- [ ] **Step 2: Failing tests.** Qdrant: use `QdrantClient(":memory:")` injected into `QdrantStore` (a real in-process engine, not a mock): upsert two lessons' chunks with distinct vectors (use `vector_size=2`), assert `search(lesson_id=1, ...)` only returns lesson 1 texts ordered by similarity, and `delete_lesson(1)` removes only lesson 1. OpenAI: inject a tiny hand-written stub object exposing `.chat.completions.parse(...)` and `.embeddings.create(...)` and assert (a) `extract_page_text` sends an `image_url` content part with a `data:<mime>;base64,...` URL, (b) `embed` batches inputs in groups of ≤100 and preserves order, (c) `generate_questions` returns the parsed `GeneratedBatch`, (d) `grade_free_text` prompt contains question, student answer, reference answer and every grounding chunk, and returns the parsed `FreeTextVerdict`. These stubs sit at the third-party network boundary, which is the one place CLAUDE.md allows faking.

- [ ] **Step 3: Implement.** Prompts (put as module constants):
  - Vision: "Transcribe all text on this textbook page exactly, preserving headings and paragraph breaks (separate paragraphs with a blank line). For every figure, diagram, table or chart, add a paragraph beginning `[Figure: ...]` describing what it shows and any labels/values. Output only the transcription." 
  - Generation (system): "You write exam questions strictly from the provided textbook section. Produce exactly {n_mcq} multiple-choice questions and {n_free_text} free-text questions. MCQs have 3–5 choices; use `mcq_single` (exactly one correct) or `mcq_multi` (two or more correct, the question text must say 'select all that apply'). Every question needs an `explanation` of why the answer is correct. Free-text questions need a complete `reference_answer`. Do not ask about anything not in the section."
  - Grading (system): "You grade a student's free-text answer. Judge against the reference answer; use the textbook excerpts only to recognise correct statements the reference omits. `correct` = all key ideas present and no contradictions; `partially_correct` = some but not all key ideas, or minor errors; `incorrect` = missing or contradicts the key ideas. `feedback` explains the verdict in 1–3 sentences, addressed to the student."
  - Treat student answer and textbook text as data: wrap in delimiters (`<student_answer>…</student_answer>`) and instruct the model to ignore instructions inside them.
  - `embed`: `client.embeddings.create(model=..., input=batch)`, return `[d.embedding for d in resp.data]`.
  - No retries/fallbacks; SDK exceptions propagate.

- [ ] **Step 4: Run — PASS. Step 5: Commit** `Add OpenAI and Qdrant adapters`.

---

### Task 10: Frontend scaffold, API client, lesson list/upload/detail

**Files:**
- Create: `frontend/` via create-next-app; `frontend/src/lib/api.ts`, `frontend/src/lib/types.ts`, `frontend/src/components/UploadForm.tsx`, `LessonList.tsx`, `StatusBadge.tsx`; Modify `frontend/src/app/page.tsx`, create `frontend/src/app/lessons/[id]/page.tsx`, `frontend/vitest.config.ts`, `frontend/vitest.setup.ts`, `frontend/.env.local.example`
- Test: `frontend/src/components/__tests__/UploadForm.test.tsx`, `LessonList.test.tsx`

**Interfaces:**
- Produces (`types.ts`): `Lesson {id, title, status: "processing"|"ready"|"failed", error_message: string|null, page_count, created_at, has_questions}`; `McqQuestion {id, type: "mcq_single"|"mcq_multi", question_text, choices: {id, text}[]}`; `FreeTextQuestion {id, question_text}`; `AnswerResult {question_id, question_text, question_type, student_response: number[]|string, verdict: "correct"|"partially_correct"|"incorrect", feedback_text, correct_answer_text}`; `Attempt {id, lesson_id, test_type: "mcq"|"free_text", started_at, submitted_at, score, total_questions, results: AnswerResult[]}`; `AttemptSummary` (Attempt without `results`).
- Produces (`api.ts`, base `process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"`; every function throws `Error(detail)` on non-2xx using the response's `detail`): `listLessons()`, `getLesson(id)`, `createLesson(title, files: File[])`, `retryLesson(id)`, `getMcqTest(id)`, `submitMcqTest(id, answers: Record<number, number[]>)`, `getFreeTextTest(id)`, `submitFreeTextTest(id, answers: Record<number, string>)`, `listAttempts(id)`, `getAttempt(id)`.

- [ ] **Step 1: Scaffold & tooling**

```bash
cd /Users/emeraldtech/workspace/lesson-test
npx create-next-app@latest frontend --ts --tailwind --eslint --app --src-dir --import-alias "@/*" --use-npm --yes
cd frontend
npm i -D vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > .env.local.example
```
`vitest.config.ts`:
```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  test: { environment: "jsdom", setupFiles: ["./vitest.setup.ts"], globals: true },
});
```
`vitest.setup.ts`: `import "@testing-library/jest-dom/vitest";`. Add `"test": "vitest run"` to `package.json` scripts.
Before writing Next.js code, read `frontend/AGENTS.md`/`node_modules/next/dist/docs` if present — the scaffolded Next.js version may differ from memory (notably async `params` in dynamic routes).

- [ ] **Step 2: Failing tests**

`UploadForm.test.tsx`: renders title input + file input (`multiple`, `accept="image/*"`); submit disabled until title non-blank and ≥1 file chosen; on submit calls the injected `onSubmit(title, files)`; shows `error` prop text.
`LessonList.test.tsx`: renders each lesson title as a link to `/lessons/{id}` with its status badge; failed lessons show their `error_message`; empty list shows "No lessons yet".

```tsx
// UploadForm.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { UploadForm } from "../UploadForm";

test("enables submit only with title and files, then submits", async () => {
  const onSubmit = vi.fn();
  render(<UploadForm onSubmit={onSubmit} busy={false} error={null} />);
  const btn = screen.getByRole("button", { name: /upload/i });
  expect(btn).toBeDisabled();
  await userEvent.type(screen.getByLabelText(/title/i), "Chapter 1");
  await userEvent.upload(screen.getByLabelText(/pages/i), new File(["x"], "p1.png", { type: "image/png" }));
  expect(btn).toBeEnabled();
  await userEvent.click(btn);
  expect(onSubmit).toHaveBeenCalledWith("Chapter 1", [expect.any(File)]);
});

test("shows error", () => {
  render(<UploadForm onSubmit={vi.fn()} busy={false} error="bad file" />);
  expect(screen.getByText("bad file")).toBeInTheDocument();
});
```

- [ ] **Step 3: Implement** components (function components + hooks, Tailwind only) and pages:
  - `/` (client component): `useEffect` loads `listLessons()`, re-polls every 3 s while any lesson is `processing`; on upload calls `createLesson` then router-pushes to `/lessons/{id}`; error state shown via `UploadForm`.
  - `/lessons/[id]`: client component; polls `getLesson` every 2 s while `processing`; shows status; `failed` → error message + "Retry" button (`retryLesson`); `ready` → links "Take MCQ Test", "Take Free-Text Test", "View Past Attempts" (inline list of `listAttempts` with score `x / y` linking to `/lessons/{id}/attempts/{attemptId}`). Disable a test link when its question list would be empty is out of scope — API returns 409 and the test page shows the message.
  - Layout: `src/app/layout.tsx` title "Lesson Quiz", simple centered `max-w-3xl` container.

- [ ] **Step 4: Run — `npm test` PASS; `npm run build` succeeds. Step 5: Commit** `Add frontend scaffold with lesson list, upload and detail`.

---

### Task 11: MCQ test page + results

**Files:** Create `frontend/src/components/McqTestForm.tsx`, `ResultsView.tsx`, `frontend/src/app/lessons/[id]/mcq-test/page.tsx`; Test `frontend/src/components/__tests__/McqTestForm.test.tsx`, `ResultsView.test.tsx`.

**Interfaces:**
- Consumes: types/api from Task 10.
- Produces: `McqTestForm({questions: McqQuestion[], onSubmit: (answers: Record<number, number[]>) => void, busy: boolean})` — radio inputs for `mcq_single`, checkboxes for `mcq_multi`; submit disabled until every question has ≥1 selection; `ResultsView({attempt: Attempt})` — header `Score: {score} / {total_questions}`, per-result card with correct/partially/incorrect badge (`data-testid="verdict-{question_id}"`), question text, student response (choice texts are not in `AnswerResult`, so for MCQ show only verdict + `correct_answer_text` + `feedback_text`; for free-text also show the student's text), "Correct answer:" and "Explanation:"/"Feedback:" blocks. Reused by Task 12 and 13.

- [ ] **Step 1: Failing tests**

```tsx
test("radio for single, checkbox for multi; submit gated and sends selections", async () => {
  const qs = [
    { id: 1, type: "mcq_single", question_text: "Q1", choices: [{ id: 10, text: "A" }, { id: 11, text: "B" }] },
    { id: 2, type: "mcq_multi", question_text: "Q2", choices: [{ id: 20, text: "C" }, { id: 21, text: "D" }] },
  ] as const;
  const onSubmit = vi.fn();
  render(<McqTestForm questions={[...qs]} onSubmit={onSubmit} busy={false} />);
  expect(screen.getAllByRole("radio")).toHaveLength(2);
  expect(screen.getAllByRole("checkbox")).toHaveLength(2);
  const submit = screen.getByRole("button", { name: /submit/i });
  expect(submit).toBeDisabled();
  await userEvent.click(screen.getByLabelText("B"));
  await userEvent.click(screen.getByLabelText("C"));
  await userEvent.click(screen.getByLabelText("D"));
  await userEvent.click(submit);
  expect(onSubmit).toHaveBeenCalledWith({ 1: [11], 2: [20, 21] });
});
```
`ResultsView` test: renders score line `Score: 1.5 / 2`, badge texts "Correct" / "Partially correct" / "Incorrect", and the correct answer + feedback strings.

- [ ] **Step 2: Run — FAIL. Step 3: Implement.** The page: loads `getMcqTest(id)` (error → show message e.g. 409 text), on submit `submitMcqTest` then renders `<ResultsView>` in place plus links back to the lesson and "Retake". Radio inputs share `name={`q-${id}`}`; labels wrap inputs so `getByLabelText` works.
- [ ] **Step 4: `npm test` PASS. Step 5: Commit** `Add MCQ test page and results view`.

---

### Task 12: Free-text test page

**Files:** Create `frontend/src/components/FreeTextTestForm.tsx`, `frontend/src/app/lessons/[id]/free-text-test/page.tsx`; Test `frontend/src/components/__tests__/FreeTextTestForm.test.tsx`.

**Interfaces:**
- Produces: `FreeTextTestForm({questions: FreeTextQuestion[], onSubmit: (answers: Record<number, string>) => void, busy: boolean})` — one `<textarea>` per question labelled by question text; submit enabled once every box has non-whitespace text (blank answers are API-legal but pointless; gating is a UX choice); `busy` shows "Grading…" and disables the button.
- Consumes: `ResultsView` (Task 11) — free-text results show the student's answer, verdict badge, feedback, correct answer.

- [ ] **Step 1: Failing test:** typing in two textareas then clicking Submit calls `onSubmit({1: "foo", 2: "bar"})`; button disabled until both filled; while `busy` the button text is "Grading…".
- [ ] **Step 2–4:** Implement form and page (page: load `getFreeTextTest`, submit with `busy` true during the (slow, per-question LLM) request, show backend error text on 502 with the form preserved so the student's answers aren't lost, then `ResultsView` on success). Run `npm test` — PASS.
- [ ] **Step 5: Commit** `Add free-text test page`.

---

### Task 13: Past attempt replay page

**Files:** Create `frontend/src/app/lessons/[id]/attempts/[attemptId]/page.tsx`; Test `frontend/src/app/lessons/[id]/attempts/[attemptId]/__tests__/page.test.tsx` (or extract `AttemptReplay` component to `components/AttemptReplay.tsx` with a test — preferred, keeps tests off route files).

**Interfaces:**
- Consumes: `getAttempt`, `ResultsView`. Produces: `AttemptReplay({attemptId: number})` — loads attempt, shows test type + submitted date, then `ResultsView`; error state on failure.

- [ ] **Step 1: Failing test:** mock `@/lib/api` module's `getAttempt` (our own network boundary wrapper — acceptable to stub since it is the HTTP edge) to resolve a free-text attempt; assert the score line, student answer text and feedback render; and that a rejected promise renders the error message.
- [ ] **Step 2–4:** Implement; `npm test` PASS; `npm run build` succeeds.
- [ ] **Step 5: Commit** `Add past attempt replay page`.

---

### Task 14: End-to-end smoke run & docs

**Files:** Create `README.md`; Modify `backend/.env.example` if needed.

- [ ] **Step 1: Write `README.md`**: prerequisites (uv, Node, a Qdrant instance — local `docker run -p 6333:6333 qdrant/qdrant` with `QDRANT_URL=http://localhost:6333` and blank key, or Qdrant Cloud — and an OpenAI key), setup (`cd backend && cp .env.example .env && uv sync`), run commands (`uv run uvicorn app.main:app --reload`; `cd frontend && cp .env.local.example .env.local && npm run dev`), test commands (`uv run pytest`; `npm test`).
- [ ] **Step 2: Full verification** — `cd backend && uv run pytest -v` and `cd frontend && npm test && npm run build`; all must pass with none skipped.
- [ ] **Step 3: Manual smoke test (requires real keys — ask the user to supply them; do not proceed with fakes and claim it works):** start Qdrant + both servers, upload 2–3 real textbook page photos, confirm status goes `processing`→`ready`, take both tests, submit, verify results and that attempts appear in history; also upload a non-image to confirm the 422 message surfaces. Use the `run` skill for launching/driving the app.
- [ ] **Step 4: Commit** `Add README with setup and run instructions`.

---

## Self-Review

**Spec coverage:** §1 purpose → Tasks 4–8; §2 architecture → Tasks 1, 2, 9; §3 data model → Task 1 (Qdrant payload Task 9); §4 ingestion → Tasks 3, 4, 7 (polling Task 10); §5 generation → Task 5; §6 flows/grading/scoring/history → Tasks 6, 8, 11–13; §7 API → Tasks 7, 8 (+`/retry`, justified by §10); §8 frontend → Tasks 10–13; §9 config → Tasks 1, 7; §10 errors → Tasks 4, 7, 8 (+UI retry in Task 10); §11 testing → every task; §12 non-goals respected.

**Known deviations/risks to confirm with the user:** (1) retry requires keeping uploads on failure — see Plan decisions; (2) free-text submit is synchronous with one LLM call per question (a 100-question test will be slow; spec accepts this, UI shows "Grading…"); (3) GPT-5 model ID and structured-output call shape must be verified against the installed `openai` SDK in Task 9.

**Type consistency:** `ChunkRecord`, `AIClient`, `VectorStore`, `GeneratedBatch`, `FreeTextVerdict`, `run_ingestion(... after_ingest)`, `generate_questions_for_lesson(session, lesson, ai)`, `grade_mcq/grade_free_text/points`, `submit_mcq/submit_free_text`, `LessonOut`/`AttemptOut` field names match between backend tasks and the frontend `types.ts`.
