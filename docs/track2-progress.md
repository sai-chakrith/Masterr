# Track 2: retesting and gap handling

## Implemented

- POST /v1/topics/{skill_id}/retest reserves ten distinct unseen question families as a verification session under topic-retest-v1. It uses reviewed, non-hidden verification questions with explicit numeric difficulty_level tags, preferring levels 3-4 and then the nearest tagged levels. Fewer than ten candidates returns insufficient_coverage and creates no partial session or reservations. Existing exposure rules also exclude families reserved in abandoned sessions.
- A completed independent retest passes at 7/10; 6/10 fails. Feedback stays withheld until completion. Help terminates independence and cannot resolve a gap. No mastery rating is set to 1.0 or otherwise modified by this track.
- Submissions accept dont_know=true with an empty answer. It is recorded as the literal I-dont-know response, marked incorrect, and included in retry identity. The existing non-null normalized integer column uses zero as an internal placeholder for skips; raw_answer and correct distinguish it from a numeric zero answer. Do not derive skip correctness from normalized_answer. The API rejects a skip submitted with a numeric answer.
- Persistent gap_states records learner/topic status and the source session. GET /v1/me/gaps returns curriculum/prerequisite order and never recomputes or changes a decision. Missing records are unassessed. Passing a retest resolves a gap; a subsequent failed independent verification/review or retest reopens it. Practice and read requests do not reopen it.
- GET /v1/sessions/{id}/borderline-review returns only missed/skipped diagnostic items and their reviewed solutions. It requires the owner's completed diagnostic and its current Borderline decision. It allocates no questions, invents no explanations, and returns a retest next action. Repeated calls do not duplicate solution exposure events.
- Question import now persists validated difficulty_level, hidden and sub_topic metadata from reviewed versioned content. Legacy difficulty labels are not guessed into numeric levels.
- Reversible Alembic migration ca64a7954ed7 adds gap_states. No production or local application database was automatically migrated.

## Track 1 handoff

LearningService.set_gap(db, session, status) is an internal transaction hook for the diagnostic classifier. It accepts mastered, borderline, gap, resolved. The caller must supply a legitimate assessment-backed decision. There is no public endpoint allowing students to set their own status. The current diagnostic remains unclassified until Track 1 calls this hook. Rating updates and predicted probabilities remain Track 1 work; Track 2 currently preserves existing score storage rather than implementing a second estimator.

## Limits and deferred work

The fixed ten-question/7-correct rule follows the supplied proposal. SPRT is a researched candidate, not an accepted or validated replacement. No claims of mastery reliability or learning gains are made. Difficulty fallback changes test composition and requires evaluation. The real draft bank has not been expanded, difficulty-calibrated, or approved; retests correctly refuse insufficient reviewed coverage. Browser UI, live tutoring/LLM integration, pilot recruitment and learning-effectiveness analysis are not implemented here. The controlled pilot/results work remains deferred by the user.

## Validation

56 tests pass, including retest thresholds, all skips, ownership, unseen-family reservation, atomic exhaustion, fallback ordering, hidden exclusion, assistance, durable gap decisions, reopening only on new independent evidence, metadata import, API validation, migration round trips and PostgreSQL SQL compilation. Synthetic fixtures are test-only and are not publishable question content.
