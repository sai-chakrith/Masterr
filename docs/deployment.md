# Run and deploy Mastrr

This release implements the application flows, but a deployment, real hosted
accounts, reviewed content and a real learner pilot have not been provisioned.
Use this guide to configure them. Never substitute invented credentials or
reviewer names just to make a readiness check pass.

## Local application

Install Python 3.12, Node 22 or newer, and the locked dependencies:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.lock.txt
cd frontend
npm ci
cd ..
```

Run `scripts/start-local.ps1` and, in another terminal,
`scripts/start-frontend.ps1`. The API binds to loopback on port 8000, and the
frontend runs on port 3000. The local token is in ignored `data/local-api-token`.
The launchers explicitly enable local development; local sign-in is refused on
a public hostname. New sessions use the `new` scoring policy in the launcher;
existing per-learner pilot assignments still take precedence.

To review content locally, set `MASTRR_ADMIN_SUBJECTS=local-developer` in the API
terminal before starting it. This is an explicit local-only reviewer grant, not
a production default. The software has no built-in administrator password.

The Python API does not automatically load `.env` files. Export backend variables
into the process environment. Next.js reads its own `frontend/.env.local`; copy
from `frontend/.env.example` for local development. Do not commit local env files.

## Create the hosted services

1. Create a dedicated Supabase project for authentication. Enable email signup
   and email confirmation. Configure a real SMTP sender, password requirements,
   email rate limits and the production site URL.
2. Use an asymmetric Supabase signing key supported by the API (ES256 or RS256).
   The API verifies signature, issuer, audience, expiry and subject using the
   project's JWKS endpoint. Legacy HS256 secrets are not accepted.
3. Configure an exact redirect allowlist containing the frontend's
   `/auth/callback` and `/auth/callback?next=/account/password` URLs. Avoid wildcard
   production redirect origins. Browser PKCE links normally return to the browser
   that initiated signup or recovery. For cross-device email links, configure
   Supabase email templates to return a `token_hash` with `type=signup` or
   `type=recovery` to `/auth/callback`; the callback supports both flows.
4. Provision PostgreSQL, either in the Supabase project or separately. Use TLS
   for a hosted database connection. Use a dedicated backend database/table-owner
   role instead of exposing a shared project superuser credential. The backend
   role must own the application tables (RLS without policies denies non-owner
   roles); no browser role is supposed to query these tables directly.
5. Put `SUPABASE_URL`, `DATABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` and optional
   `GROQ_API_KEY` in the backend secret store. The service-role key is used only
   for hosted identity deletion, never exposed to the browser.
6. Set `LOCAL_DEVELOPMENT=0`, `MASTRR_ENV=production`, and
   `MASTRR_DEFAULT_SCORING_VERSION=new`. Production refuses local token auth.
7. Build the frontend with `NEXT_PUBLIC_LOCAL_DEVELOPMENT=0`,
   `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, and
   `MASTRR_API_ORIGIN` pointing to the API's private origin. The Supabase
   publishable key is public; the service-role and Groq keys must never use a
   `NEXT_PUBLIC_` variable. These public settings and the rewrite destination are
   build-time values: rebuild when changing them.

