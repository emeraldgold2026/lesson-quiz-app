export type LessonStatus = "processing" | "ready" | "failed";

export interface Lesson {
  id: number;
  title: string;
  status: LessonStatus;
  error_message: string | null;
  page_count: number;
  created_at: string;
  has_questions: boolean;
}

export interface McqQuestion {
  id: number;
  type: "mcq_single" | "mcq_multi";
  question_text: string;
  choices: { id: number; text: string }[];
}

export interface FreeTextQuestion {
  id: number;
  question_text: string;
}

export interface AnswerResult {
  question_id: number;
  question_text: string;
  question_type: string;
  student_response: number[] | string;
  /** Readable answer: the free text, or the selected MCQ choices' texts. */
  student_response_text: string;
  verdict: "correct" | "partially_correct" | "incorrect";
  feedback_text: string;
  correct_answer_text: string;
}

export interface Attempt {
  id: number;
  lesson_id: number;
  test_type: "mcq" | "free_text";
  started_at: string;
  submitted_at: string;
  score: number;
  total_questions: number;
  results: AnswerResult[];
}

export type AttemptSummary = Omit<Attempt, "results">;
