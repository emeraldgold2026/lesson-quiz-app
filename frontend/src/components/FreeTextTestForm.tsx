"use client";

import { useState } from "react";
import type { FreeTextQuestion } from "@/lib/types";

interface Props {
  questions: FreeTextQuestion[];
  onSubmit: (answers: Record<number, string>) => void;
  busy: boolean;
}

export function FreeTextTestForm({ questions, onSubmit, busy }: Props) {
  const [answers, setAnswers] = useState<Record<number, string>>({});

  const complete = questions.every((q) => (answers[q.id] ?? "").trim() !== "");

  return (
    <form
      className="space-y-6"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(answers);
      }}
    >
      {questions.map((q) => (
        <div key={q.id} className="space-y-2 rounded border p-4">
          <label htmlFor={`q-${q.id}`} className="block font-medium">
            {q.question_text}
          </label>
          <textarea
            id={`q-${q.id}`}
            rows={4}
            className="w-full rounded border p-2"
            value={answers[q.id] ?? ""}
            onChange={(e) => setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
          />
        </div>
      ))}
      <button
        type="submit"
        disabled={!complete || busy}
        className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
      >
        {busy ? "Grading…" : "Submit"}
      </button>
    </form>
  );
}
