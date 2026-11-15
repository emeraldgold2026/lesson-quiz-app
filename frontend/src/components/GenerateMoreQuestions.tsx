"use client";

import { useState } from "react";
import { generateMoreQuestions } from "@/lib/api";

const MAX_COUNT = 20;

export function GenerateMoreQuestions({
  lessonId,
  kind,
  label,
}: {
  lessonId: number;
  kind: "mcq" | "free_text";
  label: string;
}) {
  const [count, setCount] = useState(5);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleGenerate() {
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      const { added, total } = await generateMoreQuestions(lessonId, kind, count);
      setMessage(`Added ${added} ${label} questions (${total} total).`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-1 rounded border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <label className="text-sm" htmlFor={`count-${kind}`}>
          More {label} questions
        </label>
        <input
          id={`count-${kind}`}
          type="number"
          min={1}
          max={MAX_COUNT}
          value={count}
          onChange={(e) => setCount(Number(e.target.value))}
          disabled={busy}
          className="w-20 rounded border px-2 py-1"
        />
        <button
          onClick={() => void handleGenerate()}
          disabled={busy || !Number.isInteger(count) || count < 1 || count > MAX_COUNT}
          className="rounded border px-3 py-1 disabled:opacity-50"
        >
          {busy ? "Generating..." : `Generate ${label} questions`}
        </button>
      </div>
      {message && <p className="text-sm text-green-700">{message}</p>}
      {error && <p className="text-sm text-red-700">{error}</p>}
    </div>
  );
}
