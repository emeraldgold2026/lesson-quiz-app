"use client";

import { use } from "react";
import Link from "next/link";
import { AttemptReplay } from "@/components/AttemptReplay";

export default function AttemptPage({
  params,
}: PageProps<"/lessons/[id]/attempts/[attemptId]">) {
  const { id, attemptId } = use(params);
  return (
    <div className="space-y-4">
      <Link href={`/lessons/${id}`} className="text-sm text-blue-700 hover:underline">
        Back to lesson
      </Link>
      <AttemptReplay attemptId={Number(attemptId)} />
    </div>
  );
}
