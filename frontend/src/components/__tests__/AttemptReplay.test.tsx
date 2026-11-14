import { render, screen } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { AttemptReplay } from "../AttemptReplay";
import type { Attempt } from "@/lib/types";

const base = {
  id: 5,
  lesson_id: 1,
  started_at: "2026-01-01T00:00:00Z",
  submitted_at: "2026-01-02T12:00:00Z",
};

function stubFetch(res: { ok: boolean; status?: number; body: unknown }) {
  const fn = vi.fn().mockResolvedValue({
    ok: res.ok,
    status: res.status ?? 200,
    json: async () => res.body,
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => vi.unstubAllGlobals());

test("free-text attempt shows type, score, student answer and feedback", async () => {
  const attempt: Attempt = {
    ...base,
    test_type: "free_text",
    score: 1,
    total_questions: 2,
    results: [
      { question_id: 7, question_text: "Explain X", question_type: "free_text", student_response: "my own words", student_response_text: "my own words", verdict: "correct", feedback_text: "Well done", correct_answer_text: "Reference" },
    ],
  };
  const fetchMock = stubFetch({ ok: true, body: attempt });
  render(<AttemptReplay attemptId={5} />);
  expect(await screen.findByText("Score: 1 / 2")).toBeInTheDocument();
  expect(screen.getByText("Free-text test")).toBeInTheDocument();
  expect(screen.getByText("my own words")).toBeInTheDocument();
  expect(screen.getByText("Well done")).toBeInTheDocument();
  expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/attempts\/5$/);
});

test("failed load shows the error message", async () => {
  stubFetch({ ok: false, status: 404, body: { detail: "Attempt not found" } });
  render(<AttemptReplay attemptId={5} />);
  expect(await screen.findByText("Attempt not found")).toBeInTheDocument();
  expect(screen.queryByText(/^Score:/)).not.toBeInTheDocument();
});

test.each([NaN, 0, -3, 1.5])("invalid id %s shows message and skips the API", (bad) => {
  const fetchMock = stubFetch({ ok: true, body: {} });
  render(<AttemptReplay attemptId={bad} />);
  expect(screen.getByText("Invalid attempt id")).toBeInTheDocument();
  expect(fetchMock).not.toHaveBeenCalled();
});

test("MCQ attempt shows correct answer text and explanation, not raw choice ids", async () => {
  const attempt: Attempt = {
    ...base,
    test_type: "mcq",
    score: 0,
    total_questions: 1,
    results: [
      { question_id: 3, question_text: "Pick one", question_type: "mcq_single", student_response: [4242], student_response_text: "Option A", verdict: "incorrect", feedback_text: "Because reasons", correct_answer_text: "Option B" },
    ],
  };
  stubFetch({ ok: true, body: attempt });
  const { container } = render(<AttemptReplay attemptId={5} />);
  expect(await screen.findByText("MCQ test")).toBeInTheDocument();
  expect(screen.getByText("Your answer:")).toBeInTheDocument();
  expect(screen.getByText("Option A")).toBeInTheDocument();
  expect(screen.getByText("Option B")).toBeInTheDocument();
  expect(screen.getByText("Because reasons")).toBeInTheDocument();
  expect(container.textContent).not.toContain("4242");
});
