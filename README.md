# Lesson Quiz

Upload photos of textbook pages and get tests generated from them. A vision model extracts the text, the text is chunked and embedded into Qdrant, and the app generates multiple-choice and free-text questions. You take a test, answers are graded (free-text by an LLM), and every attempt is stored so you can replay it later.

Backend: FastAPI + SQLite + Qdrant + OpenAI (`backend/`). Frontend: Next.js + React + Tailwind (`frontend/`). Diagrams of the full flow are in [docs/architecture.md](docs/architecture.md).

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (installs Python 3.13 as needed)
- Node 20+
- A Qdrant instance: locally with `docker run -p 6333:6333 qdrant/qdrant` (use `QDRANT_URL=http://localhost:6333` and a blank `QDRANT_API_KEY`), or Qdrant Cloud
- An OpenAI API key

## Setup

```bash
cd backend
cp .env.example .env   # then fill in the values below
uv sync
```

`backend/.env` variables:

| Variable | Notes |
| --- | --- |
| `OPENAI_API_KEY` | Required. If blank, requests that need it fail with a 503 naming the setting |
| `QDRANT_URL` | Required, e.g. `http://localhost:6333`. If blank, requests that need it fail with a 503 naming the setting |
| `QDRANT_API_KEY` | Blank for local Qdrant |
| `DATABASE_URL` | Optional, default `sqlite:///data/app.db` |
| `UPLOAD_DIR` | Optional, default `data/uploads` |
| `CORS_ORIGINS` | Optional, must be a JSON list, e.g. `["http://localhost:3000"]` (default) |

## Run

Backend (http://localhost:8000):

```bash
cd backend
uv run uvicorn app.main:app --reload
```

Frontend (http://localhost:3000):

```bash
cd frontend
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev
```

## Test

```bash
cd backend && uv run pytest
cd frontend && npm test
```

## How it works

1. Upload page photos for a lesson.
2. A vision model extracts the text from each page.
3. The text is chunked and embedded into Qdrant.
4. Multiple-choice and free-text questions are generated from the chunks.
5. You take a test; answers are graded and the attempt is stored in SQLite. MCQs are shown one at a time: submitting an answer gives instant feedback (right or wrong, the correct answer and the reasoning) before the next question, and the finished test is saved as one attempt. Free-text tests are answered all at once.
6. From the lesson page you can generate more MCQ or free-text questions (1–20 at a time) at any point.

`POST /lessons/{id}/mcq-test/check` with `{"question_id", "selected": [choice ids]}` grades one MCQ answer and returns the verdict, the correct choice ids, the correct answer text and the explanation. It stores nothing; the attempt is saved when the whole test is submitted.

### Generating more questions

`POST /lessons/{id}/questions` with `{"kind": "mcq" | "free_text", "count": 1-20}` appends questions to a `ready` lesson and returns `{"added", "total"}`.

- Existing questions are kept, so past attempts still replay correctly. Open a test page again to see the new questions.
- Sections of the lesson are picked at random, weighted by length, so repeated requests spread across the whole lesson.
- Duplicates are filtered in code: each new question is compared with the lesson's existing questions of that kind and with the other new ones, ignoring case and punctuation, and dropped if it is identical or at least 85% similar. Up to two extra rounds replace dropped questions, so you can still get fewer than requested. If every question is a duplicate, or generation fails, the request returns a 502 and stores nothing.
- The check is wording-based; it does not catch the same fact asked in very different words.

## Known limits

- Single user, no authentication.
- Free-text grading is one LLM call per question, run inside the request with up to 8 questions graded at a time, so large tests can still take a while to submit.
- Uploaded images are kept on disk only until ingestion succeeds; they are retained on failure so Retry works.
- Ingestion runs inside the API process: on startup, any lesson still `processing` (for example after a `--reload` restart mid-ingestion) is marked `failed` with "Interrupted by a server restart; use Retry." Its uploads are kept, so Retry works. Run a single API process.
- A lesson whose pages yield no text fails with a clear error.
- Generating more questions waits for the model inside the request, so large batches take a while. Two simultaneous requests for the same lesson do not see each other's new questions and could add similar ones.