The browser uses the official Supabase client for signup, confirmation, password
login, refresh, recovery and sign-out. Its session is stored in browser storage.
Client route guards are only a convenience; every backend request independently
verifies the bearer token and enforces learner ownership. No Supabase Data API
queries are made by the app. See the official
[Supabase password flow](https://supabase.com/docs/guides/auth/passwords) and
[JavaScript authentication reference](https://supabase.com/docs/reference/javascript/auth).

## Containers or separate hosting

The root Dockerfile builds the API; `frontend/Dockerfile` builds the frontend.
`compose.yaml` includes PostgreSQL with a persistent volume, a separate migration
and draft-import job, the API and frontend. It deliberately requires real hosted
auth configuration. Supply a strong **URL-safe** `POSTGRES_PASSWORD`, the two
public Supabase settings, backend secrets, and reviewer subjects in the hosting
secret store before running:

```text
docker compose config --quiet
docker compose up --build -d
```

The frontend listens on `127.0.0.1:3000` on the host. Place an HTTPS reverse proxy
in front of it. PostgreSQL and the API have no public host ports. The API's
`/ready` health check requires a reachable database and the current migration;
`/health` is liveness only. An empty/draft bank does not make infrastructure
unhealthy: reviewers must be able to sign in before content is published.

For separate hosting, deploy the API Dockerfile to your container host and the
Next.js app to a Node/Next-compatible host. Configure the private API rewrite
origin, run migrations and seed import as a release job, and configure HTTPS.
Choose the hosting provider yourself; no paid resources are provisioned here.
Do not run tests that generate synthetic approvals against production.

Schema changes run through Alembic, not automatic API startup DDL. Use
`python -m alembic upgrade head`; the learning and tutoring migration branches
are now merged. Do not reset or reseed a live database as a substitute for a
migration. The idempotent seed command imports original drafts and preserves
database-created reviewed versions.

PostgreSQL migrations enable row-level security on application tables and revoke
public/`anon`/`authenticated` table access. This prevents Supabase's Data API from
bypassing FastAPI ownership checks or exposing answer keys. Do not add permissive
browser policies to these tables. Security restrictions are intentionally not
removed by a feature downgrade. Supabase explains why SQL-created tables need
explicit protection in [Securing your API](https://supabase.com/docs/guides/api/securing-your-api).

## Review and publish a pilot topic

After a real reviewer creates an account, put their **verified Supabase subject
UUID** in `MASTRR_ADMIN_SUBJECTS` and restart the API. Ordinary learners cannot
grant themselves this role through a request body or user metadata.

In **Account → Open content review**:

1. Review curriculum lessons and full/half-worked examples. Save any edits as a
   draft, read the saved version, explicitly confirm personal review and publish.
2. Review notes for the pilot topic. Notes remain topic-scoped; the original 15
   drafts are in `reference/tutor-notes-v2/`.
3. Review misconception definitions before approving MCQ items that reference
   them. Corrections to a published definition require a new ID to preserve
   historical feedback. Withdrawing definitions suspends dependent items.
4. Review each required question's wording, method, arithmetic, difficulty,
   distractors and family. The original drafts are mathematically checked but
   not independently reviewed. Parameter changes alone do not establish that
   two questions are independent evidence; merge/rewrite family IDs as needed
   and supply genuinely distinct content when required.
5. Publish enough fresh visible assessment items for an 8–12-question diagnostic
   plus a ten-question retest, practice items for multiple ten-question blocks,
   and **nine review items**, three per coverage facet, for the three scheduled
   retention checks. Reserve hidden validation forms separately for the research
   pilot. The bank now includes draft retention items; their facet labels and
   difficulty still need human review.
6. Author a reviewed profile or use direct topic selection. A draft profile
   example is in `content/numbers/exam-profile-template.json`; it is not mapped
   to an official exam syllabus and is never automatically published.

The implemented review intervals are three days after passing the independent
check, seven days after passing the first review, and 21 days after passing the
second review. They are provisional policy settings, not evidence of retention.

Each change creates a new version and audit event. Publishing is protected by a
checksum so concurrent reviewers cannot approve a stale version. Editing a
published question suspends that item until its new draft is reviewed. Editing
a document draft leaves the previous published document available until a new
publication or withdrawal. Runtime database publications override seed files;
do not mix the older file-editing CLIs with live database versioning without
exporting and reconciling versions first. A reviewed database backup includes
the complete publication and audit history.

When an assessed question changes or is withdrawn, its old attempt is retained,
but the affected current result/score is withheld and a fresh retest is suggested
when enough reviewed families exist. Historical attempts are never silently
regraded against a different prompt. Passing a new retest starts a new review
cycle and supersedes older pending review reminders.

## Tutor limits and observability

Backend environment settings:

- `MASTRR_API_REQUESTS_PER_MINUTE=120` per authenticated identity.
- `MASTRR_TUTOR_DAILY_CALLS=60` actual provider attempts per identity.
- `MASTRR_TUTOR_DAILY_TOKEN_BUDGET=120000` reserved maximum completion tokens per
  identity per UTC day; retries count and failures retain their reservation.
- `MASTRR_TUTOR_GLOBAL_TOKEN_BUDGET=1000000` shared daily completion reservation.

These are shared-database limits, so extra API workers do not multiply them.
Cached visits use no provider calls. Exhaustion returns honest notes/answer
fallbacks. The token reservation is a conservative completion limit, not a dollar
bill estimate or a cap on prompt tokens. Input is bounded by reviewed notes,
selected questions, the body limit and the call limit. Review real provider usage
and set provider-side account spending controls before public signup.

Request bodies are limited to one MiB. API responses carry a generated request
ID and no-store headers. The production logging configuration records request
ID, route template, status and elapsed time; it omits query strings, credentials,
request bodies and answers. Collect these logs in your hosting monitor and alert
on sustained 5xx responses, `/ready` failures, repeated fallback/quota errors and
provider account spend. No monitoring account has been provisioned.

Run `python -m scripts.operations doctor` for infrastructure/content flags; it
prints no secret values. The tutor smoke and model-comparison tools remain
available as described in `docs/tutor-v2.md`. A live Groq call and human read of
outputs must succeed before claiming model quality or measured savings.

## Account data and deletion

Account export includes only the signed-in learner's records. It is blocked
during unfinished activities, and completed validation correctness is redacted.
Deletion removes learning records, reports and the owner's personal explanation
caches, then disables the hosted identity. A minimal tombstone rejects old access
tokens. Public topic lessons and reviewer attribution are retained.

If hosted identity deletion fails after local deletion, the tombstone remains
and sign-in stays blocked. Retry through the reviewer endpoint
`POST /v1/admin/deletions/retry` or the operator command
`python -m scripts.operations retry-deletions`. Missing service-role configuration
rejects a hosted deletion before removing data. Never log that key. Local mode
uses one fixed identity: deleting it deliberately disables that local account;
use a fresh development database to start again.

Before recruiting learners, publish the operator's real contact details, a backup
retention policy and any study consent. `/privacy` describes the implemented data
flow; it does not substitute for the operator's real arrangements.

## Backups, release checks and pilot

For SQLite, run `python -m scripts.operations backup-sqlite --out backups/NEW.db`.
It uses SQLite's backup API, verifies integrity, restores into a separate in-memory
database, and checks foreign keys. Existing files are never overwritten. For
PostgreSQL use the host's managed backup service or `pg_dump` in custom format,
then restore to a **separate** database with `pg_restore` and run migrations,
readiness and ownership checks against the restored copy. Do not test restoration
over the live database. Encrypt backups and restrict access because they contain
learning records. Run the restore drill on the actual hosting platform; it has
not been performed for a hosted service here.

The GitHub workflow runs pytest, TypeScript, a production build, isolated desktop
and mobile browser checks, and PostgreSQL migration/public-role isolation checks.
It will run remotely only after these commits are pushed to GitHub.

Before a real pilot: complete signup/confirmation/recovery on actual SMTP, test
two accounts for isolation, run the Groq smoke check, read real explanations on
five topics, exercise correction and withdrawal, test interruption/resume and
network errors on mobile, verify due reviews with a controlled test clock, and
verify the backup restore. Recruit real consenting learners and record actual
pilot outcomes. Test-fixture approvals and simulated scores are never learner
evidence. The 35-topic proposal is not fulfilled by the current 15-topic bank;
remaining curriculum scope and reviewed content are separate authoring work.
