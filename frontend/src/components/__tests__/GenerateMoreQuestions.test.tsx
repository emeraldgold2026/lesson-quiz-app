import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { GenerateMoreQuestions } from "../GenerateMoreQuestions";

afterEach(() => vi.unstubAllGlobals());

function stubFetch(status: number, body: unknown) {
  const fn = vi.fn(async () => new Response(JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", fn);
  return fn;
}

test("requests the chosen number of questions and reports the result", async () => {
  const fetchFn = stubFetch(200, { added: 3, total: 12 });
  render(<GenerateMoreQuestions lessonId={7} kind="mcq" label="MCQ" />);
  fireEvent.change(screen.getByLabelText(/more mcq questions/i), { target: { value: "3" } });
  fireEvent.click(screen.getByRole("button", { name: /generate mcq questions/i }));

  expect(await screen.findByText("Added 3 MCQ questions (12 total).")).toBeInTheDocument();
  const [url, init] = fetchFn.mock.calls[0] as unknown as [string, RequestInit];
  expect(url).toMatch(/\/lessons\/7\/questions$/);
  expect(JSON.parse(String(init.body))).toEqual({ kind: "mcq", count: 3 });
});

test("shows the server error and re-enables the button", async () => {
  stubFetch(502, { detail: "question generation failed: boom" });
  render(<GenerateMoreQuestions lessonId={7} kind="free_text" label="free-text" />);
  const button = screen.getByRole("button", { name: /generate free-text questions/i });
  fireEvent.click(button);

  expect(await screen.findByText("question generation failed: boom")).toBeInTheDocument();
  await waitFor(() => expect(button).toBeEnabled());
});

test("blocks counts outside 1-20", () => {
  render(<GenerateMoreQuestions lessonId={7} kind="mcq" label="MCQ" />);
  const input = screen.getByLabelText(/more mcq questions/i);
  const button = screen.getByRole("button", { name: /generate mcq questions/i });
  fireEvent.change(input, { target: { value: "21" } });
  expect(button).toBeDisabled();
  fireEvent.change(input, { target: { value: "0" } });
  expect(button).toBeDisabled();
  fireEvent.change(input, { target: { value: "20" } });
  expect(button).toBeEnabled();
});
