# Lesson Quiz App — Design Spec

Date: 2026-11-14
Status: Approved for implementation planning

## 1. Purpose

A single-user application that:

1. Ingests photos of textbook lesson/chapter pages (one or many images per lesson).
2. Extracts the lesson content from those images using a vision-capable LLM.
3. Generates two kinds of assessments from that content:
   - Multiple-choice questions (single- and multi-select).
   - Free-text (write-your-own-answer) questions.
4. Lets the student take either test, grades their submission, and gives feedback:
   - MCQ: correct/incorrect per question, the correct choice(s), and reasoning.
   - Free-text: a three-way verdict (correct / partially correct / incorrect), reasoning, and the correct answer.
5. Persists lesson content, generated questions, and test attempt history.

Single user, no authentication. A "lesson" may be as small as one page or as large as a full book chapter (many page images uploaded together).

## 2. High-Level Architecture

```
Frontend (Next.js/React/Tailwind)
  - Upload lesson images
  - Browse lessons
  - Take MCQ test / free-text test
  - View past attempts
        │ REST (JSON)
        ▼
Backend (FastAPI, Python, uv-managed)
  - Ingestion service: image(s) -> GPT-5 vision -> page text -> chunk -> embed -> upsert Qdrant
  - Question-generation service: walk lesson in sections -> LLM structured output -> MCQs + free-text questions
  - Test service: serve questions, grade MCQ deterministically, grade free-text via LLM+RAG judge
  - SQLite: lessons, pages, questions, choices, attempts, attempt_answers
        │                           │
        ▼                           ▼
     Qdrant                     OpenAI API
  (lesson_chunks           (vision extraction,
   collection, payload      embeddings, structured
   multi-tenant by           generation, free-text
   lesson_id)                 grading)
```

The backend is the only component that talks to OpenAI or Qdrant. The frontend never sees API keys.

SQLite is the source of truth for structured/relational data queried by ID (lessons, questions, attempts). Qdrant holds only the semantic layer — chunked lesson text and embeddings — used for retrieval during question generation and free-text grading.

## 3. Data Model

### SQLite schema

- **lessons**: `id`, `title`, `status` (`processing` / `ready` / `failed`), `error_message` (nullable), `page_count`, `created_at`
- **lesson_pages**: `id`, `lesson_id` (FK), `page_order` (int), `extracted_text` (raw GPT-vision output for that page)

Uploaded image files are processed during ingestion and then discarded — only `extracted_text` is retained. Nothing downstream (question generation, grading) needs the original images, so there is no image storage/blob layer.
- **questions**: `id`, `lesson_id` (FK), `type` (`mcq_single` / `mcq_multi` / `free_text`), `question_text`, `explanation` (reasoning for the correct answer, written at generation time), `reference_answer` (free-text only), `created_at`
- **mcq_choices**: `id`, `question_id` (FK), `choice_text`, `is_correct` (bool), `order_index`
- **attempts**: `id`, `lesson_id` (FK), `test_type` (`mcq` / `free_text`), `started_at`, `submitted_at`, `score`, `total_questions`
- **attempt_answers**: `id`, `attempt_id` (FK), `question_id` (FK), `student_response` (JSON — selected choice IDs for MCQ, raw text for free-text), `verdict` (`correct` / `partially_correct` / `incorrect` for free-text; `correct` / `incorrect` for MCQ), `feedback_text`, `correct_answer_text`

### Qdrant

One collection, `lesson_chunks`, multi-tenant via payload field (not one collection per lesson). Payload: `lesson_id`, `page_order`, `chunk_index`, `text`. Embeddings via OpenAI `text-embedding-3-small`.

## 4. Ingestion Pipeline

Triggered when a lesson's images are uploaded.

1. Create `lessons` row with `status=processing`; store each page with its `page_order`.
2. Background task (FastAPI `BackgroundTasks` — no queue/worker infrastructure needed at this scale) sends each page image to a GPT-5 vision call, extracting transcribed text plus descriptions of any figures/diagrams. Saved per-page in `lesson_pages`.
3. Concatenate ordered page texts, chunk (~500–800 tokens, slight overlap, boundaries respecting paragraph breaks), batch-embed, upsert into Qdrant.
4. Mark lesson `ready`, or `failed` with `error_message` set on any exception (vision call failure, unreadable image, etc.) — never silently swallowed.
5. Frontend polls `GET /lessons/{id}` to reflect processing/ready/failed state, since a full-chapter upload (dozens of pages) will not complete within a single request/response cycle.

## 5. Question-Generation Pipeline

Chained automatically once ingestion reaches `ready` — no manual review/edit step before questions become test-ready.

