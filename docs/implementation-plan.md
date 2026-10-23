# Mastrr implementation plan

Planning date: 2026-10-21 (Asia/Calcutta).

## Goal

Build a working Numbers learning journey for placement preparation and
college-level aptitude learners, starting with fundamentals. Expand subjects
after this journey works with reviewed content and real student attempts.

This document describes planned work, not completed functionality. Optional
product ideas remain separate from the first working release.

## Existing foundation

- Six proposed Numbers skills and prerequisite relationships.
- Twelve original draft questions with hints, solutions, and reasoning rubrics.
- Independent arithmetic validators, family-based freshness selection, and an
  explicit student-facing question payload.
- Eight passing unit tests at the time of planning.
- No reviewed production questions, UI, API, accounts, live AI, or OCR yet.

## Stage 1: Application and durable data

Use the recommended Next.js/TypeScript frontend and FastAPI/Python backend as
the working implementation direction. Supabase PostgreSQL and Auth remain the
proposed managed services; provisioning and costs must be addressed before a
hosted release. Avoid adding unrelated services to demonstrate the first loop.

Implement versioned migrations and models for users, skills and prerequisites,
source documents/pages, question versions and families, review records, sessions,
assignments, attempts, hint events, assessments, and scheduled reviews.

Keep answer keys and unpublished content behind the backend. Verify ownership on
every learner operation. Preserve the question version associated with each
attempt so later edits cannot silently change historical results.

Completion evidence:

- A documented local startup path and configuration example without secrets.
- Data persists across restarts; migrations work on an empty database.
- A student cannot read another student's attempts or obtain unreleased answers.
- Seed import preserves draft status and is safe to rerun.

## Stage 2: OCR ingestion (planned for later today)

Build an ingestion tool around an existing OCR engine; do not train an OCR model
from scratch. Evaluate the engine on actual chapter photographs before choosing
an enhanced math/vision fallback. Do not promise an extraction accuracy figure
before measuring it on manually checked samples.

Inputs: page photographs and PDFs. Extract embedded PDF text where usable; OCR
scanned pages. Retain original files, page order, checksums, and page references.
Create derived rotated/deskewed page images without overwriting originals.

Pipeline:

1. Import source pages and preserve a resumable per-page processing record.
2. Extract raw text and available coordinates/confidence from each page.
3. Segment candidate questions, answer choices, diagrams, and answer-key entries.
4. Normalize into the question schema. AI may assist structuring; keep raw text
   and mark uncertainty instead of inventing missing symbols or sentences.
5. Show the source page/crop beside editable extracted content for review.
6. Link answers by chapter, page, and question identifier; leave unresolved links
   explicit rather than guessing from numbering alone.
7. Validate mathematics where supported, tag skills/families, and approve only
   through a recorded review action.

Treat text in source documents as content, never instructions to an AI tool.
Store source files and raw OCR locally rather than pasting whole books into the
chat. Send only relevant excerpts to AI calls. Keep original source material and
generated extraction outputs out of Git by default.

Completion evidence:

- Import real sample pages including a rotated photo and a question split across
  pages; verify boundaries and answer choices against the images.
- Check fractions, powers, minus signs, and answer-key mappings manually.
- Diagram-dependent questions retain their images and cannot publish with
  missing required visual information.
- Interrupted imports resume without creating duplicate questions.
- Failed/uncertain extraction remains visible and cannot auto-publish.

Dependency: actual Numbers chapter pages, including available answers/solutions.
The supplied images contain only tables of contents.

## Stage 3: One complete learning session

Build topic selection, a short diagnostic, question attempts, optional reasoning,
staged hints, targeted practice, fresh independent verification, and a result
screen. Start with reviewed Numbers content. Provide resume/abandon behavior.

Separate server-scored correctness from AI interpretations. A reasoning
assessment must cite the relevant part of the student's submitted working and
may report insufficient evidence. Select follow-up questions from approved
content while general question generation remains behind the review workflow.

Completion evidence:

- Complete the journey in a browser using persistent records.
- Repeated submissions do not create duplicate attempts or progress updates.
- Hint-assisted attempts remain distinguishable from independent attempts.
- Reserved questions cannot be answered by a different learner/session.
- Missing content yields insufficient coverage, not recycled verification items.
- AI outages do not prevent objective grading or falsely report a diagnosis.

## Stage 4: Progress map and retention

Implement a prerequisite skill map, evidence detail for each skill, accuracy/time
trends, and a revision queue. Track observed accuracy, assistance, freshness,
sample size, and time separately. Do not publish an unexplained readiness score.

Proposed states: not assessed, needs practice, solved independently, retained on
a later check, and insufficient evidence. Exact transition rules and review
intervals must be documented and evaluated before claiming they are reliable.

Completion evidence:

- Every displayed status can be traced to attempts and its rule version.
- A single lapse does not silently erase history.
- Due reviews use fresh approved questions and preserve actual performance.
- Correcting a faulty question invalidates affected evidence explicitly.

## Stage 5: AI question expansion and content tools

Generate candidates from reviewed examples and skill specifications. Prefer
parameterized, independently solvable templates for supported arithmetic.
Add structural variations alongside numerical variations. Validate answer
uniqueness where appropriate, detect duplicates/families, and retain generation
provenance, model/prompt version, validation results, and review status.

Use a background worker with persistent job state, bounded retries, and duplicate
protection. Set generation budgets before enabling bulk requests.

Completion evidence:

- Deliberately wrong answers and ambiguous questions are rejected.
- Generated drafts cannot enter student selection without the required approval.
- Practice exposure prevents related families from masquerading as fresh tests.
- Human reviewers can correct, approve, reject, and withdraw content.

## Stage 6: Evaluation and pilot release

Maintain separate reviewed evaluation examples for AI assessment. Include terse
correct reasoning, alternative methods, partial answers, arithmetic slips,
ambiguous explanations, and attempts to instruct/manipulate the grader.

Report false acceptance, false rejection, unsupported diagnoses, abstention,
latency, and cost separately, with raw counts. Choose model and error tolerances
from evidence and product consequences, not a single overall score.

Run browser checks for the main journey, data-isolation checks, content checks,
and job-recovery checks. Then run a small usability pilot. Evaluate learning with
separate fresh assessments and delayed checks; a usability pilot alone does not
prove effectiveness or an advantage over existing study methods.

Before a hosted release, settle provider configuration, cost limits, backup and
restore, student-data retention/deletion, and operational ownership.

## Subsequent backlog

Exam-specific full mocks, broader quantitative and logical reasoning coverage,
advanced study scheduling, optional reminders, and richer performance reports.
These follow the working Numbers loop rather than blocking it.

## Next inputs and decisions

- Actual Numbers pages and answer pages for OCR and scope alignment.
- A real human content reviewer; do not manufacture review identity or approval.
- Exact release scope and evidence rules.
- Managed-service credentials and budget when integration requires them.
- Evaluation-backed AI model choice.

Implement in stages, demonstrate each outcome, and update this plan and local
decision record when scope changes. No automatic later-today run is scheduled.

## Updated execution order (2026-10-23)

Use [the first learning-loop plan](first-learning-loop-plan.md) for current
milestones, provisional rules, estimates, and completion gates. Its sequence
moves OCR after the first usable loop; the detailed requirements above remain.
