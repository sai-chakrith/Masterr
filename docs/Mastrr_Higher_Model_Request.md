# Mastrr application blueprint request

Prepared for a higher reasoning model on 23 October 2026.

## Your assignment

Act as a senior product architect, learning assessment researcher, and AI systems
engineer. Turn the context below into a coherent, implementation-ready blueprint
for Mastrr. We need you to resolve the remaining design questions, identify flaws,
and make concrete recommendations. Do not merely restate the idea or give a
feature wishlist. Explain your conclusions and tradeoffs without exposing private
chain-of-thought. Your deliverable is a specification for an implementer, not code.

This brief is self-contained. Do not assume access to earlier chats or repository
files. If you can inspect an attached repository, reconcile this brief with it and
report discrepancies. Otherwise label repository claims as supplied context.

Make reasonable assumptions and proceed. Ask questions only when a missing answer
would materially change architecture or make the work impossible. Put any such
questions at the end; complete independent decisions first. Do not invent budget,
reviewer availability, user research, implemented features, or test results.

## Product purpose and audience

Working name: Mastrr. Repository name: Masterr.
Audience: college learners studying aptitude and reasoning, initially students
preparing for placements. Begin with fundamentals before advanced questions.

We want to help learners distinguish recognizing a familiar solution from being
able to solve a fresh problem independently, address gaps, and check retention.
The core loop is diagnosis, targeted explanation, adaptive practice, independent
verification, and delayed review. A personalized skill graph should explain
prerequisites, show the evidence behind progress, and recommend the next action.

The concern motivating this request is that a chatbot, question bank, and generic
dashboard would be undifferentiated. Determine which mechanisms could make this
useful and how we would test their value. We have not established uniqueness,
learning effectiveness, or superiority over BYJUS or another product. Avoid
unsupported competitor claims; cite current primary sources if researching them.

## Current implementation supplied by the project

The repository contains a small content and validation foundation, not a student
application. It has six proposed Numbers skills, twelve original draft questions,
worked solutions, staged hints, reasoning rubrics, follow-ups, provenance, family
identifiers, independent Python arithmetic validators, a family-aware selector,
and an explicit student payload that excludes answer keys and solutions.

All questions await human review. None are approved for student delivery. Earlier
project records report eight passing unit tests; they were not rerun for this
brief. There is no implemented student UI, session API, authentication, durable
learning history, live reasoning AI, generation worker, or OCR ingestion pipeline.

The existing validators support integer answers for even counts, prime counts,
factor counts, missing digits, HCF, LCM, remainders, and modular powers. The
selector excludes unapproved items and exposed families. These safeguards need
integration and extension; they do not establish assessment reliability.

Proposed skill map:
- Integers, parity, and number properties, with no prerequisite.
- Divisibility, after integer properties.
- Primes and factors, after divisibility.
- HCF and LCM, after primes and factors.
- Remainders, after divisibility.
- Place value and units-digit cycles, after remainders.

Only a college contents page was supplied. Actual chapter and answer pages are
unavailable. Do not claim textbook alignment or reproduce unseen material.
Original reviewed content can support development without waiting for OCR.

## Decisions to preserve

- Start with Numbers. Establish a complete small learning journey before broad
  syllabus expansion. Divisibility with parity prerequisites is the proposed
  first slice, not a validated curriculum choice; challenge it if justified.
- Reviewed keys or independent mathematical validators score objective answers.
  AI interprets reasoning and recommends teaching actions; it is not the sole
  authority for correctness or assessed progress.
- Accept valid alternative methods. Ask for reasoning selectively rather than
  requiring an essay after every answer.
- A misconception is a hypothesis until supported by additional evidence.
  One wrong answer cannot establish its cause. A correct answer does not by
  itself prove a valid method.
- Distinguish independent, assisted, and solution-exposed performance. Track
  accuracy, help, and time separately; do not infer weakness from time alone.
- Reserve fresh question families for verification and retention. Numerical
  substitutions alone do not establish independent evidence. Report inadequate
  coverage rather than silently recycling familiar assessment items.
- Preserve attempts, question versions, exposures, and evidence supporting every
  status. Avoid unexplained mastery percentages and placement guarantees.
