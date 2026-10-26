# Personalised learning implementation

Updated 26 October 2026. This document records the implementation against the
Mastrr personalised-learning proposal and separates code work from content and
pilot decisions that need people.

## Architecture in this checkout

- **API and rules:** FastAPI, SQLAlchemy and pure Python policy modules. Scoring,
  question selection and recommendations remain deterministic; the tutor does
  not set mastery status.
- **Storage:** the existing SQLite-compatible schema and Alembic migrations.
  Goals, route progress and recommendation events are persisted alongside the
  existing learner, assessment, evidence and review records.
- **Learner app:** the existing Next.js, React and TypeScript frontend. It calls
  the API through the same proxy and uses the current token-based local sign-in.
- **Content:** versioned JSON curriculum and question bank. Only published,
  visible and appropriately tagged question families may be served.
- **Pilot analysis:** existing Python scripts and CSV artifacts in the scoring
  upgrade remain the source of assignment and outcome analysis.

No extra service or ML infrastructure is needed for these rules. Exam profiles,
content approval and production learner authentication are configuration and
review work, not values the implementation should invent.

## Implemented in this working tree

- Versioned curriculum validation, prerequisite-cycle checks and target-to-route
  closure. The API supports a direct target skill and an optional exam date.
- A validated exam-profile catalog now drives the API and goal form when a
  profile document is published. A profile supplies default/overridden practice
  bars and target skills; learner-added targets are merged with the profile.
  Goals keep a versioned profile snapshot, so a future catalog edit does not
  rewrite an existing learner's route or practice targets. The repository's
  profile document is deliberately empty and draft until mappings are agreed.
- Profile authoring has an export/edit/validate/approve CLI. Content edits reset
  the catalog to draft; publishing requires an explicit reviewer and ISO date.
- Persistent learner goals and learner route/progress records through a new
  Alembic migration.
- An explainable, pure next-action policy with the proposal's priority order,
  alternatives, reason text and stable reason codes.
- Recommendation display, follow and dismiss events. Stale recommendations
  are rejected using a state fingerprint.
- A route-only roadmap with status, score, evidence count, review date and
  reviewed-content availability. The frontend supports setting a target, showing
  a reasoned next action, dismissing it, and rendering the learner's prerequisite
  graph. The graph is an accessible, horizontally scrollable SVG with clickable
  topic cards, status, score, answer count and review date. React Flow is the
  selected graph library in `docs/tech-stack.md`, but it is not yet integrated:
  this machine has no frontend dependencies and the npm registry lookup failed
  with DNS `ENOTFOUND`. Replace the SVG renderer with React Flow when dependency
  installation is available; the graph data remains the backend roadmap.
- A curriculum lesson page, with server-side publication gating for its lesson
  text, and navigation from a tutoring recommendation.
- A learner-specific teaching plan endpoint selects full plus half-worked
  examples below 50%, hinted practice from 50% through 75%, and practice-first
  above 75%. A wrong practice answer returns the reviewed item solution; the
  practice screen can also request hints. The curriculum now includes the ten
  proposal pilot topics (plus the existing Numbers topics), with original
  worked examples gated as draft content.
- Curriculum approval tooling validates the full/half-worked example structure,
  records reviewer/date, and stores a content checksum. Any edit after approval
  makes runtime curriculum loading fail until the owner returns it to draft and
  reviews the updated version.
- The next-action rule sends learners below a 50% estimated score to the lesson;
  learners at or above 50% can move to practice with hints available on request.
- The active practice screen exposes the bank's reviewed hint sequence on request;
  assessment and validation sessions do not show hints.
- For tagged multiple-choice items, the second and later wrong selection tied to
  the same misconception surfaces a targeted reset using its reviewed short fix.
- Practice strategy has its own per-learner/topic pilot assignment, separate
  from the scoring-version assignment. `scripts/pilot.py assign-practice` makes
  a stable half-topic personalised/fixed split. Personalised topics target
  approximately 80% predicted success using fresh approved, tagged families;
  fixed topics receive a mixed-difficulty block. Both run up to ten questions,
  and personalized practice stops after five independent answers if the topic
  bar is reached. Scoring version can be held constant between conditions.
