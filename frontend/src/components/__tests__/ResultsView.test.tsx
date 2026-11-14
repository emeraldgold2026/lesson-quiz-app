import { render, screen } from "@testing-library/react";
import { ResultsView } from "../ResultsView";
import type { Attempt } from "@/lib/types";

const base = {
  id: 1,
  lesson_id: 1,
  started_at: "2026-01-01T00:00:00Z",
  submitted_at: "2026-01-01T00:05:00Z",
};

test("MCQ: score line, verdict badges, correct answer and explanation", () => {
  const attempt: Attempt = {
    ...base,
    test_type: "mcq",
    score: 1.5,
    total_questions: 3,
    results: [
      { question_id: 1, question_text: "Q1", question_type: "mcq_single", student_response: [10], verdict: "correct", feedback_text: "Because one", correct_answer_text: "Answer one" },
      { question_id: 2, question_text: "Q2", question_type: "mcq_multi", student_response: [20], verdict: "partially_correct", feedback_text: "Because two", correct_answer_text: "Answer two" },
      { question_id: 3, question_text: "Q3", question_type: "mcq_single", student_response: [30], verdict: "incorrect", feedback_text: "Because three", correct_answer_text: "Answer three" },
    ],
  };
  render(<ResultsView attempt={attempt} />);
  expect(screen.getByText("Score: 1.5 / 3")).toBeInTheDocument();
  expect(screen.getByTestId("verdict-1")).toHaveTextContent("Correct");
  expect(screen.getByTestId("verdict-2")).toHaveTextContent("Partially correct");
  expect(screen.getByTestId("verdict-3")).toHaveTextContent("Incorrect");
  expect(screen.getByText("Answer two")).toBeInTheDocument();
  expect(screen.getByText("Because three")).toBeInTheDocument();
  expect(screen.getAllByText("Explanation:")).toHaveLength(3);
  expect(screen.queryByText("Feedback:")).not.toBeInTheDocument();
  expect(screen.queryByText("Your answer:")).not.toBeInTheDocument();
});

test("free text: shows the student's answer and Feedback label", () => {
  const attempt: Attempt = {
    ...base,
    test_type: "free_text",
    score: 1,
    total_questions: 1,
    results: [
      { question_id: 7, question_text: "Explain X", question_type: "free_text", student_response: "my own words", verdict: "correct", feedback_text: "Well done", correct_answer_text: "Reference" },
    ],
  };
  render(<ResultsView attempt={attempt} />);
  expect(screen.getByText("my own words")).toBeInTheDocument();
  expect(screen.getByText("Feedback:")).toBeInTheDocument();
  expect(screen.queryByText("Explanation:")).not.toBeInTheDocument();
  expect(screen.getByText("Well done")).toBeInTheDocument();
});
