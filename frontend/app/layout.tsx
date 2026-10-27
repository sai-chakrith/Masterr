import type { Metadata } from "next";
import "./globals.css";
import AppFrame from "@/components/AppFrame";
import DemoNotice from "@/components/DemoNotice";

export const metadata: Metadata = {
  title: "Mastrr",
  description: "Aptitude learning with transparent progress and independent checks.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-white text-slate-900 antialiased dark:bg-slate-950 dark:text-slate-100">
        <DemoNotice />
        <AppFrame>{children}</AppFrame>
      </body>
    </html>
  );
}
