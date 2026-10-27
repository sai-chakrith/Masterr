"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, setToken } from "@/lib/api";
import { authClient, hostedAuthConfigured, localAuthEnabled, LOCAL_SESSION, signOut } from "@/lib/auth-client";

function Arrow() { return <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="M4 12h15m-6-6 6 6-6 6" /></svg>; }
function Mark() { return <svg aria-hidden="true" width="26" height="26" viewBox="0 0 28 28" fill="none"><path d="M3 22V6l11 11L25 6v16" stroke="currentColor" strokeWidth="3" strokeLinejoin="round" /></svg>; }

export default function SignInForm() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup" | "recover">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [token, setLocalToken] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const hosted = hostedAuthConfigured();
  const input = "mt-2 block w-full rounded-xl border border-[#dce1da] bg-white px-4 py-3.5 text-[15px] text-[#172b24] outline-none transition placeholder:text-[#9aaba2] focus:border-[#286b50] focus:ring-4 focus:ring-[#286b50]/10";

  function changeMode(next: typeof mode) {
    setMode(next); setError(""); setMessage(""); setPassword(""); setConfirm(""); setShowPassword(false);
  }

  async function verifyAndContinue() {
    try { await api.account(); }
    catch (e) { await signOut().catch(() => undefined); setToken(null); throw e; }
    router.replace("/");
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      if (mode === "signup" && password !== confirm) throw new Error("Your passwords don’t match. Please check them and try again.");
      const auth = authClient();
      if (!auth) {
        if (!localAuthEnabled()) throw new Error("Account sign-in is not configured yet. Please contact the administrator.");
        const response = await fetch(`/api/v1/auth/${mode === "signup" ? "signup" : "login"}`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username: username.trim(), password, remember }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data?.error?.message ?? (typeof data?.detail === "string" ? data.detail : "Could not sign in. Please try again."));
        setToken(LOCAL_SESSION);
        await verifyAndContinue();
        return;
      }
      const callback = window.location.origin + "/auth/callback";
      if (mode === "recover") {
        const { error } = await auth.auth.resetPasswordForEmail(username.trim(), { redirectTo: callback + "?next=/account/password" });
        if (error) throw error;
        setMessage("If that email has an account, a password reset link will arrive shortly.");
      } else if (mode === "signup") {
        const { data, error } = await auth.auth.signUp({ email: username.trim(), password, options: { emailRedirectTo: callback } });
        if (error) throw error;
        if (data.session) await verifyAndContinue();
        else setMessage("Check your email for the confirmation link, then sign in.");
      } else {
        const { error } = await auth.auth.signInWithPassword({ email: username.trim(), password });
        if (error) throw error;
        await verifyAndContinue();
      }
    } catch (e) { setError(e instanceof Error ? e.message : "Sign-in failed. Please try again."); }
    finally { setBusy(false); }
  }

  async function developerLogin(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try { setToken(token.trim()); await verifyAndContinue(); }
    catch (e) { setError(e instanceof Error ? e.message : "Developer sign-in failed."); }
    finally { setBusy(false); }
  }

  return <div className="min-h-screen bg-[#f8f9f5] text-[#172b24] lg:grid lg:grid-cols-[1fr_1fr]">
    <aside className="relative hidden overflow-hidden bg-[#102c25] px-12 py-10 text-[#eef5e8] lg:flex lg:min-h-screen lg:flex-col xl:px-20">
      <Link href="/login" className="flex w-fit items-center gap-3 text-2xl font-semibold tracking-tight"><span className="text-[#b7d98b]"><Mark /></span>mastrr<span className="text-[#b7d98b]">.</span></Link>
      <div className="relative z-10 my-auto py-16">
        <div className="mb-7 flex items-center gap-2.5 text-[11px] font-semibold tracking-[0.2em] text-[#c1d0bf]"><span className="h-1.5 w-1.5 rounded-full bg-[#b7d98b]" /> YOUR NEXT STEP STARTS HERE</div>
        <h2 className="max-w-lg text-[clamp(2.8rem,4.6vw,4.8rem)] leading-[1.08] font-medium tracking-[-0.055em]">Less guessing.<br />More <span className="font-serif italic text-[#c5e6a2]">understanding.</span></h2>
        <p className="mt-7 max-w-sm text-base leading-7 text-[#afc2b6]">Find the gaps. Work through the why.<br />Build the confidence to solve it on your own.</p>
        <div aria-hidden="true" className="relative mt-12 max-w-sm rounded-2xl border border-white/10 bg-white/[0.035] p-6">
          <div className="mb-6 flex items-center justify-between"><span className="text-xs tracking-wide text-[#b7c8bc]">A clearer way forward</span><span className="rounded-full bg-[#b7d98b]/10 px-2.5 py-1 text-[10px] text-[#c5e6a2]">YOUR LEARNING LOOP</span></div>
          {[['01', 'Understand your starting point', 'A short, focused diagnostic'], ['02', 'Make the method click', 'Explanations for your mistakes'], ['03', 'Try it on your own', 'Fresh questions. Independent checks.']].map(([number, title, caption], i) => <div key={number} className="relative flex gap-4 pb-6 last:pb-0">
            {i < 2 && <span className="absolute top-8 left-4 h-10 w-px bg-white/15" />}
            <span className={`z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-[10px] ${i === 1 ? 'border-[#c5e6a2] bg-[#c5e6a2] text-[#102c25]' : 'border-white/20 bg-[#19372d] text-[#b4c8b7]'}`}>{number}</span>
            <div><p className="text-sm font-medium">{title}</p><p className="mt-1 text-xs text-[#a2b7a8]">{caption}</p></div>
          </div>)}
        </div>
      </div>
      <div className="flex items-center gap-3 text-[11px] tracking-wide text-[#9bb09f]"><span className="h-px w-6 bg-[#849b7d]" /> SMALL STEPS. STRONGER FOUNDATIONS.</div>
      <div aria-hidden="true" className="pointer-events-none absolute -right-52 -bottom-64 h-[650px] w-[650px] rounded-full border border-[#b7d98b]/10" />
    </aside>

    <section className="flex min-h-screen flex-col px-6 py-7 sm:px-12 lg:px-14 xl:px-24">
      <div className="flex items-center justify-between lg:justify-end">
        <Link href="/login" className="flex items-center gap-2 text-xl font-semibold tracking-tight lg:hidden"><Mark />mastrr.</Link>
        <Link href="/privacy" className="text-xs text-[#687a70] hover:text-[#245a43]">Privacy & your data <span aria-hidden="true">↗</span></Link>
      </div>
      <div className="mx-auto my-auto w-full max-w-[400px] py-12">
        <p className="mb-4 text-[11px] font-semibold tracking-[0.18em] text-[#508166]">A LITTLE PROGRESS, EVERY DAY</p>
        <h1 className="text-[38px] leading-tight font-semibold tracking-[-0.045em] sm:text-[42px]">{mode === "signup" ? "Make room to grow." : mode === "recover" ? "Let’s get you back in." : "Welcome back."}</h1>
        <p className="mt-3 text-sm leading-6 text-[#758278]">{mode === "signup" ? "Create an account. Your learning journey starts with you." : mode === "recover" ? "Enter your email and we’ll send you a reset link." : "Your next breakthrough is one step away."}</p>

        {mode !== "recover" && <div className="mt-8 grid grid-cols-2 rounded-xl bg-[#edf0e9] p-1" aria-label="Account access">
          {(["login", "signup"] as const).map(item => <button type="button" key={item} disabled={busy} aria-pressed={mode === item} onClick={() => changeMode(item)} className={`rounded-lg py-2.5 text-sm font-medium transition ${mode === item ? 'bg-white text-[#204a36] shadow-sm' : 'text-[#778578] hover:text-[#204a36]'}`}>{item === "login" ? "Sign in" : "Create account"}</button>)}
        </div>}

        <form onSubmit={e => void submit(e)} className="mt-7 space-y-5" aria-label={mode === "signup" ? "Create account" : mode === "recover" ? "Reset password" : "Sign in"}>
          <label className="block text-sm font-medium">{hosted ? "Email address" : "Username"}
            <input name="username" type={hosted ? "email" : "text"} autoComplete={hosted ? "email" : "username"} autoCapitalize="none" spellCheck={false} required maxLength={hosted ? 254 : 32} disabled={busy} value={username} onChange={e => setUsername(e.target.value)} placeholder={hosted ? "you@example.com" : "Enter your username"} className={input} />
            {!hosted && mode === "signup" && <span className="mt-2 block text-xs font-normal text-[#758278]">3–32 characters. Letters, numbers, dots, hyphens or underscores.</span>}
          </label>
          {mode !== "recover" && <div>
            <div className="flex items-center justify-between"><label htmlFor="account-password" className="text-sm font-medium">Password</label>{hosted && mode === "login" && <button type="button" disabled={busy} onClick={() => changeMode("recover")} className="text-xs font-medium text-[#286b50] hover:underline">Forgot password?</button>}</div>
            <div className="relative"><input id="account-password" name="password" type={showPassword ? "text" : "password"} autoComplete={mode === "signup" ? "new-password" : "current-password"} required minLength={mode === "signup" ? 12 : 1} maxLength={128} disabled={busy} value={password} onChange={e => setPassword(e.target.value)} placeholder={mode === "signup" ? "Create a strong password" : "Enter your password"} className={input + " pr-16"} />
              <button type="button" aria-label={showPassword ? "Hide password" : "Show password"} aria-pressed={showPassword} onClick={() => setShowPassword(!showPassword)} className="absolute inset-y-0 right-4 my-auto h-8 text-xs font-medium text-[#687a70] hover:text-[#245a43]">{showPassword ? "Hide" : "Show"}</button></div>
            {mode === "signup" && <p className="mt-2 text-xs text-[#758278]">Use at least 12 characters.</p>}
          </div>}
          {mode === "signup" && <label className="block text-sm font-medium">Confirm password<input type="password" autoComplete="new-password" required disabled={busy} value={confirm} onChange={e => setConfirm(e.target.value)} className={input} placeholder="Enter your password again" /></label>}
          {!hosted && mode !== "recover" && <label className="flex items-center gap-2.5 text-xs text-[#687a70]"><input type="checkbox" checked={remember} disabled={busy} onChange={e => setRemember(e.target.checked)} className="h-4 w-4 accent-[#286b50]" />Keep me signed in for 7 days</label>}
          {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm leading-5 text-red-800">{error}</p>}
          {message && <p role="status" className="rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm leading-5 text-green-800">{message}</p>}
          <button type="submit" disabled={busy} className="flex w-full items-center justify-center gap-3 rounded-xl bg-[#245c43] px-5 py-3.5 text-sm font-semibold text-white shadow-[0_4px_10px_#245c4318] transition hover:bg-[#194932] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#286b50]">{busy ? "Please wait…" : mode === "signup" ? "Create your account" : mode === "recover" ? "Send reset link" : "Sign in to Mastrr"}{!busy && <Arrow />}</button>
        </form>
        {mode === "recover" ? <button onClick={() => changeMode("login")} className="mt-6 text-sm text-[#286b50] hover:underline">← Back to sign in</button> : <p className="mt-6 text-center text-xs text-[#7b877d]">{mode === "signup" ? "Already have an account?" : "New here?"} <button disabled={busy} onClick={() => changeMode(mode === "signup" ? "login" : "signup")} className="font-semibold text-[#286b50] hover:underline">{mode === "signup" ? "Sign in" : "Create an account"}</button></p>}
        {!hosted && <p className="mt-7 text-center text-[11px] leading-5 text-[#89948b]">Accounts on this device are saved to this local server.<br />Use the same server to return to your progress.</p>}
        {!hosted && <details className="mt-8 border-t border-[#e1e6dc] pt-4 text-xs text-[#89948b]"><summary className="w-fit cursor-pointer hover:text-[#245c43]">Developer access</summary><form onSubmit={e => void developerLogin(e)} className="mt-4 space-y-3"><label className="block">Local development token<input type="password" required disabled={busy} value={token} onChange={e => setLocalToken(e.target.value)} className={input} /></label><button disabled={busy} className="rounded-lg border border-[#cbd5c7] px-4 py-2 text-[#245c43]">Use developer token</button></form></details>}
      </div>
      <footer className="flex items-center justify-between text-[10px] text-[#919d92]"><span>© {new Date().getFullYear()} Mastrr</span><span>Learn with intention.</span></footer>
    </section>
  </div>;
}
