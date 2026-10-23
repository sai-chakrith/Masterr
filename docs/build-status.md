# First backend milestone

Updated 23 October 2026.

The user authorized starting implementation after reviewing the higher-model
response. This record supersedes older statements that no API or persistence
exists. The selected stack stays in force. SQLite is an explicit local/test
fallback because the local PostgreSQL/container service is unavailable.

## Implemented

Persistent authenticated session endpoints, fixed-version assignment, original
draft import, integer scoring, assistance snapshots, conservative family
reservation, transactional submission, learner ownership checks, evidence events,
two due-review records after a passed independent form, resume and abandon.
Local development uses one explicit secret token mapped to one developer identity.
Supabase asymmetric JWT validation is implemented and tested with local signed
tokens and mocked key discovery; live account integration is not completed.

Three-facet forms cover basic, combined, and constraints tasks. Each facet needs a
different unseen family. Direct challenge checks are allowed. Help ends the
independent form and cancels its remaining questions. Feedback is withheld until
the form ends; post-form solution exposure does not rewrite the original attempt.
Reservations remain consumed on abandon to avoid reusing possibly exposed items.

## Verification

The original eight arithmetic/content tests passed before development.
The expanded suite covers successful and failed forms, assistance, invalid input,
duplicate and concurrent submissions, cross-user access, restart/resume, both
review occasions with a controlled clock, exhausted coverage, JWT claims, and
migration round trips. PostgreSQL SQL generation is tested offline.

Database migrations and original draft import were run on the local database.
The importer can be rerun without duplicate versions or fabricated approvals.

## Material limits and next implementation work

- No real content has been approved. The runtime correctly cannot assign drafts.
  Synthetic approved fixtures are confined to tests and are not an educational bank.
- There is no student frontend or complete diagnostic-to-teaching route yet.
  Practice/diagnostic sessions currently assign one item each.
- The skill specification/coverage audit and reviewed teaching/probe pool need work.
- AI tutoring, mistake notebook, skill list, and study queue are later steps.
- Reviewer authorization/UI, withdrawal audit, evidence invalidation/recomputation,
  retention/deletion/export, rate limits, and operational backups are not built.
  Do not treat the backend as pilot-ready before these gates are addressed.
- PostgreSQL is the intended durable hosted database, but live PostgreSQL execution
  and its concurrency behavior have not been tested here.
- Supabase project setup and browser login remain unconfigured. JWT verification
  supports asymmetric signing keys; legacy HS256 projects need a separate design.
- Private content is never returned by student endpoints. Before Supabase deployment,
  configure database roles/schema exposure so the browser cannot bypass the API.
- Policy thresholds and two/seven-day dates are provisional software rules.
  Tests establish behavior, not assessment validity or improved learning.

Next: build the divisibility specification and coverage matrix, add the bounded
review workflow, then connect this service to the Next.js student journey.

## Technical references

- https://supabase.com/docs/guides/auth/jwts
- https://supabase.com/docs/guides/auth/signing-keys
- https://docs.sqlalchemy.org/en/20/dialects/sqlite.html
- https://www.sqlite.org/lang_transaction.html

## Verification result

42 tests passed on Python 3.12 with one upstream Starlette/httpx deprecation
warning. API behavior is verified through FastAPI TestClient. Alembic upgrade,
downgrade, re-upgrade, and offline PostgreSQL schema compilation pass. The local
startup script reached Uvicorn application startup, but cross-session loopback
HTTP requests timed out in this execution environment. The temporary server was
stopped; no live website is claimed. Use scripts/start-local.ps1 from a local
terminal to launch the backend. No live PostgreSQL or Supabase test was performed.
