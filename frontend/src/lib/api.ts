import type {
  Attempt,
  AttemptSummary,
  FreeTextQuestion,
  Lesson,
  McqQuestion,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function detailToMessage(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) => (d && typeof d === "object" && "msg" in d ? String(d.msg) : null))
      .filter((m): m is string => m !== null);
    if (msgs.length > 0) return msgs.join("; ");
  }
  return fallback;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = undefined;
    }
    throw new Error(detailToMessage(detail, `Request failed (${res.status})`));
  }
  return (await res.json()) as T;
}

function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export const listLessons = () => request<Lesson[]>("/lessons");
export const getLesson = (id: number) => request<Lesson>(`/lessons/${id}`);

export function createLesson(title: string, files: File[]): Promise<Lesson> {
  const form = new FormData();
  form.append("title", title);
  for (const f of files) form.append("files", f);
  return request<Lesson>("/lessons", { method: "POST", body: form });
}

export const retryLesson = (id: number) =>
  request<Lesson>(`/lessons/${id}/retry`, { method: "POST" });

export const getMcqTest = (id: number) =>
  request<McqQuestion[]>(`/lessons/${id}/mcq-test`);
export const submitMcqTest = (id: number, answers: Record<number, number[]>) =>
  postJson<Attempt>(`/lessons/${id}/mcq-test/submit`, { answers });

export const getFreeTextTest = (id: number) =>
  request<FreeTextQuestion[]>(`/lessons/${id}/free-text-test`);
export const submitFreeTextTest = (id: number, answers: Record<number, string>) =>
  postJson<Attempt>(`/lessons/${id}/free-text-test/submit`, { answers });

export const listAttempts = (id: number) =>
  request<AttemptSummary[]>(`/lessons/${id}/attempts`);
export const getAttempt = (id: number) => request<Attempt>(`/attempts/${id}`);
