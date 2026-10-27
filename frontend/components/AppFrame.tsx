"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import AccountNav from "@/components/AccountNav";

export default function AppFrame({ children }: { children: React.ReactNode }) {
  const login = usePathname() === "/login";
  if (login) return <main>{children}</main>;
  return <>
    <header className="border-b border-slate-200 dark:border-slate-800">
      <nav className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
        <Link href="/" className="text-lg font-semibold tracking-tight">Mastrr</Link>
        <Link href="/tutor" className="text-sm text-slate-600 hover:underline dark:text-slate-300">Tutor</Link>
        <AccountNav />
      </nav>
      <nav aria-label="Learning tools" className="mx-auto flex max-w-3xl gap-5 px-4 pb-3 text-sm">
        <Link href="/practice-test" className="hover:underline">Timed practice</Link>
        <Link href="/history" className="hover:underline">History</Link>
      </nav>
    </header>
    <main className="mx-auto max-w-3xl px-4 py-6">{children}</main>
  </>;
}
