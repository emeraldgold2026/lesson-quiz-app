"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { getFreeTextTest, submitFreeTextTest } from "@/lib/api";
import type { Attempt, FreeTextQuestion } from "@/lib/types";
import { FreeTextTestForm } from "@/components/FreeTextTestForm";
import { ResultsView } from "@/components/ResultsView";

export default function FreeTextTestPage({
  params,
}: PageProps<"/lessons/[id]/free-text-test">) {
  const { id: idParam } = use(params);
  const id = Number(idParam);
  const [questions, setQuestions] = useState<FreeTextQuestion[] | null>(null);
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setQuestions(await getFreeTextTest(id));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [id]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  // The form stays mounted while attempt is null, so its typed answers
  // survive a failed submit.
  async function handleSubmit(answers: Record<number, string>) {
    setBusy(true);
    try {
      setAttempt(await submitFreeTextTest(id, answers));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  function handleRetake() {
    setAttempt(null);
    setQuestions(null);
    void load();
  }

  return (
    <div className="space-y-4">
      <Link href={`/lessons/${id}`} className="text-sm text-blue-700 hover:underline">
        Back to lesson
      </Link>
      <h2 className="text-xl font-semibold">Free-text Test</h2>
      {error && <p className="text-sm text-red-700">{error}</p>}
      {attempt ? (
        <div className="space-y-4">
          <ResultsView attempt={attempt} />
          <div className="flex gap-3">
            <button onClick={handleRetake} className="rounded bg-blue-600 px-4 py-2 text-white">
              Retake
            </button>
            <Link href={`/lessons/${id}`} className="rounded border px-4 py-2">
              Back to lesson
            </Link>
          </div>
        </div>
      ) : (
        questions && (
          <FreeTextTestForm questions={questions} onSubmit={(a) => void handleSubmit(a)} busy={busy} />
        )
      )}
    </div>
  );
}
