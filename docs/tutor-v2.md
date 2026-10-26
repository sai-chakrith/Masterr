> Current application update (27 October 2026): this document retains its earlier milestone snapshot. See [application status](application-status.md) and [deployment instructions](deployment.md) for the integrated app, current checks and remaining launch requirements.

# Tutor v2 implementation

Implemented 27 October 2026 against this repository's FastAPI/SQLAlchemy application.
The report's `main.py`, `backend/database.py`, patch archive, old `/tutor` handler
and 35-topic bank are not present here. The working curriculum currently has 15
topics, including the original Numbers foundation and newer pilot topics. The
implementation adapts the report to those actual structures.

## Behaviour

Open **Tutor** in the top navigation, choose a topic, and select **Open tutoring**.
The authenticated endpoint is `POST /v1/me/tutor/{skill_id}`. The owner comes only
from the verified identity, never a request body. Topics are listed by
`GET /v1/me/tutor/topics`. The response includes `content`, `lesson`, `personal`,
`parts`, `generated_by`, `selected_question_ids`, `model`, `prompt_version` and
`usage`. There was no old tutoring response in this checkout to preserve.

The lesson explains a concept, its method and common mistakes. It is shared by
topic, notes hash, prompt version, model and generation settings. The personal
part takes at most three distinct missed questions, with `I don't know` first,
then difficulty nearest level three. Only the owner's completed sessions and
currently approved, visible questions qualify. Hidden questions, validation
attempts and unfinished sessions are excluded. An active session in the topic
blocks tutoring so the tutor cannot supply answers during an independent check.
Selected multiple-choice answers are resolved to their text before generation.

Personal cache keys include exact question/answer data and the learner identity.
The report proposed sharing these across learners; this implementation keeps them
private because typed answers can contain identifying information. Working text,
identity and unrelated attempts are never sent to Groq. No tutor call grades an
answer, changes a rating, or marks tutoring complete merely because it was opened.

Groq is called directly through its documented HTTP endpoint using the Python
standard library. This avoids SDK parameter-version issues and adds no packages.
The default model is `openai/gpt-oss-120b`, `reasoning_effort=low`,
`include_reasoning=false`, and `max_completion_tokens=2000`. Empty or truncated
responses retry once; provider exceptions use a labelled fallback. Unknown or
non-stop finish reasons also fail closed. Calls have a 30-second timeout.
The personal response is structured JSON rather than free text with an `Answer:`
line, so the checker can validate exactly one answer per supplied question.

Each final answer must match its independently computed bank key. Fractions,
decimal equivalents, ratios, percentages and simple units are parsed as whole
values; text uses exact normalised equality. Percent signs and units matter.
Substring/whole-word matching is deliberately avoided: “not true” cannot match
“true”, and “14” cannot match “4”. A failed answer or response shape regenerates
once. If it still fails, all generated personal steps are discarded and only the
recorded questions, learner answers and correct answers remain. The final answer
check does **not** verify intermediate working or diagnose the cause of an error.

Fallbacks are labelled, never cached, and can be replaced on the next successful
call. A fixed next-step line is added by code. Usage records preserve the provider's
actual prompt, cached prompt, completion and reasoning counts for every returned
response, including retries and rejected examples. Missing counts remain null;
an entirely cached visit has an empty usage list. Provider error text and keys
are not persisted. No token-cost or quality savings have been measured live here.

## Notes and review

Whole-topic retrieval reads `knowledge/notes/<skill_id>.md` only when a matching
`<skill_id>.review.json` supplies approved status, an actual reviewer, date, and
the SHA-256 of the exact bytes. Editing notes invalidates the publication hash;
review and republish the edit. If no published file exists, only the matching
lesson from an approved curriculum is eligible. No other topic is searched.
Missing approved notes yield an honest fallback without a provider call.

`reference/tutor-notes-v2-template.md` and 15 original topic drafts in
`reference/tutor-notes-v2/` support content review, including expanded Percentages.
These are drafts, not human-approved teaching material. They are excluded from
retrieval. Inspect estimated size with:

```powershell
.venv/Scripts/python.exe -m scripts.tutor_notes check
```

After an actual person reviews the method, numbers, limits and wording, that person
can publish a topic with their real name and date:

