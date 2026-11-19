import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { McqTestForm } from "../McqTestForm";
import type { McqCheckResult, McqQuestion } from "@/lib/types";

const qs: McqQuestion[] = [
  { id: 1, type: "mcq_single", question_text: "Q1", choices: [{ id: 10, text: "A" }, { id: 11, text: "B" }] },
  { id: 2, type: "mcq_multi", question_text: "Q2", choices: [{ id: 20, text: "C" }, { id: 21, text: "D" }] },
];

// Question 1: B is right. Question 2: C and D are right.
const key: Record<number, McqCheckResult> = {
  1: { verdict: "correct", correct_choice_ids: [11], correct_answer_text: "B", explanation: "Because B" },
  2: { verdict: "correct", correct_choice_ids: [20, 21], correct_answer_text: "C; D", explanation: "Because C and D" },
};

function grader() {
  return vi.fn(async (id: number, selected: number[]): Promise<McqCheckResult> => {
    const k = key[id];
    const ok = selected.length === k.correct_choice_ids.length && selected.every((s) => k.correct_choice_ids.includes(s));
    return { ...k, verdict: ok ? "correct" : "incorrect" };
  });
}

test("shows one question at a time, numbered, with a gated Submit answer button", async () => {
  render(<McqTestForm questions={qs} onCheck={grader()} onSubmit={vi.fn()} busy={false} />);
  expect(screen.getByText("Question 1 of 2")).toBeInTheDocument();
  expect(screen.getByRole("group", { name: "Question 1. Q1" })).toBeInTheDocument();
  expect(screen.queryByText("Q2")).not.toBeInTheDocument();
  expect(screen.getAllByRole("radio")).toHaveLength(2);
  expect(screen.getByRole("button", { name: /submit answer/i })).toBeDisabled();
  await userEvent.click(screen.getByLabelText("A"));
  expect(screen.getByRole("button", { name: /submit answer/i })).toBeEnabled();
});

test("a wrong answer gets instant feedback: verdict, correct answer, reasoning; then it is locked", async () => {
  const onCheck = grader();
  render(<McqTestForm questions={qs} onCheck={onCheck} onSubmit={vi.fn()} busy={false} />);
  await userEvent.click(screen.getByLabelText("A"));
  await userEvent.click(screen.getByRole("button", { name: /submit answer/i }));

  expect(onCheck).toHaveBeenCalledWith(1, [10]);
  const status = await screen.findByRole("status");
  expect(status).toHaveTextContent("Incorrect");
  expect(status).toHaveTextContent("Correct answer: B");
  expect(status).toHaveTextContent("Why: Because B");
  expect(screen.getByText("Your answer")).toBeInTheDocument();
  expect(screen.getByText("Correct answer")).toBeInTheDocument();
  expect(screen.getByLabelText(/^A/)).toBeDisabled();
  expect(screen.getByRole("button", { name: /next question/i })).toBeEnabled();
});

test("walks through every question, then submits all answers together", async () => {
  const onSubmit = vi.fn();
  const onCheck = grader();
  render(<McqTestForm questions={qs} onCheck={onCheck} onSubmit={onSubmit} busy={false} />);

  await userEvent.click(screen.getByLabelText("B"));
  await userEvent.click(screen.getByRole("button", { name: /submit answer/i }));
  expect(await screen.findByRole("status")).toHaveTextContent("Correct!");
  await userEvent.click(screen.getByRole("button", { name: /next question/i }));

  expect(screen.getByText("Question 2 of 2")).toBeInTheDocument();
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  expect(screen.getAllByRole("checkbox")).toHaveLength(2);
  await userEvent.click(screen.getByLabelText("C"));
  await userEvent.click(screen.getByLabelText("D"));
  await userEvent.click(screen.getByRole("button", { name: /submit answer/i }));
  expect(await screen.findByRole("status")).toHaveTextContent("Correct answer: C; D");

  expect(onSubmit).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: /finish test/i }));
  expect(onSubmit).toHaveBeenCalledWith({ 1: [11], 2: [20, 21] });
});

test("unchecking the last checkbox gates Submit answer again", async () => {
  render(<McqTestForm questions={[qs[1]]} onCheck={grader()} onSubmit={vi.fn()} busy={false} />);
  await userEvent.click(screen.getByLabelText("C"));
  expect(screen.getByRole("button", { name: /submit answer/i })).toBeEnabled();
  await userEvent.click(screen.getByLabelText("C"));
  expect(screen.getByRole("button", { name: /submit answer/i })).toBeDisabled();
});

test("a failed check shows the error and lets the student try again", async () => {
  const onCheck = vi
    .fn<(id: number, selected: number[]) => Promise<McqCheckResult>>()
    .mockRejectedValueOnce(new Error("server down"))
    .mockResolvedValueOnce(key[1]);
  render(<McqTestForm questions={[qs[0]]} onCheck={onCheck} onSubmit={vi.fn()} busy={false} />);
  await userEvent.click(screen.getByLabelText("B"));
  await userEvent.click(screen.getByRole("button", { name: /submit answer/i }));
  expect(await screen.findByText("server down")).toBeInTheDocument();
  expect(screen.queryByRole("status")).not.toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: /submit answer/i }));
  expect(await screen.findByRole("status")).toHaveTextContent("Correct!");
  expect(screen.queryByText("server down")).not.toBeInTheDocument();
});

test("Finish test is disabled while the final submit is in flight", async () => {
  render(<McqTestForm questions={[qs[0]]} onCheck={grader()} onSubmit={vi.fn()} busy={true} />);
  await userEvent.click(screen.getByLabelText("B"));
  await userEvent.click(screen.getByRole("button", { name: /submit answer/i }));
  expect(await screen.findByRole("button", { name: /submitting/i })).toBeDisabled();
});