- Expand a trusted bank with AI-generated drafts grounded in skill specifications
  and reviewed examples. Validate and review before publication. AI checking AI
  is an additional check, not proof. Review logical questions for assumptions
  and answer uniqueness. Generation does not guarantee curriculum coverage.
- OCR uses an existing engine with preserved source pages, raw extraction,
  references, uncertainty, and human correction. OCR success is not publication
  approval. OCR follows the first usable loop.
- Keep the first system maintainable by a small development effort. Do not assume
  a funded team or add services without a clear requirement.

## Selected application stack

The user delegated the stack decision. Treat this as the default architecture;
recommend a change only for a concrete incompatibility or material advantage.

| Layer | Selected technology |
| --- | --- |
| Frontend | Next.js App Router, React, TypeScript |
| Styling | Tailwind CSS and shadcn/ui |
| Math display | KaTeX |
| Skill graph | React Flow when the progress map is implemented |
| Backend | Python 3.12, FastAPI, Pydantic |
| Persistence | PostgreSQL, SQLAlchemy 2, psycopg 3, Alembic |
| Hosted database and identity | Supabase PostgreSQL and Supabase Auth |
| Verification | Existing Python validators, pytest, and Playwright |
| AI | Backend-only hosted-model adapter, provider and model not selected |

FastAPI owns assignments, grading, content approval, learning rules, evidence,
review scheduling, and AI requests. Avoid duplicating learning logic in Next.js.
Keep keys and private solutions server-side. Verify identity and ownership for
all learner operations. Direct database connections do not automatically inherit
Supabase user RLS context; specify the actual enforcement design.

Start with local development and PostgreSQL. Require real authentication and
isolation for the multi-user pilot. A due-review queue can use database records
queried when a student returns; notifications and a scheduler are separate needs.
Introduce persistent background jobs only when ingestion or generation needs them.
No initial requirement for Redis, a vector database, a graph database, custom
model training, microservices, or an agent framework. Hosting remains undecided.

## Central open problem the question reasoning AI

Design an AI tutor that interprets the learner's submitted method, identifies
what the text actually supports, asks targeted follow-ups, and gives useful hints.
Example: for divisibility by 6, a student checks divisibility by 3 but omits the
even-number condition. The system might ask whether 15 satisfies their rule and
whether 15 is divisible by 6. It must distinguish this from an arithmetic slip,
incomplete wording, guessing, or a valid method expressed differently.

Define inputs, structured outputs, model responsibilities, tool boundaries,
prompt construction, and fallback behavior. Include a JSON contract and worked
examples. Address correct answer with flawed reasoning, wrong answer with valid
method, terse working, no working, ambiguity, alternative methods, contradictory
statements, malicious instructions, and failed AI requests. AI confidence scores
are not calibrated probabilities unless demonstrated to be so.

Determine whether follow-ups come from reviewed items, constrained templates,
or live generation. Prevent follow-ups or tutor feedback from leaking reserved
assessment content. Specify latency, cost accounting, caching where safe,
submission deduplication, and what remains usable during outages.

Recommend a provider/model evaluation procedure. If you can browse, shortlist
current models using official documentation and date-stamped capabilities/prices.
If you cannot, do not invent a current winner or price. Specify a reproducible
selection gate and an actionable initial integration approach instead.

## Provisional plan to critique

Initial content target: 18-24 reviewed divisibility questions, including at least
two diagnostic, six practice, three verification, and three delayed-review items,
plus separate prerequisite probes. This is a planning target, not demonstrated
coverage. Review whether two review dates and multiple retries exhaust these
pools. Provide a concrete family allocation and replenishment strategy.

Provisional routing: two correct unassisted practice questions from distinct
families allow verification. Three fresh unassisted verification answers produce
an independent-check-passed status. Help during verification converts that attempt
to assisted practice. Proposed review dates are 2 and 7 days later, with fresh
families. All thresholds and intervals are unvalidated and open to revision.

Prior effort estimate: 14-21 focused working days to pilot readiness, excluding
human review, credentials, recruitment, and real retention delays. Re-estimate
from actual work; do not preserve it merely to agree with us.

## Required output

