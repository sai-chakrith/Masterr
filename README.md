# Mastrr

Aptitude learning with diagnosis, topic notes, personal tutoring, adaptive practice,
independent retests and scheduled reviews. The current curriculum covers 15 topics.

## Implemented application

- Next.js learner roadmap, goals, lessons, personal tutor, persistent sessions and history.
- Supabase email signup, confirmation, login, refresh, password recovery and sign-out.
- FastAPI ownership checks, immutable question versions, deterministic arithmetic grading,
  diagnostic/retest policies, transparent progress and fresh-family reservations.
- Topic-scoped RAG tutoring with caches, bounded retries, final-answer checks, labelled
  fallbacks, recorded usage and per-user/shared provider budgets.
- Timed mixed-topic practice with server deadlines and results withheld until completion.
  Timed practice does not change mastery decisions.
- Reviewer console for curriculum, notes, profiles, misconceptions, question editing,
  explicit publication, withdrawal and learner reports. Changes have versioned audit records.
- Private data export, account deletion, stale-assessment handling, request limits,
  readiness checks, safe request logging, backup/restore verification and deployment files.

## Run locally

Install Python 3.12 and Node 22 or newer. Create `.venv`, install
`requirements.lock.txt`, and run `npm ci` inside `frontend/`.
Then run `scripts/start-local.ps1` and `scripts/start-frontend.ps1` in separate
terminals. Open [the local app](http://127.0.0.1:3000), sign in with the ignored
`data/local-api-token`, and choose a goal.

The local launcher defaults to the new scoring policy. Pilot assignments can still
select the legacy policy explicitly. Local reviewer access requires setting
`MASTRR_ADMIN_SUBJECTS=local-developer` before starting the API.

## Content and launch status

**This is not a published learner service yet.** The source bank contains 1,272
unapproved drafts, including 135 retention-review items. Curriculum, notes,
misconceptions and exam mappings need genuine content review. The app intentionally
refuses to serve drafts; test-fixture approvals are never imported into real data.
A mathematically checked parameter variation is not proof of independent family
coverage or learning effectiveness.

Database-backed reviewer publications are used at runtime. Source files remain
editable drafts; do not confuse their status with a reviewed live database.
Supabase, SMTP, Groq and hosting need owner configuration. No accounts, deployment,
real learner outcomes or live model quality are claimed by the source code.

Read [the deployment and review runbook](docs/deployment.md) for exact setup,
publication, security, backup and pilot steps. [Tutor v2](docs/tutor-v2.md) records
the tutoring design and its original verification snapshot.

## Checks

```text
python -m pytest -q
cd frontend
npm ci
npm run typecheck
npm run build
npx playwright install chromium
npm run test:e2e
```

For browser tests, build with `NEXT_PUBLIC_LOCAL_DEVELOPMENT=1` and
`MASTRR_API_ORIGIN=http://127.0.0.1:8765`. Playwright starts a separate loopback API
on 8765 and frontend on 3765, creates a new guarded synthetic database in `.e2e/`,
and makes no paid provider calls. It never uses the normal development database.
See the GitHub workflow for the Linux setup. Use a fresh workspace-local pytest
`--basetemp` and `-s` if Windows sandbox output capture or temp paths fail.

The CI workflow includes PostgreSQL migration and public-role isolation checks.
Docker runtime verification requires a running Docker engine. Hosted account,
email and Groq checks require real configured services.
