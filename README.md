# Mastrr

Aptitude and reasoning preparation, beginning with a complete Numbers learning loop.

## Built so far

The first backend foundation is implemented with FastAPI, SQLAlchemy, and Alembic:

- Durable sessions, fixed question versions, saved working, and server-side integer scoring.
- Recorded family reservations, prompt exposure, hints, and solution exposure.
- Three-facet independent checks with results withheld until the form ends.
- Help converts a check to assisted practice before releasing the hint or solution.
- Idempotent submissions, ownership checks, and serialized learner operations.
- Evidence events and review records scheduled two and seven days after a passed check.
- Resume, abandon, due-review inspection, and fresh-content exhaustion responses.
- Explicit single-developer local authentication; Supabase asymmetric JWT verification support.
- An idempotent importer preserving the twelve original questions as drafts.

This is a backend milestone, not a complete student application. The frontend,
adaptive teaching, reasoning AI, reviewer UI, correction/recomputation workflow,
and public deployment remain to be built. The provisional policy describes
performance on a small check, not calibrated mastery or placement readiness.

All supplied questions still await genuine human review. Student sessions
currently return insufficient coverage. Approved fixtures exist only inside tests;
they are not imported by startup and are not approved learning material.

## Local setup

Use Python 3.12 and uv. From the repository root:

~~~powershell
uv venv --python 3.12 .venv
uv pip sync --python .venv/Scripts/python.exe requirements.lock.txt
.\scripts\start-local.ps1
~~~

The launcher migrates the local database, imports drafts without publishing them,
creates a local API token if needed, and starts on http://127.0.0.1:8000.
API documentation is at http://127.0.0.1:8000/docs.

The token lives in ignored data/local-api-token. Supply it through the
Authorization header as Bearer followed by the token. Never publish local mode
or share that token. Startup does not load .env files automatically; .env.example
documents environment variables.

~~~powershell
$headers = @{ Authorization = 'Bearer ' + (Get-Content data/local-api-token -Raw).Trim() }
Invoke-RestMethod http://127.0.0.1:8000/v1/me/today -Headers $headers
~~~

To use PostgreSQL, configure DATABASE_URL as a postgresql+psycopg URL and run the
same migrations. Before multi-user use, disable local development, configure
SUPABASE_URL with asymmetric signing keys, use a restricted database role, deny
browser database access, and complete deployment/isolation verification.
No real Supabase project has been provisioned or verified yet.

## Checks

~~~powershell
New-Item -ItemType Directory .test-tmp -Force | Out-Null
.venv/Scripts/python.exe -m pytest -q --basetemp=.test-tmp/current
.venv/Scripts/python.exe -m backend.numbers
~~~

The tests use synthetic fixtures to exercise the complete deterministic flow.
They cover persistence, grading, public payloads, assistance, cross-user isolation,
concurrent/replayed submissions, actual due dates under a test clock, exhausted
families, JWT verification, and migration upgrade/downgrade. Test-clock reviews
verify software behavior; they do not measure student retention.

SQLite is the local/test fallback. PostgreSQL migration SQL compilation is tested;
live PostgreSQL integration and concurrency are not verified on this machine.

## API outline

| Method | Path | Purpose |
| --- | --- | --- |
| GET | /health | Process health and AI availability |
| GET | /v1/me/today | Active session, reviews, evidence |
| POST | /v1/sessions | Start diagnostic, practice, verification, or due review |
| GET | /v1/sessions/{id} | Resume and issue current public question |
| POST | /v1/sessions/{id}/abandon | End session without reclaiming reserved families |
| POST | /v1/assignments/{id}/submit | Submit using an Idempotency-Key header |
| POST | /v1/assignments/{id}/help | Release reviewed hint or solution with exposure recorded |

Independent checks currently cover divisibility only and require approved basic,
combined, and constraints facets from distinct unseen families. Direct challenge
checks are allowed. Prerequisite diagnostics and automatic teaching routes are
not yet integrated. Diagnostic/practice sessions currently contain one question;
the next milestone connects these into the adaptive student journey.

## Project records

- [Selected stack](docs/tech-stack.md)
- [Current build status](docs/build-status.md)
- [First learning-loop plan](docs/first-learning-loop-plan.md)
- [Longer implementation plan](docs/implementation-plan.md)