- Question-review tooling exports the prompt, validator, answer, solution, hints,
  difficulty tags, options and review metadata. A human records each explicit
  approval or withdrawal with reviewer and ISO date; the decision creates a new
  immutable version and the bank validator must pass before the JSON is saved.
- The content model and learner session now support four-option questions with
  misconception-tagged distractors. The API only sends option IDs and display
  text; it records the selected option and deterministic feedback, without
  exposing the answer key. Forty pilot-topic misconception definitions exist as
  drafts. Deterministic draft distractors are attached to 752 pilot questions;
  `scripts.add_distractors` validates and attaches them without approving content.
  `scripts.misconception_review` exports and validates concept copy; changing it
  returns the definition to draft. The question-bank validator will not approve
  an item while a referenced misconception is draft. A human must check every
  option and tag before the pilot can use this feedback.
- The previous bank had only one practice item per topic, which could not support
  a five-answer mastery threshold or ten-question blocks. A deterministic,
  seedable generator now creates 40 practice drafts for each of the 15 curriculum
  topics (600 drafts total) and a 35-item draft assessment bank for each of the
  nine newly added arithmetic pilot topics (315 drafts). The new assessment pools
  follow the weighted difficulty split and include ten hidden validation items.
  All generated items remain draft until human review and are not served to learners.
- A separate `scripts/personalisation_analysis.py` reads validation stages,
  practice effort and recommendation events, and reports normalised gain and a
  within-learner effect estimate by assigned strategy. It also prints assigned
  learner-topic denominators, per-topic treatment counts, and missing pre, post
  and delayed forms. It reports descriptive estimates only and requires a
  reviewed bank and complete roster before use.
- A stuck rule redirects after ten independent practice answers when the score
  has not reached the bar and has not risen over the last five observations.
- Passing an independent retest schedules reviews after 3, 7 and 21 days. A
  passed review schedules the next interval; a failed review reopens a gap under
  the existing deterministic assessment rules. When a learner has an exam date,
  scheduled reviews are capped at 9 a.m. local time on the day before the exam.
- Exam-profile practice bars control the practice-to-retest readiness target and
  are shown on each route topic. The independent scoring foundation retains its
  existing diagnostic cut-offs and 7/10 retest rule; profile-specific changes to
  those decision standards require a separate scoring validation.
- Curriculum and question availability remain explicit. Draft curriculum does
  not expose lesson text; draft and hidden questions are never served. The
  legacy one-question flow can still use approved untagged content, while the
  new adaptive and fixed pilot policies require difficulty tags.

## Existing foundation reused

The scoring-upgrade commit already supplies the Elo-style score, diagnostic
rescoring and safety zone, 10-question retest, answer provenance, versioned
question bank, pilot assignment and analysis scripts, and the current app
session flow. Those modules were extended rather than replaced. The scoring
upgrade's own progress record remains authoritative for its decision history.

## Verification in this checkout

- `.venv/Scripts/python.exe -m pytest -q --basetemp=.pytest-tmp-p7 --ignore=tests/test_api.py`:
  **137 passed**, including the ten-topic assessment-pool, misconception-review,
  and pilot-split checks.
  An isolated API test still stalls before producing output, even with its pytest
  temp directory redirected into the writable repository. It was interrupted
  without an API response, so HTTP behavior remains unverified through TestClient.
- The focused MCQ feedback tests pass (**2 passed**).
- Exam-profile, practice-bar, exam-date review, question-bank, and migration
  checks passed in the focused run (**14 passed**).
- Direct route-function checks passed for approved-profile listing and
  profile-only goal submission; the catalog validator currently confirms the
  intentionally empty draft file is valid.
- Curriculum checksum approval, draft examples, and score-band teaching checks
  passed; both curriculum and exam-profile catalogs validate in their current
  draft state.
- The current curriculum validation passes for 15 topics. The question-bank
  audit reports the expected 35 assessment items, 3/6/11/11/4 difficulty split,
  and 10 hidden questions for all 15 topics; none of the content is approved.
