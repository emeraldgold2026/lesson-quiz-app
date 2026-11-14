"use client";

import { useEffect, useState } from "react";
import { getAttempt } from "@/lib/api";
import type { Attempt } from "@/lib/types";
import { ResultsView } from "@/components/ResultsView";

const TEST_TYPE_LABELS: Record<Attempt["test_type"], string> = {
  mcq: "MCQ test",
  free_text: "Free-text test",
};

export function AttemptReplay({ attemptId }: { attemptId: number }) {
  const valid = Number.isInteger(attemptId) && attemptId > 0;
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!valid) return;
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setAttempt(null);
    setError(null);
    getAttempt(attemptId).then(
      (a) => {
        if (!cancelled) setAttempt(a);
      },
      (e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      },
    );
    return () => {
      cancelled = true;
    };
  }, [attemptId, valid]);

  if (!valid) return <p className="text-sm text-red-700">Invalid attempt id</p>;

  return (
    <div className="space-y-4">
      {error && <p className="text-sm text-red-700">{error}</p>}
      {attempt && (
        <>
          <div>
            <h2 className="text-xl font-semibold">{TEST_TYPE_LABELS[attempt.test_type]}</h2>
            <p className="text-sm text-gray-600">
              Submitted {new Date(attempt.submitted_at).toLocaleString()}
            </p>
          </div>
          <ResultsView attempt={attempt} />
        </>
      )}
    </div>
  );
}
