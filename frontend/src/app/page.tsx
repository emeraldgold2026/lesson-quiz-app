"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createLesson, listLessons } from "@/lib/api";
import type { Lesson } from "@/lib/types";
import { LessonList } from "@/components/LessonList";
import { UploadForm } from "@/components/UploadForm";

export default function Home() {
  const router = useRouter();
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setLessons(await listLessons());
      setLoadError(null);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  const anyProcessing = lessons.some((l) => l.status === "processing");
  useEffect(() => {
    if (!anyProcessing) return;
    const timer = setInterval(() => void refresh(), 3000);
    return () => clearInterval(timer);
  }, [anyProcessing, refresh]);

  async function handleUpload(title: string, files: File[]) {
    setBusy(true);
    setUploadError(null);
    try {
      const lesson = await createLesson(title, files);
      router.push(`/lessons/${lesson.id}`);
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <UploadForm onSubmit={handleUpload} busy={busy} error={uploadError} />
      <section>
        <h2 className="mb-2 text-lg font-semibold">Lessons</h2>
        {loadError && <p className="mb-2 text-sm text-red-700">{loadError}</p>}
        <LessonList lessons={lessons} />
      </section>
    </div>
  );
}
