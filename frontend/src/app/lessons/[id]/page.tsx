"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { getLesson, listAttempts, retryLesson } from "@/lib/api";
import type { AttemptSummary, Lesson } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";

export default function LessonDetail({ params }: PageProps<"/lessons/[id]">) {
  const { id: idParam } = use(params);
  const id = Number(idParam);
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [attempts, setAttempts] = useState<AttemptSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);

  // Only the most recently issued lesson request may update state, so a slow poll
  // sent before a Retry cannot overwrite the Retry's newer result.
  const latestRequest = useRef(0);

  const refresh = useCallback(async () => {
    const seq = ++latestRequest.current;
    try {
      const fresh = await getLesson(id);
      if (seq !== latestRequest.current) return;
      setLesson(fresh);
      setError(null);
    } catch (e) {
      if (seq !== latestRequest.current) return;
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [id]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  const status = lesson?.status;
  useEffect(() => {
    if (status !== "processing") return;
    const timer = setInterval(() => void refresh(), 2000);
    return () => clearInterval(timer);
  }, [status, refresh]);

  async function handleRetry() {
    const seq = ++latestRequest.current;
    setRetrying(true);
    try {
      const fresh = await retryLesson(id);
      if (seq === latestRequest.current) setLesson(fresh);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRetrying(false);
    }
  }

  async function showAttempts() {
    try {
      setAttempts(await listAttempts(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="space-y-4">
      <Link href="/" className="text-sm text-blue-700 hover:underline">
        Back to lessons
      </Link>
      {error && <p className="text-sm text-red-700">{error}</p>}
      {lesson && (
        <>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-semibold">{lesson.title}</h2>
            <StatusBadge status={lesson.status} />
          </div>
          {lesson.status === "processing" && (
            <p className="text-gray-600">Processing your pages...</p>
          )}
          {lesson.status === "failed" && (
            <div className="space-y-2">
              <p className="text-red-700">{lesson.error_message}</p>
              <button
                onClick={() => void handleRetry()}
                disabled={retrying}
                className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
              >
                {retrying ? "Retrying..." : "Retry"}
              </button>
            </div>
          )}
          {lesson.status === "ready" && (
            <div className="space-y-4">
              <div className="flex flex-wrap gap-3">
                <Link
                  href={`/lessons/${id}/mcq-test`}
                  className="rounded bg-blue-600 px-4 py-2 text-white"
                >
                  Take MCQ Test
                </Link>
                <Link
                  href={`/lessons/${id}/free-text-test`}
                  className="rounded bg-blue-600 px-4 py-2 text-white"
                >
                  Take Free-Text Test
                </Link>
                <button
                  onClick={() => void showAttempts()}
                  className="rounded border px-4 py-2"
                >
                  View Past Attempts
                </button>
              </div>
              {attempts && (
                <ul className="divide-y rounded border">
                  {attempts.length === 0 && <li className="p-3 text-gray-500">No attempts yet.</li>}
                  {attempts.map((a) => (
                    <li key={a.id} className="p-3">
                      <Link
                        href={`/lessons/${id}/attempts/${a.id}`}
                        className="text-blue-700 hover:underline"
                      >
                        {a.test_type === "mcq" ? "MCQ" : "Free-text"}:{" "}
                        {a.score} / {a.total_questions}
                      </Link>{" "}
                      <span className="text-sm text-gray-500">
                        {new Date(a.submitted_at).toLocaleString()}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
