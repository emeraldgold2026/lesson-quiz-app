"use client";

import { useState } from "react";
import type { McqQuestion } from "@/lib/types";

interface Props {
  questions: McqQuestion[];
  onSubmit: (answers: Record<number, number[]>) => void;
  busy: boolean;
}

export function McqTestForm({ questions, onSubmit, busy }: Props) {
  const [answers, setAnswers] = useState<Record<number, number[]>>({});

  const complete = questions.every((q) => (answers[q.id]?.length ?? 0) > 0);

  function select(q: McqQuestion, choiceId: number, checked: boolean) {
    setAnswers((prev) => {
      if (q.type === "mcq_single") return { ...prev, [q.id]: [choiceId] };
      const current = prev[q.id] ?? [];
      const next = checked
        ? [...current, choiceId]
        : current.filter((c) => c !== choiceId);
      return { ...prev, [q.id]: next };
    });
  }

  return (
    <form
      className="space-y-6"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(answers);
      }}
    >
      {questions.map((q) => {
        const multi = q.type === "mcq_multi";
        return (
          <fieldset key={q.id} className="space-y-2 rounded border p-4">
            <legend className="px-1 font-medium">{q.question_text}</legend>
            {multi && (
              <p className="text-sm text-gray-500">Select all that apply.</p>
            )}
            {q.choices.map((c) => (
              <label key={c.id} className="flex items-center gap-2">
                <input
                  type={multi ? "checkbox" : "radio"}
                  name={`q-${q.id}`}
                  checked={answers[q.id]?.includes(c.id) ?? false}
                  onChange={(e) => select(q, c.id, e.target.checked)}
                />
                {c.text}
              </label>
            ))}
          </fieldset>
        );
      })}
      <button
        type="submit"
        disabled={!complete || busy}
        className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
      >
        {busy ? "Submitting..." : "Submit"}
      </button>
    </form>
  );
}
