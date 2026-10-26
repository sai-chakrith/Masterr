# Track 3: data, API and dashboard

Assigned from the supplied mastery scoring proposal. First slice implemented on 26 October 2026.

## Implemented

- Extend the existing attempts records instead of duplicating them in a responses table. Learner, session, question version, skill, source mode, assistance and timestamp are already available through their foreign keys.
- Add optional duration_ms (client supplied, 0 to 24 hours), predicted_probability (reserved for the scoring engine) and scoring_version. Timing participates in submission idempotency; legacy untimed request hashes remain compatible.
- Add nullable question difficulty_level (1-5), sub_topic and a hidden flag. Existing questions retain their original content and approval status; unknown difficulty is left null. Normal selection excludes hidden items.
- Add per-learner/topic scoring configuration and rating/count/recent-change storage. No historical estimates are invented. Current scoring remains the only active implementation.
- Add reversible Alembic migration; application startup still does not mutate schemas.

## Handoff

Superseded on 26 October 2026: the engine, version switch, bank and dashboard are now built. See mastery-scoring-progress.md.

## Remaining Track 3 work

Question-bank review/import and allocation, browser timing capture, I-dont-know input support, dashboard states, and the operational scoring version switch. The present checkout has integer-answer tasks rather than the PDF's multiple-choice sessions, so skipping must be implemented with explicit grading semantics across API and scoring, not as a fake numeric answer.

## Validation

46 backend tests passed, including timing persistence, idempotent retries, hidden-item exclusion, migration round trips, and PostgreSQL offline SQL compilation. Tests use a workspace temp directory because the sandbox default temp location is inaccessible. This is engineering verification, not a learner-effectiveness result.
