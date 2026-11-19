# Architecture

The browser only ever talks to the FastAPI backend. The backend owns every secret and every call to OpenAI and Qdrant, and reaches them through the `AIClient` and `VectorStore` protocols, which tests replace with fakes.

## System

```mermaid
flowchart LR
    Browser["Browser<br/>Next.js · React · Tailwind"] <-->|"REST / JSON"| Routers

    subgraph API["FastAPI backend"]
        direction TB
        Routers["Routers<br/>lessons · tests · attempts"] --> Services["Services<br/>ingestion · generation<br/>grading · attempts"]
        Services --> Clients["Clients<br/>AIClient · VectorStore"]
    end

    Services <-->|"lessons, pages,<br/>questions, attempts"| SQLite[("SQLite<br/>source of truth")]
    Services -.->|"kept until ingestion succeeds"| Uploads["Uploads on disk"]
    Clients <-->|"chunk vectors,<br/>top-k search"| Qdrant[("Qdrant<br/>lesson_chunks")]
    Clients -->|"vision, embeddings,<br/>questions, grading"| OpenAI["OpenAI"]
```

`OPENAI_API_KEY`, `QDRANT_URL` and `QDRANT_API_KEY` live in `backend/.env`; the browser never receives them. Qdrant keeps every lesson in one collection, separated by a `lesson_id` payload field.

## Ingestion

An upload returns `202` at once. Steps 2–6 run as a FastAPI background task, and the page polls `GET /lessons/{id}` every 2 seconds until the status changes.

```mermaid
flowchart LR
    U["1 · Upload<br/>POST /lessons<br/>images saved to disk<br/>lesson: processing"] --> V["2 · Read pages<br/>vision model reads each<br/>page: text + figure notes"]
    V --> T["3 · Save text<br/>page text committed<br/>no DB write lock held<br/>during LLM calls"]
    T --> I["4 · Index<br/>chunk ~500–800 tokens<br/>embed, upsert to Qdrant<br/>keyed by lesson_id"]
    I --> G["5 · Generate<br/>questions per section<br/>structured LLM output<br/>checked before saving"]
    G --> R["6 · Ready<br/>one short transaction:<br/>store questions<br/>lesson: ready"]

    V -.->|error| F
    T -.->|error| F
    I -.->|error| F
    G -.->|error| F
    F["Failed<br/>error message shown in the UI<br/>partial vectors cleared<br/>uploads kept"] -.->|"Retry reruns from step 2"| V
```

Lessons still `processing` when the server starts are failed the same way, so Retry works after a restart.

## Taking tests

MCQs are graded by a rule, free-text answers by an LLM judge.

```mermaid
flowchart LR
    subgraph MCQ["MCQ test · graded in code, no LLM"]
        direction LR
        M1["Submit<br/>all answers at once"] --> M2["Grade<br/>selected set must equal<br/>the correct set"] --> M3["Score<br/>correct 1 · wrong 0"] --> M4[("Save attempt<br/>answers, verdicts,<br/>explanations")] --> M5["Results<br/>correct choices and<br/>the stored reasoning"]
    end

    subgraph FT["Free-text test · graded by an LLM against the stored reference answer"]
        direction LR
        F1["Submit<br/>one text per question"] --> F2["Retrieve context<br/>embed question + answer<br/>top-k chunks from Qdrant"] --> F3["Judge, 8 at a time<br/>LLM sees answer,<br/>reference and chunks"] --> F4[("Score + save<br/>correct 1 · partial 0.5<br/>wrong 0")] --> F5["Results<br/>verdict, feedback and<br/>the reference answer"]
        F3 -.->|"any grading error"| FE["502, nothing saved"]
    end
```

## Generating more questions

`POST /lessons/{id}/questions` with `{"kind": "mcq" | "free_text", "count": 1-20}` adds questions of one kind to a `ready` lesson.

```mermaid
flowchart LR
    A["Request<br/>kind, count 1–20"] --> B["Pick sections<br/>random, weighted by<br/>section length"]
    B --> C["Generate<br/>LLM is shown the<br/>questions that exist"]
    C --> D["Drop duplicates<br/>normalised text, drop if<br/>85% similar or more"]
    D -->|"some dropped, up to 2 more rounds"| B
    D --> E[("Append<br/>new questions added<br/>old ones and attempts kept")]
    C -.->|"generation error, or every question a duplicate"| X["502, nothing stored"]
```

The duplicate check compares wording, not meaning, so the same fact asked in very different words can still get through.
