import { Suspense } from "react";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import FreeTextTestPage from "./page";

function json(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status }));
}

async function renderPage() {
  const params = Promise.resolve({ id: "7" });
  await act(async () => {
    render(
      <Suspense fallback="loading">
        <FreeTextTestPage params={params as never} searchParams={Promise.resolve({}) as never} />
      </Suspense>,
    );
  });
  await screen.findByLabelText("Q1");
}

afterEach(() => vi.unstubAllGlobals());

test("a failed grading request shows the error and keeps typed answers", async () => {
  const fetchMock = vi.fn((_url: string, init?: RequestInit) =>
    init?.method === "POST"
      ? json({ detail: "Grader unavailable" }, 502)
      : json([{ id: 1, question_text: "Q1" }, { id: 2, question_text: "Q2" }]),
  );
  vi.stubGlobal("fetch", fetchMock);
  await renderPage();
  await userEvent.type(screen.getByLabelText("Q1"), "my first");
  await userEvent.type(screen.getByLabelText("Q2"), "my second");
  await userEvent.click(screen.getByRole("button", { name: /submit/i }));
  expect(await screen.findByText("Grader unavailable")).toBeInTheDocument();
  expect(screen.getByLabelText("Q1")).toHaveValue("my first");
  expect(screen.getByLabelText("Q2")).toHaveValue("my second");
  expect(screen.getByRole("button", { name: /submit/i })).toBeEnabled();
});

test("successful submit shows results with Retake and lesson links", async () => {
  const attempt = {
    id: 1,
    lesson_id: 7,
    test_type: "free_text",
    started_at: "2026-01-01T00:00:00",
    submitted_at: "2026-01-01T00:01:00",
    score: 1,
    total_questions: 1,
    results: [
      {
        question_id: 1,
        question_text: "Q1",
        question_type: "free_text",
        student_response: "x",
        student_response_text: "x",
        verdict: "correct",
        feedback_text: "Nice",
        correct_answer_text: "x",
      },
    ],
  };
  vi.stubGlobal(
    "fetch",
    vi.fn((_url: string, init?: RequestInit) =>
      init?.method === "POST" ? json(attempt) : json([{ id: 1, question_text: "Q1" }]),
    ),
  );
  await renderPage();
  await userEvent.type(screen.getByLabelText("Q1"), "x");
  await userEvent.click(screen.getByRole("button", { name: /submit/i }));
  expect(await screen.findByRole("button", { name: "Retake" })).toBeInTheDocument();
  expect(screen.getByText("Nice")).toBeInTheDocument();
  expect(screen.getAllByRole("link", { name: "Back to lesson" }).length).toBeGreaterThan(0);
});
