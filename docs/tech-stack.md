# Technology decision: Mastrr first release

Date: 2026-10-23. Selected under the user's instruction to decide the stack.
This decision supersedes earlier stack-pending language. It does not provision
services, purchase subscriptions, or claim implementation is complete.

| Layer | Selected technology |
| --- | --- |
| Frontend | Next.js App Router, React, TypeScript |
| Styling and components | Tailwind CSS, shadcn/ui |
| Math rendering | KaTeX |
| Skill graph | React Flow, added at the evidence-map milestone |
| Backend | Python 3.12, FastAPI, Pydantic |
| Database access and migrations | SQLAlchemy 2, psycopg 3, Alembic |
| Durable data | PostgreSQL; Supabase-managed PostgreSQL for the hosted pilot |
| Authentication | Supabase Auth; email/password first |
| AI integration | Backend-only hosted-model adapter; model selected on the reviewed evaluation set before student use |
| Correctness | Existing explicit Python mathematical validators and reviewed answer keys; SymPy only where needed |
| Backend verification | pytest, retaining the existing unittest suite |
| Browser verification | Playwright for the critical learning journey |
| Local tooling | npm with package-lock.json; Python venv with pinned dependencies; local PostgreSQL |

## Why this stack

Keep the existing Python content and validation work and build learning rules
in one modular FastAPI application. Use the React frontend for sessions and the
skill map. PostgreSQL holds relational content, immutable attempts, review
records, and schedules. Managed authentication avoids building password flows.
No separate graph database is needed: store prerequisites as relational edges.

FastAPI is the authority for assignments, answer release, scoring, evidence,
review scheduling, content approval, and AI requests. Next.js handles UI and
session integration, not a second implementation of learning rules.

The browser signs in through Supabase Auth and sends an access token to the API.
The API verifies signature, issuer, audience, expiry, and learner ownership.
Use a restricted direct database role for application queries and enforce
ownership explicitly; direct SQLAlchemy connections do not inherit the browser's
Supabase RLS context. Keep private answer/content tables outside exposed Data API
schemas, or disable the Data API for application data. Privileged credentials
stay on the server. Test cross-user isolation before the multi-user pilot.

Local development uses PostgreSQL, with Supabase Auth configured before the
multi-user milestone. PostgreSQL/Supabase can also run locally if the required
container runtime is available; inspect the machine before choosing setup.
No public hosting is necessary to demonstrate the first loop.

Persist due reviews as rows and fetch them on login/session start; do not add a
worker merely to show due reviews. Add a PostgreSQL-backed worker only when
background generation or ingestion requires durable jobs. No Redis, Celery,
vector database, custom model training, or agent framework in the first loop.
Use reviewed lessons when AI is unavailable. Provider/model evaluation remains
a quality gate, not an unresolved choice of application architecture.

OCR and public hosting remain later milestones. Select their concrete engines
and providers against real pages, deployment needs, and budget at that time.
Pin exact compatible package versions and runtimes during scaffolding, commit
lockfiles, and avoid claiming unverified latest release numbers in this record.

## Official references checked

- https://nextjs.org/docs/app/getting-started/installation
- https://fastapi.tiangolo.com/tutorial/sql-databases/
- https://supabase.com/docs/guides/auth
- https://supabase.com/docs/guides/database/secure-data
