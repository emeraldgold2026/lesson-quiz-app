import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { UploadForm } from "../UploadForm";

test("enables submit only with title and files, then submits", async () => {
  const onSubmit = vi.fn();
  render(<UploadForm onSubmit={onSubmit} busy={false} error={null} />);
  const btn = screen.getByRole("button", { name: /upload/i });
  expect(btn).toBeDisabled();
  await userEvent.type(screen.getByLabelText(/title/i), "Chapter 1");
  await userEvent.upload(screen.getByLabelText(/pages/i), new File(["x"], "p1.png", { type: "image/png" }));
  expect(btn).toBeEnabled();
  await userEvent.click(btn);
  expect(onSubmit).toHaveBeenCalledWith("Chapter 1", [expect.any(File)]);
});

test("file input accepts multiple images", () => {
  render(<UploadForm onSubmit={vi.fn()} busy={false} error={null} />);
  const input = screen.getByLabelText(/pages/i);
  expect(input).toHaveAttribute("multiple");
  expect(input).toHaveAttribute("accept", "image/*");
});

test("blank title keeps submit disabled", async () => {
  render(<UploadForm onSubmit={vi.fn()} busy={false} error={null} />);
  await userEvent.type(screen.getByLabelText(/title/i), "   ");
  await userEvent.upload(screen.getByLabelText(/pages/i), new File(["x"], "p1.png", { type: "image/png" }));
  expect(screen.getByRole("button", { name: /upload/i })).toBeDisabled();
});

test("shows error", () => {
  render(<UploadForm onSubmit={vi.fn()} busy={false} error="bad file" />);
  expect(screen.getByText("bad file")).toBeInTheDocument();
});
