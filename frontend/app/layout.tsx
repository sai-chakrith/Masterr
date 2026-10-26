import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import AccountNav from "@/components/AccountNav";

export const metadata: Metadata = {
  title: "Mastrr",
  description: "Aptitude learning with transparent progress and independent checks.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-white text-slate-900 antialiased dark:bg-slate-950 dark:text-slate-100">
        <header className="border-b border-slate-200 dark:border-slate-800">
          <nav className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
            <Link href="/" className="text-lg font-semibold tracking-tight">
              Mastrr
            </Link>
            <Link href="/tutor" className="text-sm text-slate-600 hover:underline dark:text-slate-300">
              Tutor
            </Link>
            <AccountNav />
          </nav>
          <nav aria-label="Learning tools" className="mx-auto flex max-w-3xl gap-5 px-4 pb-3 text-sm"><Link href="/practice-test" className="hover:underline">Timed practice</Link><Link href="/history" className="hover:underline">History</Link></nav>
        </header>
        <main className="mx-auto max-w-3xl px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
