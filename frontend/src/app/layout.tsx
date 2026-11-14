import { Suspense } from "react";
import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Lesson Quiz",
  description: "Turn lesson pages into quizzes",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <main className="mx-auto w-full max-w-3xl p-6">
          <h1 className="mb-6 text-2xl font-bold">Lesson Quiz</h1>
          <Suspense fallback={<p className="text-gray-500">Loading...</p>}>{children}</Suspense>
        </main>
      </body>
    </html>
  );
}
