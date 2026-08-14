import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "PII Redaction Tool — Detect & Redact Sensitive Data",
  description:
    "Upload .docx documents to automatically detect and redact personally identifiable information with AI-powered precision.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} h-full`} suppressHydrationWarning>
      <body className="min-h-full flex flex-col bg-slate-50 text-slate-800 font-[family-name:var(--font-inter)] antialiased">
        {children}
      </body>
    </html>
  );
}
