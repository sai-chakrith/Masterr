# Mastrr: first learning-loop build plan

Planning date: 2026-10-23. This is planned work, not implemented functionality.
This execution order updates implementation-plan.md: OCR follows the first loop.
The stack is selected in tech-stack.md. Assessment rules remain provisional.

## First release

Start with divisibility and prerequisite checks of integers and parity. Deliver
one resumable journey: diagnostic -> targeted lesson -> assisted practice ->
fresh independent verification -> evidence summary -> delayed review.
Expand across the remaining Numbers skills after this journey works.

Include reviewed questions, staged hints, server scoring, persistent attempts,
a small prerequisite graph, evidence details, and a due-review queue.
Defer full mocks, broad syllabus coverage, bulk generation, elaborate analytics,
notifications, OCR, and public hosting until the first loop works.

## Milestones

| Milestone | Deliverable and completion check | Focused effort estimate |
| --- | --- | --- |
| 1. Learning specification and content | Divisibility objectives, prerequisite probes, lessons, coverage matrix, mistake hypotheses, and reviewed questions; no draft can reach a student | 2-3 days plus human review |
| 2. Persistent session and scoring | Migrations, assignments, attempts, hints, resume, server grading; restart persistence, idempotency, ownership, and answer-release checks pass | 3-4 days |
| 3. Complete browser journey | Diagnostic through verification and evidence summary; resume works, assisted attempts stay distinct, insufficient fresh content is explicit | 3-4 days |
| 4. Evidence map and reviews | Prerequisites, attempt details, rule versions, due reviews; each status traces to evidence and fresh review families are reserved | 2-3 days |
| 5. Bounded AI assistance | Reasoning feedback and approved follow-ups; evaluate alternative methods, partial work, abstention, and manipulation; outages preserve grading | 2-4 days |
| 6. Usability pilot and corrections | Observe sessions, log issues, fix blocking failures, and prepare separate learning evaluation | 2-3 days plus participant availability |

Total planning estimate: 14-21 focused working days, excluding human review,
service setup, recruitment, and actual retention delays. Re-estimate after
milestone 1. These are effort ranges, not delivery commitments.

## Content and evidence policy

Initially target 18-24 reviewed divisibility questions: at least two diagnostic,
six practice, three verification, and three delayed-review items, with remaining
items covering alternative routes. Add separate prerequisite probes. This is a
coverage target, not a validated sample-size rule. Review structural diversity;
changing only numbers does not create an independent question family.
Reserve assessment families before practice. Exhausted coverage blocks a check
rather than silently recycling familiar items. Real human approval is required.

Provisional rules to implement transparently and evaluate in the pilot:

- One diagnostic error triggers another probe; a misconception stays a hypothesis.
- Two correct unassisted practice answers from distinct families permit a
  verification attempt. This is a routing rule, not proof of mastery.
- Three correct fresh verification answers from distinct reserved families,
  without help, produce an independent-check-passed status. Other outcomes show
  actual evidence and route to relevant practice. Thresholds are provisional.
- Help during verification converts that attempt to assisted practice; later
  verification requires a different fresh family.
- Propose reviews 2 and 7 days after the independent check using separate fresh
  families. Track pending, overdue, missed, and completed reviews explicitly.
- Display not assessed, practice needed, independent check passed, and later
  check passed with an insufficient-evidence/coverage condition where applicable.
  Avoid unsupported mastery percentages or permanent mastery claims.
- Preserve accuracy, help, optional reasoning, timestamps, question versions,
  family exposure, and the rule version supporting each progress update.
- Track solving time separately; pauses and lack of benchmarks limit conclusions.

## Technical implementation

Reuse the Python bank, arithmetic validators, student-payload allowlist, and
family selector. The earlier Next.js/TypeScript, FastAPI, PostgreSQL/Supabase
proposal remains the planning option pending final selection. Local development
must not depend on buying public hosting. Use one modular backend.

Minimum records: learners, skills/prerequisites, question versions and families,
review records, sessions, assignments, attempts, hint events, evidence events,
and review schedules. Preserve question versions and invalidate faulty evidence
explicitly when content is withdrawn. Keep answers server-side and reveal worked
solutions only after attempts end; record that exposure. Require authentication
and ownership checks before any multi-user pilot.

Build the deterministic journey before live AI. AI interprets reasoning and
selects approved follow-ups; verified keys or mathematical validators score
objective answers. Store model/prompt versions and allow insufficient evidence.
Choose the model from a separate reviewed evaluation set and document error,
abstention, latency, and cost results before enabling it for students.

## Evaluation

Begin with 5-8 consenting volunteer usability participants. Observe comprehension,
navigation, hints, completion, and resume behavior. Report counts and dropouts.
This participant target supports usability iteration, not statistical proof.

Evaluate learning separately with reserved pre-test, immediate post-test, and
delayed-test forms of comparable coverage and difficulty. Keep evaluation families
out of teaching and model selection. For a fair comparison with ordinary practice,
match content, study time, and assessment conditions; specify group allocation,
outcomes, sample-size rationale, and analysis before collecting comparative data.
Report accuracy, assistance, retention, completion, uncertainty, and attrition
separately. A simulated clock verifies scheduling, not actual retention.

## Dependencies and immediate next task

Next: write the divisibility learning specification and question coverage matrix,
then expand draft content and prepare it for human review. Existing questions
remain drafts until a real reviewer records approval. Do not invent approvals.

Actual chapter and answer pages are needed for textbook alignment and OCR checks;
original reviewed content lets the first loop proceed without them. AI credentials
and budget are needed at model integration; hosting choices at external release.
Continue independent work while external inputs are unavailable.

After the loop and pilot: expand the remaining Numbers skills, add OCR with
source-preserving human review, introduce validated AI question generation, then
revisit hosting and wider release. Existing implementation-plan.md retains
additional ingestion, isolation, and operational requirements.

