"use client";

import { useState } from "react";
import type { McqCheckResult, McqQuestion } from "@/lib/types";

interface Props {
  questions: McqQuestion[];
  /** Grades one answer for instant feedback; nothing is saved until the test is submitted. */
  onCheck: (questionId: number, selected: number[]) => Promise<McqCheckResult>;
  onSubmit: (answers: Record<number, number[]>) => void;
  busy: boolean;
}

export function McqTestForm({ questions, onCheck, onSubmit, busy }: Props) {
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<number, number[]>>({});
  const [checked, setChecked] = useState<Record<number, McqCheckResult>>({});
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState<string | null>(null);

  const q = questions[index];
  const result = checked[q.id];
  const selected = answers[q.id] ?? [];
  const multi = q.type === "mcq_multi";
  const isLast = index === questions.length - 1;

  function select(choiceId: number, isChecked: boolean) {
    setAnswers((prev) => {
      if (!multi) return { ...prev, [q.id]: [choiceId] };
      const current = prev[q.id] ?? [];
      const next = isChecked ? [...current, choiceId] : current.filter((c) => c !== choiceId);
      return { ...prev, [q.id]: next };
    });
  }

  async function handleCheck() {
    setChecking(true);
    setCheckError(null);
    try {
      const res = await onCheck(q.id, selected);
      setChecked((prev) => ({ ...prev, [q.id]: res }));
    } catch (e) {
      setCheckError(e instanceof Error ? e.message : String(e));
    } finally {
      setChecking(false);
    }
  }

  function choiceClasses(choiceId: number): string {
    if (!result) return "";
    if (result.correct_choice_ids.includes(choiceId)) return "bg-green-100 text-green-900";
    if (selected.includes(choiceId)) return "bg-red-100 text-red-900";
    return "";
  }

  function choiceNote(choiceId: number): string | null {
    if (!result) return null;
    const isCorrect = result.correct_choice_ids.includes(choiceId);
    const picked = selected.includes(choiceId);
    if (isCorrect) return picked ? "Correct" : "Correct answer";
    return picked ? "Your answer" : null;
  }

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (!result) void handleCheck();
        else if (isLast) onSubmit(answers);
        else setIndex(index + 1);
      }}
    >
      <p className="text-sm text-gray-600">
        Question {index + 1} of {questions.length}
      </p>
      <fieldset className="space-y-2 rounded border p-4">
        <legend className="px-1 font-medium">
          <span className="mr-2 font-semibold text-blue-700">Question {index + 1}.</span>{" "}
          {q.question_text}
        </legend>
        {multi && <p className="text-sm text-gray-500">Select all that apply.</p>}
        {q.choices.map((c) => {
          const note = choiceNote(c.id);
          return (
            <label key={c.id} className={`flex items-center gap-2 rounded px-2 py-1 ${choiceClasses(c.id)}`}>
              <input
                type={multi ? "checkbox" : "radio"}
                name={`q-${q.id}`}
                checked={selected.includes(c.id)}
                disabled={result !== undefined || checking}
                onChange={(e) => select(c.id, e.target.checked)}
              />
              <span>{c.text}</span>
              {note && <span className="ml-auto text-sm font-medium">{note}</span>}
            </label>
          );
        })}
      </fieldset>

      {result && (
        <div
          role="status"
          className={`space-y-1 rounded border p-4 ${
            result.verdict === "correct" ? "border-green-300 bg-green-50" : "border-red-300 bg-red-50"
          }`}
        >
          <p className="font-semibold">{result.verdict === "correct" ? "Correct!" : "Incorrect"}</p>
          <p>
            <span className="font-semibold">Correct answer:</span> {result.correct_answer_text}
          </p>
          <p className="whitespace-pre-wrap">
            <span className="font-semibold">Why:</span> {result.explanation}
          </p>
        </div>
      )}
      {checkError && <p className="text-sm text-red-700">{checkError}</p>}

      {result ? (
        <button
          type="submit"
          disabled={busy}
          className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
        >
          {isLast ? (busy ? "Submitting..." : "Finish test") : "Next question"}
        </button>
      ) : (
        <button
          type="submit"
          disabled={selected.length === 0 || checking}
          className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
        >
          {checking ? "Checking..." : "Submit answer"}
        </button>
      )}
    </form>
  );
}
