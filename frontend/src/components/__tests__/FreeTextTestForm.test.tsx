import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FreeTextTestForm } from "../FreeTextTestForm";
import type { FreeTextQuestion } from "@/lib/types";

const qs: FreeTextQuestion[] = [
  { id: 1, question_text: "Q1" },
  { id: 2, question_text: "Q2" },
];

test("submit gated until both boxes filled, then sends typed text", async () => {
  const onSubmit = vi.fn();
  render(<FreeTextTestForm questions={qs} onSubmit={onSubmit} busy={false} />);
  const submit = screen.getByRole("button", { name: /submit/i });
  expect(submit).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Q1"), "foo");
  expect(submit).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Q2"), "bar");
  expect(submit).toBeEnabled();
  await userEvent.click(submit);
  expect(onSubmit).toHaveBeenCalledWith({ 1: "foo", 2: "bar" });
});

test("whitespace-only answer does not enable submit", async () => {
  render(<FreeTextTestForm questions={qs} onSubmit={vi.fn()} busy={false} />);
  await userEvent.type(screen.getByLabelText("Q1"), "foo");
  await userEvent.type(screen.getByLabelText("Q2"), "   ");
  expect(screen.getByRole("button", { name: /submit/i })).toBeDisabled();
});

test("while busy the button reads Grading… and is disabled", async () => {
  render(<FreeTextTestForm questions={qs} onSubmit={vi.fn()} busy={true} />);
  await userEvent.type(screen.getByLabelText("Q1"), "foo");
  await userEvent.type(screen.getByLabelText("Q2"), "bar");
  expect(screen.getByRole("button", { name: "Grading…" })).toBeDisabled();
});