```powershell
.venv/Scripts/python.exe -m scripts.tutor_notes publish percentages --reviewer "REAL REVIEWER" --review-date YYYY-MM-DD --confirm-reviewed
```

This explicit workflow does not invent a reviewer or approve drafts automatically.
The report's 400–600-token target is a guideline; character estimates are not
tokenizer measurements. Review clarity and mathematical scope before word count.

## Run and verify

1. Set `GROQ_API_KEY` in the backend process environment. `.env.example` lists the
   optional `MASTRR_LLM_MODEL`, `MASTRR_REASONING_EFFORT` and
   `MASTRR_MAX_COMPLETION_TOKENS` overrides. This application does not load `.env`
   files automatically; export their values before starting the process.
2. Run `.venv/Scripts/python.exe -m alembic upgrade heads`. Do not reseed a live
   database to upgrade the tutor. The existing launcher now uses `heads` too.
3. Start the API and frontend as described in the project README. Open `/tutor`.
4. Run `.venv/Scripts/python.exe -m pytest -q -s --basetemp=output/tutor-tests-UNIQUE`.
   `-s` and a fresh workspace-local temporary directory avoid this environment's
   output-capture/temp-directory errors. Use a new directory for each run.
5. With reviewed notes and completed mistakes available, set `MASTRR_API_TOKEN`
   and run `.venv/Scripts/python.exe -m scripts.tutor_smoke percentages`.
   It prints actual usage only, then requires both second-visit caches and zero
   second-visit calls. It exits unsuccessfully on fallback or incomplete setup.

Tutoring has its own additive Alembic branch from the committed scoring revision
`b7d41e0c2a15`. The personalised-learning migration already in the working tree
is preserved as a parallel branch. `upgrade heads` upgrades both when present;
the tutor commit also works independently without that uncommitted migration.
SQLite upgrade/downgrade and PostgreSQL offline SQL compilation are tested.
No schema is changed automatically at API startup.

Changing notes, model, effort or token limit changes cache keys. Increment
`PROMPT_VERSION` when changing prompts or when refreshing a provider model under
an unchanged model name. No provider prompt-cache discount is assumed. Concurrent
cold requests can duplicate generation; conflict-safe inserts prevent duplicate
cache rows. This first implementation does not add a distributed job queue.

## Remaining human/live checks

No Groq key was configured during implementation, so live model acceptance,
latency, quality, usage and the 120b-versus-20b comparison remain unmeasured.
Run the smoke tool on a configured machine and read real outputs across at least
five topics. A model comparison must use authorised, completed non-holdout
questions and the same acceptance criteria; the model is not switched here.
The manual `scripts.tutor_compare` tool accepts a topic and repeated `--learner`
arguments with `--confirm-authorized`. It compares up to 20 eligible distinct
mistakes on both models without writing tutor caches or changing the production
model, and emits actual answer-check rates, usage and elapsed times. If fewer
cases are available, its denominator is the actual count, not an assumed 20.
Current bank answer keys and distractors are covered by automated equality
checks, but actual model phrasings and reasoning-topic text still require review.

Official parameter references checked during implementation:
[Groq reasoning](https://console.groq.com/docs/reasoning),
[GPT-OSS 120B](https://console.groq.com/docs/model/openai/gpt-oss-120b), and
[prompt caching](https://console.groq.com/docs/prompt-caching).

## Verification recorded on 27 October 2026

- Current working tree: **185 passed**, one existing Starlette/httpx deprecation
  warning, under real pytest. This includes the earlier uncommitted scoring and
  personalised-learning work; those changes were preserved.
- Tutor-only staged backend on an exported committed baseline: **38 passed**
  (36 tutor cases and two existing migration cases). This independently checks
  that the tutor backend does not require the other uncommitted implementation.
- TypeScript: `tsc --noEmit` passed.
- Frontend: Next.js production build passed, with `/tutor` prerendered successfully.
- Notes: all 15 topics have drafts; character-based estimates are about 508–593
  tokens. Those estimates are not provider token counts or human content approval.
- Live Groq: not run, because no key is configured. Human review: pending.

The sandbox blocked package downloads and build directories initially, and an
isolated API test run stalled inside Python's event-loop socket setup. Dependency
installation, the build and isolated tests succeeded with approved tool escalation.