Organize your response into the following concrete deliverables.

### 1 Product scope and decisions

Give a short product definition, primary user jobs, roles, and explicit boundaries
for a demonstration, a multi-user pilot, and a full Numbers release. Separate
accepted decisions, your recommended decisions, assumptions, and future options.
List contradictions and weak assumptions. Avoid turning every idea into v1 scope.

### 2 Student and reviewer workflows

Specify onboarding, diagnostic, teaching, practice, verification, delayed review,
progress evidence, resume, exhausted content, and error states. Give a screen
inventory with the information, actions, and acceptance criteria for each screen.
Include reviewer editing, approval, withdrawal, reporting, and correction flows.
Explain what the learner sees in a representative complete session.

### 3 Learning and assessment policy

Provide a skill specification template, prerequisite strategy, question purposes,
family/exposure policy, assistance definitions, answer normalization rules, and
versioned state-transition table. Cover skipped prerequisites, retries, mixed
results, missed reviews, contradictory evidence, content correction, and active
versus elapsed time. Separate routing heuristics from validated mastery claims.

### 4 Reasoning AI design

Supply the contract and examples requested above, the allowed actions, input
context limits, review rubric, evaluation cases, failure behavior, and model
selection procedure. Explain how useful tutoring and defensible assessment
coexist. Clarify how assessed progress can change after AI feedback and who is
authorized to make that change.

### 5 Content and ingestion plan

Provide an executable coverage matrix for the first skill, including allocation
by purpose, subskill, family, and review occasion. Show how enough independent
items remain for retries. Define drafting, validation, review, publication,
withdrawal, generation provenance, and later OCR ingestion. Identify the actual
reviewer dependency rather than manufacturing approval.

### 6 Data and API specification

Give entities, key fields, relationships, ownership, uniqueness constraints,
indexes, timestamps, migrations, and immutable/versioned records. Provide a
compact ER diagram if useful. List API methods and paths with request/response
shapes, authentication, state preconditions, errors, idempotency, and transactional
boundaries. Show exactly how attempts, exposure, evidence, and due reviews connect.

### 7 Security and operational design

Define Supabase Auth integration, JWT validation, direct database roles, ownership
checks, exposed schemas/RLS boundaries, reviewer authorization, secret management,
answer release, and abuse/rate limits. Cover backups/restoration, minimal logs,
student consent and retention/deletion, export, accessibility, mobile use, and
observability proportionate to pilot scope. Separate launch blockers from later
improvements. Do not speculate about jurisdiction-specific law without sources.

### 8 Verification and evaluation

Give critical automated tests and manual acceptance scenarios. Separate software
correctness, content quality, AI reasoning quality, usability, and learning
outcomes. Include false acceptance/rejection, unsupported diagnosis, abstention,
latency, and cost with counts and denominators. Propose initial release gates as
recommendations and explain how to set thresholds. Do not report invented results.

For learning evaluation, specify reserved comparable pre/post/delayed forms,
matched time/content comparison conditions, allocation, attrition handling, and
what a small pilot can and cannot establish. A prior 5-8 participant usability
target is not a powered effectiveness study; give a justified evaluation plan.

### 9 Implementation sequence

Give dependency-ordered milestones with concrete repository modules, deliverables,
completion checks, effort ranges, external blockers, and a minimum demo path.
Identify tasks that can proceed without textbook pages, AI credentials, or
hosting. Include local setup, pilot deployment recommendation, recurring cost
categories, and rollback/recovery. Avoid exact cost claims without assumptions.

### 10 Final decision register and first task

Finish with a compact register of decisions, rationale, uncertainty, and what
would trigger revision. List only genuine unresolved user inputs. End with the
exact first implementation task and its definition of done so a coding model can
begin without another high-level planning round.

## Response standard

Prioritize depth on the reasoning AI, evidence rules, content sufficiency, and
complete learning journey. Use concrete examples, schemas, tables, and concise
rationale where helpful. Do not substitute buzzwords, feature lists, or a generic
SaaS architecture for the requested blueprint. Cite current primary sources for
external technical claims when browsing. This request authorizes planning, not
service provisioning, purchases, publication, or invented implementation work.
