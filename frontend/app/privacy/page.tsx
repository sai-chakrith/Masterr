import Link from "next/link";
export default function DataUsePage() {
  return <article className="space-y-5 leading-7">
    <h1 className="text-3xl font-semibold">Your data in Mastrr</h1>
    <p>Mastrr stores your sign-in identifier, chosen goals, question attempts, optional working, hints used, session times, learning estimates and tutor explanations. These records support your learning route and independent checks.</p>
    <h2 className="text-xl font-semibold">AI explanations</h2>
    <p>When hosted AI tutoring is enabled, Groq receives topic notes and up to three completed missed questions with your recorded answers. Your account identifier and optional working are not sent. Avoid putting identifying information in an answer. Final answers are checked against the bank; generated working may still contain mistakes.</p>
    <h2 className="text-xl font-semibold">Accounts and controls</h2>
    <p>Hosted sign-in is provided by Supabase. In Account you can download your learning records and request deletion. Validation answer keys are excluded from exports. Deletion removes learning records and personal tutor caches and disables the identity. A minimal deletion record prevents an old token from recreating your account. Published content-review attribution remains in the audit history.</p>
    <h2 className="text-xl font-semibold">Operational copies</h2>
    <p>Administrators control hosting, backups and the retention period for backup copies. Before a public or research pilot, the operator must publish its contact details, retention schedule and any study-specific consent information. The software does not claim that a running score proves mastery or placement readiness.</p>
    <p><Link href="/account" className="underline">Open account controls</Link></p>
  </article>;
}
