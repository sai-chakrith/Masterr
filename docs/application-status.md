# Application status — 27 October 2026

Mastrr now has an integrated **15-topic pilot application**. It is ready for
service configuration and human content publication, not yet for a public learner
launch. The original report's 35-topic scope is not claimed as delivered.

## Implemented

- Goals and prerequisite roadmap; diagnosis, personal tutoring, adaptive practice,
  independent retest, scheduled review and saved history.
- Official Supabase client integration for signup, email confirmation, login,
  session refresh, password recovery/change and sign-out. Local token mode is
  explicitly enabled on localhost only; the production API rejects it.
- Reviewer access controlled by verified subject allowlist, with immutable content
  versions, explicit approval, concurrent-edit protection, withdrawal and reports.
  Runtime database publications override original draft files.
- Assessment changes withhold affected current results and suggest rechecking,
  while preserving the original attempts. Old pending reviews are superseded
  after a new retest passes.
- Timed mixed-topic practice, server deadlines, delayed result disclosure and
  durable family reservations. Timed practice never issues mastery decisions;
  its completed mistakes can be revisited in the personal tutor.
- Ownership-protected data export, validation-key redaction, deletion of owned
  learning data and personal caches, stale-token tombstones and retryable hosted
  identity deletion.
- Shared-database request/model budgets, bounded bodies, request IDs, safe request
  logging, health/readiness endpoints, backup/restore tooling, container packaging
  and CI configuration, including PostgreSQL browser-role isolation checks.
- Fifteen original notes drafts, a profile-authoring example, and 135 additional
  draft retention questions. The complete source bank has 1,272 drafts. All remain
  unpublished pending genuine content review; no reviewer was invented.

## Verified locally

- Full real-pytest suite: **211 passed**, with one existing Starlette/httpx
  deprecation warning.
- Clean locked frontend installation using npm 10: passed.
- TypeScript and Next.js production build: passed for all application routes.
- SQLite schema upgrade/downgrade/re-upgrade and preserved-row checks: passed.
- PostgreSQL migration SQL generation, including RLS restrictions: passed.
- SQLite backup and independent restore checks: passed. The existing local
  database was backed up, migrated and imported without approving content.
- Current local database doctor: connected, migrations current, no approved
  questions or curriculum, no Groq/hosted-auth configuration or reviewer grants.
- Docker Compose configuration validation: passed with explicitly synthetic
  configuration values. This did not start containers or provision accounts.
- Playwright: **seven passed, one intentionally skipped**. The full stateful
  diagnosis-to-review-scheduling journey ran once on desktop. Reviewer publication,
  timed practice, account export, layout and sign-out ran on desktop and an
  emulated Pixel 7 viewport. The duplicate mobile full-journey case was skipped;
  this is not a claim of testing on a physical phone or against hosted accounts.

The browser fixture uses a new isolated synthetic database, fake test identities and no paid
provider calls. Its approvals and scores are never real learner evidence.

The recording launcher also creates an isolated, visibly labelled sample database,
without changing the normal database or approving source drafts. Its browser check
passed for sign-in, the demo banner, both fallback tutoring panels and continuing
into practice. Five additional tests cover environment loading, database isolation
and sanitised provider errors. See [recording instructions](recording-demo.md).
Live Groq verification remains pending a replacement private key; the exposed key
was not saved or used.

## Owner and reviewer actions still required

1. Create Supabase, SMTP, database and hosting resources; configure the real
   settings and verified reviewer subjects. No services were provisioned because
   the owner requested deployment preparation and instructions instead.
2. Review and publish one complete pilot topic: methods, examples, notes,
   questions, distractors, genuine family separation, difficulty and review facets.
   Mathematical validation and generated labels are not independent review.
3. Verify actual signup, email confirmation, refresh, recovery, sign-out and
   deletion against the hosted project, using two real test accounts for isolation.
4. Run the live Groq smoke check, inspect actual reasoning and record real
   usage/latency. The 120b-versus-20b comparison remains unrun; no model switch
   or model-quality result is claimed.
5. Start Docker or use the intended hosting platform, execute the PostgreSQL
   runtime/isolation checks and perform a hosted restore drill. Docker's engine
   was unavailable locally, so container and hosted runtime success is unverified.
6. Publish operator contact, backup-retention and consent arrangements; recruit
   consenting learners and execute the pilot. No learning gains or calibrated
   mastery claim follows from these software checks.
7. Agree official exam mappings and remaining curriculum coverage. The example
   arithmetic profile is a draft, not a verified external syllabus.

See [deployment and review instructions](deployment.md) for the exact commands,
environment settings, reviewer workflow, safeguards and release checks.
