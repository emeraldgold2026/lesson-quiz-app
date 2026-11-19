import type { AnswerResult, Attempt } from "@/lib/types";

const VERDICTS: Record<AnswerResult["verdict"], { label: string; classes: string }> = {
  correct: { label: "Correct", classes: "bg-green-100 text-green-800" },
  partially_correct: { label: "Partially correct", classes: "bg-yellow-100 text-yellow-800" },
  incorrect: { label: "Incorrect", classes: "bg-red-100 text-red-800" },
};

function VerdictBadge({ result }: { result: AnswerResult }) {
  const { label, classes } = VERDICTS[result.verdict];
  return (
    <span
      data-testid={`verdict-${result.question_id}`}
      className={`rounded px-2 py-0.5 text-sm font-medium ${classes}`}
    >
      {label}
    </span>
  );
}

export function ResultsView({ attempt }: { attempt: Attempt }) {
  const freeText = attempt.test_type === "free_text";
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">
        Score: {attempt.score} / {attempt.total_questions}
      </h3>
      {attempt.results.map((r, i) => (
        <div key={r.question_id} className="space-y-2 rounded border p-4">
          <div className="flex items-start justify-between gap-3">
            <p className="font-medium">
              {!freeText && (
                <span className="mr-2 font-semibold text-blue-700">Question {i + 1}.</span>
              )}{" "}
              {r.question_text}
            </p>
            <VerdictBadge result={r} />
          </div>
          <div>
            <p className="text-sm font-semibold">Your answer:</p>
            <p className="whitespace-pre-wrap">{r.student_response_text}</p>
          </div>
          <div>
            <p className="text-sm font-semibold">Correct answer:</p>
            <p className="whitespace-pre-wrap">{r.correct_answer_text}</p>
          </div>
          <div>
            <p className="text-sm font-semibold">{freeText ? "Feedback:" : "Explanation:"}</p>
            <p className="whitespace-pre-wrap">{r.feedback_text}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