1. Question count scales with content length: roughly 1 MCQ per ~150–200 words and 1 free-text question per ~300–400 words of extracted lesson text, clamped to [5, 100] per type. This is a tunable heuristic/constant, not a fixed requirement.
2. To ensure coverage of a full chapter rather than whatever a single top-k retrieval happens to surface, generation walks the lesson in sequential sections (grouped chunks in page order) and generates a batch of questions per section — questions spread across the whole lesson, not just its most "retrievable" parts.
3. One structured-output LLM call per section returns questions with: text, type, MCQ choices with `is_correct` flags, an `explanation` (the reasoning), and for free-text questions, a `reference_answer`.
4. Persist questions/choices to SQLite.

Writing the explanation/reference answer once, at generation time, is what allows MCQ grading to be fully deterministic and free-text grading to check against a fixed reference instead of improvising one per submission.

## 6. Test-Taking Flows & Grading

### MCQ test

1. `GET /lessons/{id}/mcq-test` returns questions (text, type, choices) without `is_correct` or `explanation`.
2. Student answers (radio for `mcq_single`, checkboxes for `mcq_multi`) and submits the whole test at once.
3. `POST /lessons/{id}/mcq-test/submit` with `{question_id: [selected_choice_ids]}` for all questions.
4. Backend grades deterministically: correct iff the selected set exactly equals the `is_correct` set for that question. No LLM call at grading time.
5. Response per question: `verdict` (correct/incorrect), the correct choice(s), and the stored `explanation`. Attempt and per-question results persisted.

### Free-text test

1. `GET /lessons/{id}/free-text-test` returns question text only (no reference answer).
2. Student types an answer per question and submits the whole test at once.
3. `POST /lessons/{id}/free-text-test/submit` with `{question_id: answer_text}` for all questions.
4. For each answer: embed the question (+ student answer), retrieve top-k chunks for that `lesson_id` from Qdrant as grounding, then one LLM call with `{question, student_answer, reference_answer, grounding_chunks}` returning a structured verdict: `correct` / `partially_correct` / `incorrect`, `feedback` (reasoning), and `correct_answer` (the stored `reference_answer`, surfaced verbatim).
5. Persist attempt and answers in the same shape as MCQ.

MCQ grading is pure DB/Python logic — fast, free, deterministic. Free-text grading makes one LLM call per question per submission, which is unavoidable since it is a semantic judgment.

**Scoring:** `attempts.score` counts `correct` = 1 point, `partially_correct` = 0.5 points, `incorrect` = 0 points for free-text tests; MCQ tests count `correct` = 1, `incorrect` = 0.

### Attempt history

- `GET /lessons/{id}/attempts` — list past attempts for a lesson.
- `GET /attempts/{id}` — full detail of one past attempt (questions, student answers, verdicts, feedback) for review.

## 7. API Surface

- `POST /lessons` — create lesson (title + images), kicks off ingestion
- `GET /lessons` — list lessons with status
- `GET /lessons/{id}` — lesson detail/status (for polling during processing)
- `GET /lessons/{id}/mcq-test`, `POST /lessons/{id}/mcq-test/submit`
- `GET /lessons/{id}/free-text-test`, `POST /lessons/{id}/free-text-test/submit`
- `GET /lessons/{id}/attempts`
- `GET /attempts/{id}`

## 8. Frontend Structure (Next.js App Router)

- `/` — lesson list + "upload new lesson" (multi-image picker + title field)
- `/lessons/[id]` — lesson detail: status, and once ready, "Take MCQ Test" / "Take Free-Text Test" / "View Past Attempts"
- `/lessons/[id]/mcq-test` — form with radio/checkbox per question → submit → results view (per-question correct/incorrect + explanation)
- `/lessons/[id]/free-text-test` — textbox per question → submit → results view (per-question verdict badge + feedback + correct answer)
- `/lessons/[id]/attempts/[attemptId]` — read-only replay of a past attempt

## 9. Configuration & Secrets

`OPENAI_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY` live in a backend-only `.env` file (gitignored), loaded via Pydantic Settings. The frontend never receives these values; all OpenAI/Qdrant calls are proxied through the FastAPI backend.

## 10. Error Handling

- Ingestion failures (vision call error, unreadable image) mark the lesson `failed` with a stored, user-visible `error_message` and a retry affordance in the UI — never silently swallowed.
- Grading-call failures (e.g., OpenAI unavailable mid-submission) fail that submission with a clear error rather than storing a fabricated verdict.
- Validate only at system boundaries (image upload contents, API request bodies); trust internal data once persisted.

## 11. Testing Strategy

- Backend: `pytest`, mirroring source layout under `tests/`. MCQ grading is a pure function and gets direct unit tests with no mocking. Ingestion, question generation, and free-text grading are tested against thin fake OpenAI/Qdrant client wrappers rather than live APIs.
- Frontend: Vitest + React Testing Library for the test-taking forms and results views.

## 12. Explicit Non-Goals (YAGNI)

- No multi-user accounts, auth, or roles.
- No question review/edit UI before a test goes live.
- No background job queue/worker (Celery, etc.) — FastAPI `BackgroundTasks` is sufficient at single-user scale.
- No per-lesson Qdrant collections — a single multi-tenant collection is sufficient at this scale.
