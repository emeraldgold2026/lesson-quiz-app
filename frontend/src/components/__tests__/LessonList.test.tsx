import { render, screen } from "@testing-library/react";
import { LessonList } from "../LessonList";
import type { Lesson } from "@/lib/types";

const base: Lesson = {
  id: 1,
  title: "Fractions",
  status: "ready",
  error_message: null,
  page_count: 3,
  created_at: "2026-01-01T00:00:00Z",
  has_questions: true,
};

test("renders lessons as links with status badges", () => {
  render(
    <LessonList
      lessons={[base, { ...base, id: 2, title: "Decimals", status: "processing" }]}
    />,
  );
  expect(screen.getByRole("link", { name: "Fractions" })).toHaveAttribute("href", "/lessons/1");
  expect(screen.getByRole("link", { name: "Decimals" })).toHaveAttribute("href", "/lessons/2");
  expect(screen.getByText("ready")).toBeInTheDocument();
  expect(screen.getByText("processing")).toBeInTheDocument();
});

test("failed lessons show their error message", () => {
  render(<LessonList lessons={[{ ...base, status: "failed", error_message: "No text found" }]} />);
  expect(screen.getByText("No text found")).toBeInTheDocument();
});

test("empty list shows placeholder", () => {
  render(<LessonList lessons={[]} />);
  expect(screen.getByText(/No lessons yet/)).toBeInTheDocument();
});
