"use client";

import { useState } from "react";

interface Props {
  onSubmit: (title: string, files: File[]) => void;
  busy: boolean;
  error: string | null;
}

export function UploadForm({ onSubmit, busy, error }: Props) {
  const [title, setTitle] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const canSubmit = title.trim() !== "" && files.length > 0 && !busy;

  return (
    <form
      className="space-y-3 rounded border p-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (canSubmit) onSubmit(title.trim(), files);
      }}
    >
      <div>
        <label htmlFor="lesson-title" className="block text-sm font-medium">
          Lesson title
        </label>
        <input
          id="lesson-title"
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="mt-1 w-full rounded border px-2 py-1"
        />
      </div>
      <div>
        <label htmlFor="lesson-pages" className="block text-sm font-medium">
          Lesson pages (images)
        </label>
        <input
          id="lesson-pages"
          type="file"
          multiple
          accept="image/*"
          onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
          className="mt-1 block w-full text-sm"
        />
      </div>
      {error && <p className="text-sm text-red-700">{error}</p>}
      <button
        type="submit"
        disabled={!canSubmit}
        className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
      >
        {busy ? "Uploading..." : "Upload"}
      </button>
    </form>
  );
}
