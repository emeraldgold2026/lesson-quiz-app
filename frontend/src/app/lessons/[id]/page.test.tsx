import { Suspense } from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import LessonDetail from "./page";
import type { Lesson } from "@/lib/types";

const lesson = (status: Lesson["status"]): Lesson => ({
  id: 7,
  title: "Chapter 1",
  status,
  error_message: status === "failed" ? "Boom" : null,
  page_count: 1,
  created_at: "2026-01-01T00:00:00Z",
  has_questions: false,
});

type Pending = { url: string; method: string; resolve: (body: unknown) => void };

function controlledFetch() {
  const pending: Pending[] = [];
  const fn = vi.fn(
    (url: string, init?: RequestInit) =>
      new Promise<Response>((res) => {
        pending.push({
          url,
          method: init?.method ?? "GET",
          resolve: (body) => res(new Response(JSON.stringify(body), { status: 200 })),
        });
      }),
  );
  vi.stubGlobal("fetch", fn);
  return pending;
}

async function settle(p: Pending, body: unknown) {
  await act(async () => p.resolve(body));
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function renderPage() {
  await act(async () => {
    render(
      <Suspense fallback="loading">
        <LessonDetail
          params={Promise.resolve({ id: "7" }) as never}
          searchParams={Promise.resolve({}) as never}
        />
      </Suspense>,
    );
  });
}

test("Retry is disabled while in flight and a stale poll cannot undo it", async () => {
  const pending = controlledFetch();
  await renderPage();
  await settle(pending[0], lesson("processing"));

  // Two polls go out; the newer one reports the failure, the older is still in flight.
  await act(async () => void (await vi.advanceTimersByTimeAsync(2000)));
  await act(async () => void (await vi.advanceTimersByTimeAsync(2000)));
  const [stalePoll, latestPoll] = pending.slice(1, 3);
  await settle(latestPoll, lesson("failed"));

  const retry = screen.getByRole("button", { name: /retry/i });
  fireEvent.click(retry);
  const retryReq = pending[3];
  expect(retryReq.method).toBe("POST");
  expect(screen.getByRole("button", { name: /retry/i })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: /retry/i }));
  expect(pending.filter((p) => p.method === "POST")).toHaveLength(1);

  await settle(retryReq, lesson("processing"));
  expect(screen.getByText("Processing your pages...")).toBeInTheDocument();

  // The poll sent before the retry answers late with the old "failed" state.
  await settle(stalePoll, lesson("failed"));
  expect(screen.getByText("Processing your pages...")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /retry/i })).not.toBeInTheDocument();
});
