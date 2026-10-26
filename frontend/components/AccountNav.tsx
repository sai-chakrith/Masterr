"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { authClient, savedToken, signOut } from "@/lib/auth-client";
export default function AccountNav() {
  const [signedIn, setSignedIn] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();
  useEffect(() => {
    setSignedIn(Boolean(savedToken()));
    const sub = authClient()?.auth.onAuthStateChange((_event, session) => setSignedIn(Boolean(session)));
    const refresh = () => setSignedIn(Boolean(savedToken()));
    window.addEventListener("storage", refresh); window.addEventListener("mastrr-auth", refresh);
    return () => { sub?.data.subscription.unsubscribe(); window.removeEventListener("storage", refresh); window.removeEventListener("mastrr-auth", refresh); };
  }, []);
  async function logout() {
    try { await signOut(); setSignedIn(false); router.replace("/login"); }
    catch { setError("Could not sign out. Please try again."); }
  }
  return <div className="flex items-center gap-4 text-sm">
    <Link href={signedIn ? "/account" : "/login"} className="hover:underline">{signedIn ? "Account" : "Sign in"}</Link>
    {signedIn && <button onClick={() => void logout()} className="underline">Sign out</button>}
    {error && <span role="alert">{error}</span>}
  </div>;
}
