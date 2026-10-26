# Mastery scoring upgrade: build status

Updated 26 October 2026. Tracks the task list in the "Mastrr Mastery Scoring Upgrade"
proposal. Earlier slices are recorded in track2-progress.md and track3-progress.md.

## Status by task

| ID | Task | Status | Where |
| --- | --- | --- | --- |
| K1 | Scoring engine: Elo update, trend-based K, "I don't know" rule, shown score | Done. Tests cover every row of the points table | backend/mastery.py, tests/test_mastery.py |
| K2 | Final simulation, confirm 88% / 60% cut-offs and 7/10 retest | Built and run. Team sign-off pending (see below) | scripts/convergence_study.py, docs/simulation-results.md |
| K3 | Diagnostic re-score and safety-zone decision (8-12 questions) | Done. Same answers in any order give the same result | backend/learning.py (finish, extend_diagnostic) |
| K4 | Near-bar picking: alternate levels 3 and 4, skip hidden and seen | Done | LearningService.pick_levels / take_level |
| K5 | Stage 1 analysis: calibration table and learning curves | Script done. Needs pilot data | scripts/pilot_analysis.py |
| S1 | Retest picks 10 unseen level 3-4 questions with fallback | Done (Track 2), now on the shared diagnostic/verification pool | LearningService.retest_questions |
| S2 | Retest scoring 7/10, "I don't know" not correct, every answer updates the rating | Done. No jump to 1.0 | finish(), score_answer() |
| S3 | Gap statuses; a resolved gap reopens only on new answers | Done. Diagnostic now writes Mastered / Borderline / Gap | set_gap(), gaps() |
| S4 | Borderline review of missed and "I don't know" questions, then retest | Done (API and screen) | borderline_review(), frontend/app/review |
| S5 | Pilot design and Stage 2-3 analysis | Forms, protocol and analysis built. Recruiting and survey are people work | docs/pilot-protocol.md, scripts/pilot_analysis.py |
| C1 | Database: answers, rating storage, hidden/sub_topic, version | Done. Migration b7d41e0c2a15 adds answer source, "I don't know" flag, session version and stage | backend/models.py, migrations/ |
| C2 | Question bank 35 assessment items per topic, 3/6/11/11/4, 10 hidden, tag review | 525 assessment drafts and 600 practice drafts are validated across 15 curriculum topics. Human content review and approval pending | content/numbers/questions.json, scripts/question_bank.py, scripts/generate_questions.py |
| C3 | Record every answer with time taken, source and version | Done | submit() |
| C4 | Dashboard: "I don't know" button and wording, browser timing, score line, Borderline colour, 10-question retest screen | Done (Next.js) | frontend/ |
| C5 | Version switch per learner and topic, pilot accounts, updated tests | Done. 103 backend tests pass | scripts/pilot.py, tests/ |
| ALL | End-to-end test, then run the pilot | Scripted end-to-end run passes. Pilot not started | - |

## How the two versions differ in this codebase

The switch is stored per learner and topic (topic_scoring_configs) and copied onto each
session when it starts, so flipping it never changes a session in progress.

| | Current (comparison group) | New |
| --- | --- | --- |
| Diagnostic | 6 questions at levels 1, 2, 3, 4, 5, 3; Mastered when more than half are right, else Gap | 8 questions alternating levels 3 and 4, re-scored together; 88% or more Mastered, under 60% Gap, otherwise one more question at a time up to 12, then Borderline |
| Retest | 3 easiest unseen questions, pass at 2 of 3 | 10 unseen questions, levels 3-4 then nearest, pass at 7 of 10 |
| "I don't know" | Not offered (the API rejects it) | Offered; counts 0.25 and never raises the score |
| Running score | Not kept | Updated after every independent answer; dashboard shows "72% · based on N answers" |

The current version follows the proposal's description of the old app, because the original
_score() code is not in this repository. Practice, verification and review sessions keep the
existing divisibility-check-v1 rules in both versions; in the new version their answers also
move the running score.

## Decisions made while building

- **Answers are whole numbers, not 4-option choices.** "I don't know" still counts 0.25 as the
  proposal specifies. With typed answers a blind guess is almost never right, so this credit is
  generous; revisit after the pilot shows real usage.
- **The re-score treats "I don't know" as 0.25** with a normal prior of sd 1.5 around level 3
  ("mild pull to the middle"). The running update caps its change at zero.
- **Help-assisted and untagged answers never move the rating.** Validation answers store a
  prediction for Stage 1 but never move the rating.
- **Help is closed during diagnostics** so every diagnostic answer is independent evidence.
- **One diagnostic per topic.** A second one is refused once a decision exists.
- **Diagnostic and retest share one pool** (purposes diagnostic and verification, tagged,
  visible). This is what makes the bank split matter, as in the proposal.
- **Validation forms:** hidden questions are split A / B by snake draft (A = levels 1,3,3,4,4;
  B = 2,2,3,4,5). Order is enforced: pre (A) before any topic work, post (B) once the topic is
  Mastered or Resolved, delayed (A) at least 14 days after the post-test. No feedback, no help.
- **Dashboard score is hidden during a retest or check** so a moving number cannot reveal answers.
- **Question families:** the project rule says changing only numbers does not make a new
  family, so each of the 35 questions per topic is a different structure with its own family.

## K2 result and what the team must sign off

docs/simulation-results.md reproduces most of the proposal's figures within a few points:
below-bar Mastered 3.3% (proposal 2.2%), above-bar Gap 1.7% (1.7%), Borderline 47% (43%),
improved learners failing the retest 13% (15%), retest fallback 4.7 of 10 (4).

Two figures differ. Still-weak learners passing the retest come out at 34%, against 18.9% in the
proposal. The current design's below-bar Mastered rate comes out at 61%, against 40%. The
proposal's convergence_study.py and the old _score() are not in this repository. These numbers
depend on the assumed population spread and tutoring gain, which are unknown. The sensitivity
table shows 8/10 would bring still-weak passes to 15% but fail 36% of improved learners.
Decide at the week-1 meeting whether to keep 7/10.

## Remaining work that needs people

1. Review and approve the 210 assessment draft questions (num-101 to num-310): wording, solutions and
   difficulty tags. Use `python -m scripts.question_bank export data/question_bank.csv`, edit
   tags in the sheet, then `apply-tags`. Only approved questions are served.
2. Configure Supabase Auth and create pilot accounts; then assign versions with
   `python -m scripts.pilot assign learner-ids.txt --out data/pilot-assignments.csv`.
3. Recruit about 35 learners, run the protocol in docs/pilot-protocol.md, collect the survey.
4. After the pilot run `python -m scripts.pilot_analysis` and
   `python -m scripts.question_bank flag` (tags with 30+ answers).
5. Browser verification with Playwright is not set up yet; the end-to-end check used the API
   through the frontend proxy.
