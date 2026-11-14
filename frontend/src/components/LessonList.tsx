import Link from "next/link";
import type { Lesson } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";

export function LessonList({ lessons }: { lessons: Lesson[] }) {
  if (lessons.length === 0) {
    return <p className="text-gray-500">No lessons yet. Upload one above.</p>;
  }
  return (
    <ul className="divide-y rounded border">
      {lessons.map((l) => (
        <li key={l.id} className="p-3">
          <div className="flex items-center justify-between gap-3">
            <Link href={`/lessons/${l.id}`} className="font-medium text-blue-700 hover:underline">
              {l.title}
            </Link>
            <StatusBadge status={l.status} />
          </div>
          {l.status === "failed" && l.error_message && (
            <p className="mt-1 text-sm text-red-700">{l.error_message}</p>
          )}
        </li>
      ))}
    </ul>
  );
}
