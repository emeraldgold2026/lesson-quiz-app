import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { McqTestForm } from "../McqTestForm";
import type { McqQuestion } from "@/lib/types";

test("radio for single, checkbox for multi; submit gated and sends selections", async () => {
  const qs: McqQuestion[] = [
    { id: 1, type: "mcq_single", question_text: "Q1", choices: [{ id: 10, text: "A" }, { id: 11, text: "B" }] },
    { id: 2, type: "mcq_multi", question_text: "Q2", choices: [{ id: 20, text: "C" }, { id: 21, text: "D" }] },
  ];
  const onSubmit = vi.fn();
  render(<McqTestForm questions={qs} onSubmit={onSubmit} busy={false} />);
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

test("questions are numbered in display order", () => {
  const qs: McqQuestion[] = [
    { id: 41, type: "mcq_single", question_text: "First?", choices: [{ id: 1, text: "A" }] },
    { id: 7, type: "mcq_single", question_text: "Second?", choices: [{ id: 2, text: "B" }] },
  ];
  render(<McqTestForm questions={qs} onSubmit={vi.fn()} busy={false} />);
  expect(screen.getByRole("group", { name: "Question 1. First?" })).toBeInTheDocument();
  expect(screen.getByRole("group", { name: "Question 2. Second?" })).toBeInTheDocument();
});

test("submit stays disabled while busy", async () => {
  const qs: McqQuestion[] = [
    { id: 1, type: "mcq_single", question_text: "Q1", choices: [{ id: 10, text: "A" }] },
  ];
  render(<McqTestForm questions={qs} onSubmit={vi.fn()} busy={true} />);
  await userEvent.click(screen.getByLabelText("A"));
  expect(screen.getByRole("button", { name: /submit/i })).toBeDisabled();
});

test("unchecking the last checkbox gates submit again", async () => {
  const qs: McqQuestion[] = [
    { id: 2, type: "mcq_multi", question_text: "Q2", choices: [{ id: 20, text: "C" }] },
  ];
  render(<McqTestForm questions={qs} onSubmit={vi.fn()} busy={false} />);
  await userEvent.click(screen.getByLabelText("C"));
  expect(screen.getByRole("button", { name: /submit/i })).toBeEnabled();
  await userEvent.click(screen.getByLabelText("C"));
  expect(screen.getByRole("button", { name: /submit/i })).toBeDisabled();
});