- Changed TypeScript/TSX files parsed with the bundled esbuild transformer.
- `git diff --check`: passed.
- Before the SVG graph was added, changed TS/TSX files parsed through the
  bundled esbuild transformer. The new `SkillRouteGraph.tsx` has not yet been
  parsed by the frontend toolchain. A Next.js build and TypeScript typecheck are
  unverified: frontend dependencies are not installed, and offline pnpm
  installation was blocked by Windows denying pnpm's project-store symlink;
  online package resolution currently fails with DNS `ENOTFOUND`.

## Remaining work before learner pilot

1. **Review and publish curriculum and questions.** The current Numbers
   curriculum and its worked examples are marked `draft`; question-bank records
   are drafts awaiting human review. The API correctly reports no activities
   until appropriate content is approved. The ten pilot topics are present in
   the curriculum, with generated practice and assessment drafts. Use
   `python -m scripts.question_bank export path.csv` for the review sheet.
   Generate practice drafts with `python -m scripts.generate_questions --count 40 --seed 20261026`.
   The nine new assessment pools were drafted with `python -m scripts.generate_questions --assessment --seed 20261026 --skills percentages profit-loss simple-interest compound-interest ratio-proportion averages mixtures-alligations partnership time-work`.
   Apply validated content edits with `python -m scripts.question_bank apply-content path.csv`,
   record reviewer/date, then apply explicit decisions with
   `python -m scripts.question_bank apply-review path.csv`.
   Reseed the database with `python -m backend.seed` to import the new versions.
   Approve the curriculum separately with `python -m scripts.curriculum_review approve --reviewer REVIEWER_NAME --date YYYY-MM-DD` after reviewing all skills.
2. **Write and approve exam profiles.** Agree the supported exams, route topics
   and topic bars, then use `scripts.exam_profiles` to export the review sheet,
   apply edited content, validate it and explicitly approve the catalog.
   The API currently returns no profile choices because that catalog remains
   empty and draft. Direct target skills work in the meantime.
3. **Review and complete teaching and misconception content.** The curriculum's
   worked and half-worked examples are drafts and need a human review. The
   question bank has deterministic distractor drafts and 40 misconception
   definitions for pilot topics, all unapproved. Review every option/tag and
   concept with `scripts.question_bank export` and `scripts.misconception_review
   export`; current selected-option feedback and repeat-misconception reset stay
   unavailable until the referenced content is explicitly approved and seeded.
4. **Finish pilot assignment and controls.** The new practice-strategy switch is
   separate from the existing scoring-version switch. Agree the 10 pilot topics,
   assign the same scoring version to both practice conditions, then use
   `assign-practice` for the within-learner split. Verify the exported roster
   against the protocol before recruiting. Use `scripts/personalisation_analysis.py`
   for strategy comparison; inspect its output against the agreed analysis plan.
5. **Provision authentication and recruit learners.** The repository has a
   local token sign-in path; hosted Supabase credentials, pilot accounts,
   recruitment, consent and dates require project-owner setup.
6. **Validate in a browser and against real responses.** Exercise goal setting,
   all action types, interruption/resume, dismiss/follow logging, 3/7/21-day
   review transitions, content withdrawal, and the final route on the approved
   pilot bank. Replace the current SVG graph renderer with the selected React
   Flow library and verify graph interaction in the browser. The 35-learner
   effect-size target is a hypothesis, not a result.

## Scope cautions

- The proposal describes 35 topics and a ten-topic arithmetic pilot. This
  checkout now contains 15 Numbers skills, including the ten pilot topics;
  generated content is still draft. The remaining 20 proposed topics and exam
  mappings still need curriculum decisions and reviewed content.
- The published 75–85% practice band is a hypothesis. The implementation starts
  at an 80% predicted-success target and keeps the policy version explicit so
  pilot evidence can tune it.
- The existing 10-question retest owns assessment decisions. Practice estimates
  only unlock a retest; they do not mark a topic Mastered or Resolved.
- A running server deployment, approved content set, active pilot or measured
  learning gain is not claimed by this implementation record.
