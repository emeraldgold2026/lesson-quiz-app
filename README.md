# Lesson Quiz

Upload photos of textbook pages and get tests generated from them. A vision model extracts the text, the text is chunked and embedded into Qdrant, and the app generates multiple-choice and free-text questions. You take a test, answers are graded (free-text by an LLM), and every attempt is stored so you can replay it later.

Backend: FastAPI + SQLite + Qdrant + OpenAI (`backend/`). Frontend: Next.js + React + Tailwind (`frontend/`).

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
| `OPENAI_API_KEY` | Required |
| `QDRANT_URL` | Required, e.g. `http://localhost:6333` |
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
5. You take a test; answers are graded and the attempt is stored in SQLite.

## Known limits

- Single user, no authentication.
- Free-text grading is one LLM call per question and runs inside the request, so large tests are slow to submit.
- Uploaded images are kept on disk only until ingestion succeeds; they are retained on failure so Retry works.
- Ingestion runs inside the API process: on startup, any lesson still `processing` (for example after a `--reload` restart mid-ingestion) is marked `failed` with "Interrupted by a server restart; use Retry." Its uploads are kept, so Retry works. Run a single API process.
- A lesson whose pages yield no text fails with a clear error.
